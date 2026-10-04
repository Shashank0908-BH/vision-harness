"""Route before execution; preserve measured estimates separately from review."""

import hashlib
import time
from pathlib import Path

from ..artifacts import ArtifactStore
from ..contracts import Answer
from ..providers.astra import Astra
from ..providers.jev import Jev
from ..tracing import Trace, write_json
from .catalog import ROOT, eligible, load_catalog, rank, sha256, verify_procedure
from .contracts import Intent, Proposal, ScorableProcedure
from .executor import execute, input_probe


def validate_proposal(proposal, procedures):
    ids = {p.plan_id for p in procedures}
    proposed = [c.plan_id for c in proposal.candidates]
    if len(proposed) != len(ids) or set(proposed) != ids or proposal.preferred_id not in ids:
        raise ValueError("Astra must describe every eligible procedure exactly once and choose one")


def validate_answer(answer, evidence):
    if answer.status == "answered":
        if isinstance(answer.value, bool) or not isinstance(answer.value, (int, float)) or answer.value != evidence["count"]:
            raise ValueError("Astra's answer does not equal the measured instance count")
        if set(answer.evidence_ids) != {evidence["evidence_id"]}:
            raise ValueError("Answer must reference exactly the selected measurement")
    elif answer.value is not None:
        raise ValueError("An abstained/error answer cannot carry a numeric final value")


