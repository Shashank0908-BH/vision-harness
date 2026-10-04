"""Bounded observed-output selection, with an independent visual-only candidate."""

import time
from pathlib import Path

import cv2
import numpy as np

from ..artifacts import ArtifactStore
from ..contracts import Answer
from ..providers.astra import Astra
from ..providers.jev import Jev
from ..routing.catalog import eligible, load_catalog, rank, sha256
from ..routing.contracts import Intent
from ..routing.executor import execute, input_probe
from ..routing.runtime import source_hash
from ..tracing import Trace, redact, write_json
from .contracts import Inspection, ObservedCandidate
from .measurements import disagreement, mask_candidate, visual_candidate

MAX_PROCEDURES = 4


def validate_inspection(inspection, candidates):
    ids = [c.plan_id for c in candidates]
    seen = [o.plan_id for o in inspection.observations]
    if len(seen) != len(ids) or set(seen) != set(ids):
        raise ValueError("Inspection must describe every valid candidate exactly once")


def run_comparison(
    image: Path,
    question: str,
    settings,
    vanilla_settings,
    catalog_path: Path,
    output: Path,
    observer=None,
    *,
    astra=None,
    vanilla=None,
    jev=None,
    executor=execute,
    offline=False,
):
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    trace = Trace(output, observer)
    manifest = {
        "run_id": output.name,
        "mode": "observed-output-routing-v2",
        "offline": offline,
        "config": settings.model_dump(),
        "vanilla_config": vanilla_settings.model_dump(),
        "source_sha256": source_hash(),
        "maximum_specialist_executions": MAX_PROCEDURES,
        "execution": "native registered workers and stateless hosted requests",
    }
    write_json(output / "manifest.json", manifest)
    result = {"status": "error", "value": None, "review_status": "not_completed"}
    stage = "configuration"
    errors = []

    def failed(candidate_id, error, kind="execution_error"):
        record = {
            "candidate_id": candidate_id,
            "kind": kind,
            "error_type": type(error).__name__,
            "error": str(error)[:2000],
        }
        errors.append(record)
        write_json(output / "candidate-errors.json", errors)
        trace.emit("candidate_excluded", record)

    try:
        if settings.loop.enabled:
            raise ValueError(
                "Observed-output v2 has no review/replanning loop; use its separate config"
            )
        if settings.models.astra != vanilla_settings.models.astra:
            raise ValueError("The independent visual candidate must use the same Astra model")
        catalog = load_catalog(catalog_path)
        if any(p.plan_id == "vanilla-astra" for p in catalog.procedures):
            raise ValueError("Catalog uses the reserved visual candidate ID")
        manifest["catalog_sha256"] = sha256(catalog_path)
        manifest["prompt_sha256"] = {
            path: sha256(Path(path))
            for path in {
                settings.paths.astra_prompt,
                settings.paths.plan_rubric,
                settings.paths.review_rubric,
                vanilla_settings.paths.astra_prompt,
            }
        }
        write_json(output / "catalog.json", catalog.model_dump())
        write_json(output / "candidate-errors.json", errors)
        stage = "input"
        if image.stat().st_size > settings.limits.max_input_bytes:
            raise ValueError("Input image exceeds configured byte limit")
        native = cv2.imread(str(image), cv2.IMREAD_UNCHANGED)
        if native is None or native.dtype != np.uint8:
            raise ValueError(
                "Compare requires an explicit 8-bit raster conversion; high-bit-depth science images must not be silently downcast"
            )
        if native.ndim not in (2, 3) or (native.ndim == 3 and native.shape[2] != 3):
            raise ValueError("Compare supports grayscale or three-channel raster images")
        store = ArtifactStore(output, settings.limits.max_pixels, settings.limits.max_input_bytes)
        store.import_image(image)
        trace.emit("input", {"question": question})
        probe = input_probe(store.load("original"))
        manifest["image_sha256"] = store.records["original"]["sha256"]
        write_json(output / "manifest.json", manifest)
        candidates, masks, overlays = [], {}, []

        # Freeze the independent estimate before any interpretation or tool outputs.
        stage = "vanilla_candidate"
        try:
            baseline = (vanilla or Astra(vanilla_settings, trace)).answer(
                question,
                [store.image_input("original")],
                {"mode": "vanilla", "evidence": []},
            )
            write_json(output / "vanilla-answer.json", baseline.model_dump())
            candidate = visual_candidate(baseline, manifest["image_sha256"], settings.models.astra)
            if candidate:
                candidates.append(candidate)
            else:
                failed("vanilla-astra", ValueError(baseline.explanation), baseline.status)
        except Exception as error:
            failed("vanilla-astra", error)
        trace.emit("vanilla_frozen", {"candidate_available": bool(candidates)})

        stage = "intent"
        astra = astra or Astra(settings, trace)
        intent = astra.structured(
            "interpret the task and modality",
            question,
            [store.image_input("original")],
            {"input_probe": probe},
            Intent,
        )
        write_json(output / "intent.json", intent.model_dump())
        procedures, rejected = eligible(catalog, intent, probe)
        write_json(
            output / "eligibility.json",
            {"eligible": [p.plan_id for p in procedures], "rejected": rejected},
        )
        if not procedures:
            write_json(
                output / "research-request.json",
                {"query": question, "intent": intent.model_dump(), "rejected": rejected},
            )
            result = {
                "status": "unsupported",
                "value": None,
                "review_status": "not_completed",
                "explanation": "No eligible registered procedure; compare is scoped to the registered modality/task.",
            }
            return result
        if len(procedures) > MAX_PROCEDURES:
            raise ValueError(
                "Eligible catalog exceeds the four-procedure experiment budget; no silent truncation"
            )
        stage = "specialist_candidates"
        for procedure in procedures:
            try:
                evidence = executor(procedure, store, trace, output)
                candidate, labels = mask_candidate(procedure, evidence, store, output)
                # Reject an unusable visual artifact before admitting the candidate.
                overlay_id = evidence["overlay_id"]
                if store.load(overlay_id).shape != store.load("original").shape:
                    raise ValueError("Overlay is not in original image geometry")
                candidates.append(candidate)
                masks[candidate.plan_id] = labels
                overlays.append({"candidate_id": candidate.plan_id, "artifact_id": overlay_id})
            except Exception as error:
                failed(procedure.plan_id, error)
        if not candidates:
            result = {
                "status": "abstained",
                "value": None,
                "review_status": "not_completed",
                "explanation": "No valid numeric candidate remained.",
                "candidate_failures": errors,
            }
            return result
        write_json(output / "candidates.json", [c.model_dump() for c in candidates])
        candidates_hash = sha256(output / "candidates.json")
        differences = disagreement(candidates, masks)
        write_json(output / "disagreement.json", differences)
        trace.emit(
            "candidates_frozen", {"sha256": candidates_hash, "ids": [c.plan_id for c in candidates]}
        )

        stage = "visual_inspection"
        image_order = [{"candidate_id": None, "artifact_id": "original"}, *overlays]
        inspection = astra.structured(
            "inspect all candidate outputs without changing their counts",
            question,
            [store.image_input(item["artifact_id"]) for item in image_order],
            {
                "intent": intent.model_dump(),
                "candidates": [c.model_dump() for c in candidates],
                "image_order": image_order,
                "disagreement": differences,
                "candidate_failures": errors,
            },
            Inspection,
        )
        validate_inspection(inspection, candidates)
        write_json(output / "inspection.json", inspection.model_dump())
        observations = {o.plan_id: o for o in inspection.observations}
        scorable = [
            ObservedCandidate(
                plan_id=c.plan_id, candidate=c, astra_visual_observations=observations[c.plan_id]
            )
            for c in candidates
        ]
        state = {
            "question": question,
            "intent_from_astra": intent.model_dump(),
            "input_probe": probe,
            "disagreement": differences,
            "candidate_failures": errors,
            "inspection_limitations": inspection.limitations,
            "observed_candidates": [c.model_dump() for c in scorable],
            "astra_observations_are_not_independent_measurements": True,
            "pixels_available_to_jev": False,
            "benchmark_labels_available": False,
        }
        stage = "jev_output_selection"
        jev = jev or Jev(settings, trace)
        assessments = jev.assess(state, scorable)
        ranking = rank(assessments, [c.plan_id for c in candidates])
        selected = next(c for c in candidates if c.plan_id == ranking[0])
        decision = {
            "selected_id": selected.plan_id,
            "ranking": ranking,
            "assessments": [a.model_dump() for a in assessments],
            "candidates_sha256": candidates_hash,
            "selection_timing": "after all attempted candidate executions and visual inspection",
            "tie_rule": "descending Jev Score, then ascending candidate ID",
            "scores_are_calibrated_accuracy": False,
        }
        write_json(output / "decision.json", decision)
        decision_hash = sha256(output / "decision.json")
        trace.emit("output_decision", decision)
        # Mechanical provenance-preserving copy: neither language model rewrites a count.
        answer = Answer(
            status="answered",
            value=selected.value,
            evidence_ids=[selected.evidence_id],
            explanation=f"Selected {selected.plan_id}; the count is copied from its saved {selected.kind}.",
            limitations=selected.limitations
            + inspection.limitations
            + observations[selected.plan_id].concerns,
        )
        write_json(output / "candidate-answer.json", answer.model_dump())
        stage = "jev_review"
        review = jev.review(
            {
                **state,
                "selected": selected.model_dump(),
                "selected_visual_observations": observations[selected.plan_id].model_dump(),
                "answer": answer.model_dump(),
                "count_copied_exactly": True,
            }
        )
        write_json(output / "review.json", review.model_dump())
        if (
            sha256(output / "candidates.json") != candidates_hash
            or sha256(output / "decision.json") != decision_hash
        ):
            raise ValueError("Frozen candidate collection or selection changed")
        supported = review.support_probability >= settings.review.minimum_support_probability
        result = {
            **answer.model_dump(),
            "selected_id": selected.plan_id,
            "source_kind": selected.kind,
            "review_status": "supported" if supported else "caution",
            "review_support": review.support_probability,
            "review_is_calibrated_accuracy": False,
            "candidate_failures": errors,
            "decision_sha256": decision_hash,
        }
        if not supported:
            result["limitations"].append(
                "Jev review is below the support threshold; this is a provisional estimate."
            )
        trace.emit(
            "answer_review", {"review_status": result["review_status"], **review.model_dump()}
        )
        return result
    except Exception as error:
        result = {
            "status": "error",
            "value": None,
            "review_status": "not_completed",
            "stage": stage,
            "error_type": type(error).__name__,
            "error": str(error),
            "candidate_failures": errors,
        }
        trace.emit("error", result)
        return redact(result)
    finally:
        trace.emit("final_answer", result)
        write_json(output / "answer.json", result)
        manifest.update(elapsed_seconds=time.monotonic() - started, status=result["status"])
        write_json(output / "manifest.json", manifest)