def source_hash():
    digest = hashlib.sha256()
    for path in sorted((ROOT / "src/vision_harness").rglob("*.py")):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run_route(image: Path, question: str, settings, catalog_path: Path, output: Path,
              compare_all=False, observer=None, astra=None, jev=None, executor=execute):
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    trace = Trace(output, observer)
    manifest = {
        "run_id": output.name, "mode": "specialist-routing-v1", "offline": False,
        "config": settings.model_dump(), "catalog_sha256": sha256(catalog_path),
        "source_sha256": source_hash(), "compare_all": compare_all,
        "execution": "native isolated environments; Harbor ATIF export, not a Harbor container job",
        "review_policy": "soft concern => provisional estimate; validation failure => error",
    }
    write_json(output / "manifest.json", manifest)
    result = {"status": "error", "value": None, "review_status": "not_run"}
    stage = "initialization"
    try:
        catalog = load_catalog(catalog_path)
        write_json(output / "catalog.json", catalog.model_dump())
        store = ArtifactStore(output, settings.limits.max_pixels, settings.limits.max_input_bytes)
        store.import_image(image)
        probe = input_probe(store.load("original"))
        trace.emit("input", {"question": question, "probe": probe})
        astra = astra or Astra(settings, trace)
        jev = jev or Jev(settings, trace)
        stage = "astra_intent"
        intent = astra.structured("interpret task and input modality", question,
                                  [store.image_input("original")], {"input_probe": probe}, Intent)
        write_json(output / "intent.json", intent.model_dump())
        procedures, rejected = eligible(catalog, intent, probe)
        trace.emit("eligibility", {"eligible": [p.plan_id for p in procedures], "rejected": rejected})
        if not procedures:
            result = {"status": "unsupported", "value": None, "review_status": "not_run",
                      "reason": "No registered procedure matches the task and validated input conditions"}
            write_json(output / "research-request.json", {"query": question, "intent": intent.model_dump(), "rejected": rejected})
            return result
        stage = "registry_validation"
        for p in procedures:
            verify_procedure(p)
        stage = "astra_proposal"
        context = {"intent": intent.model_dump(), "input_probe": probe,
                   "eligible_procedures": [p.model_dump() for p in procedures]}
        proposal = astra.structured("describe every eligible procedure and select your preferred one",
                                   question, [store.image_input("original")], context, Proposal)
        validate_proposal(proposal, procedures)
        write_json(output / "proposal.json", proposal.model_dump())
        reasons = {c.plan_id: c for c in proposal.candidates}
        candidates = [ScorableProcedure(plan_id=p.plan_id, procedure=p,
                      rationale=reasons[p.plan_id].rationale, assumptions=reasons[p.plan_id].assumptions)
                      for p in procedures]
        stage = "jev_selection"
        # Jev does not receive Astra's preferred ID or image pixels. Rationale is attributed.
        assessments = jev.assess({"question": question, "intent_from_astra": intent.model_dump(),
                                 "input_probe": probe, "pixels_available_to_jev": False,
                                 "benchmark_labels_available": False}, candidates)
        ranking = rank(assessments, [p.plan_id for p in procedures])
        decision = {"astra_preferred_id": proposal.preferred_id, "jev_ranking": ranking,
                    "selected_id": ranking[0], "assessments": [a.model_dump() for a in assessments],
                    "tie_rule": "descending Score, then ascending stable procedure ID",
                    "frozen_before_execution": True, "catalog_sha256": manifest["catalog_sha256"],
                    "image_sha256": store.records["original"]["sha256"]}
        write_json(output / "decision.json", decision)
        decision_hash = sha256(output / "decision.json")
        trace.emit("routing_decision", {**decision, "sha256": decision_hash})
        selected = next(p for p in procedures if p.plan_id == ranking[0])
        stage = "specialist_execution"
        evidence = executor(selected, store, trace, output)
        stage = "astra_answer"
        answer = astra.structured("return a grounded estimate using only the selected procedure",
                                 question, [store.image_input("original"), store.image_input(evidence["overlay_id"])],
                                 {"intent": intent.model_dump(), "procedure": selected.model_dump(), "evidence": evidence}, Answer)
        validate_answer(answer, evidence)
        write_json(output / "candidate-answer.json", answer.model_dump())
        stage = "jev_review"
        review = jev.review({"question": question, "intent_from_astra": intent.model_dump(),
                             "input_probe": probe, "procedure": selected.model_dump(),
                             "evidence": evidence, "answer": answer.model_dump(),
                             "pixels_available_to_jev": False,
                             "deterministic_checks": {"input_hash": True, "checkpoint_hashes": True,
                                                      "full_frame_integer_instances": True, "answer_count_grounded": True}})
        write_json(output / "review.json", review.model_dump())
        supported = review.support_probability >= settings.review.minimum_support_probability
        result = {**answer.model_dump(), "selected_id": selected.plan_id,
                  "review_status": "supported" if supported else "caution",
                  "review_support": review.support_probability,
                  "review_is_calibrated_accuracy": False,
                  "decision_sha256": decision_hash,
                  "limitations": answer.limitations + ([] if supported else ["Jev review did not meet the support threshold; this remains a provisional measurement."])}
        trace.emit("answer_review", {"review_status": result["review_status"], **review.model_dump()})
        # Freeze the selected answer before evaluation-only competing results exist.
        write_json(output / "answer.json", result)
        trace.emit("final_answer", result)
        if compare_all:
            stage = "comparison_only"
            comparison = {selected.plan_id: {"status": "success", "evidence": evidence}}
            for p in procedures:
                if p.plan_id == selected.plan_id:
                    continue
                try:
                    comparison[p.plan_id] = {"status": "success", "evidence": executor(p, store, trace, output)}
                except Exception as error:
                    comparison[p.plan_id] = {"status": "error", "error": str(error)}
            if sha256(output / "decision.json") != decision_hash:
                raise ValueError("Frozen routing decision changed")
            write_json(output / "comparison.json", comparison)
            trace.emit("comparison_finished", {"statuses": {k: v["status"] for k, v in comparison.items()},
                                               "withheld_from_selected_answer": True})
        return result
    except Exception as error:
        result = {"status": "error", "value": None, "review_status": "not_completed",
                  "stage": stage, "error_type": type(error).__name__, "error": str(error)}
        trace.emit("error", result)
        return result
    finally:
        write_json(output / "answer.json", result)
        manifest["elapsed_seconds"] = time.monotonic() - started
        manifest["status"] = result["status"]
        write_json(output / "manifest.json", manifest)
