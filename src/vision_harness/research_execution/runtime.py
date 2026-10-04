"""Bounded research → selection → documentation → planning → execution → review."""

import importlib.metadata
import json
import platform
import shutil
import time
import traceback
import uuid
from pathlib import Path

from ..providers.astra import Astra
from ..tracing import Trace, redact, write_json
from .contracts import Inspection, Policy, ScalarAnswer, Task
from .discovery import discover
from .documents import compile_usage
from .evidence import image_content, inspect_artifacts, probe
from .executor import execute
from .planning import program_hash, propose
from .replay import load_prefix
from .scoring import Scorer, retain_candidates


def inventory():
    versions = {}
    for name in ("numpy", "scipy", "scikit-image", "opencv-python-headless", "tifffile",
                 "stardist", "tensorflow", "torch", "cellpose", "csbdeep"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {"os": platform.system(), "machine": platform.machine(), "python": platform.python_version(),
            "accelerator": "CPU only; no GPU or macOS MPS inside this Docker task",
            "resources": "2 CPU cores, 6 GiB RAM per trial", "packages": versions,
            "checkpoint_cache": "/opt/checkpoints/stardist (2D_versatile_fluo checkpoint files)",
            "installation": "pip --user permitted, internet for author docs and public weights; limited by round timeout",
            "preinstalled_is_not_a_ranking_signal": True}


def run(query, mode, settings, directory, raw=Path("/data/input.tif"), preview=Path("/data/input.png"), policy=None, development_prefix=None):
    if mode not in ("vanilla", "full"):
        raise ValueError("Unknown research-execution arm")
    if development_prefix and mode != "full":
        raise ValueError("Development prefix replay applies only to the full workflow")
    policy = policy or Policy()
    if (directory / "manifest.json").exists():
        raise ValueError("Trial output exists; use a fresh directory for an independent run")
    directory.mkdir(parents=True, exist_ok=True)
    trace = Trace(directory, lambda event: print(json.dumps({"sequence": event["sequence"], "kind": event["kind"],
        **({"stage": event["data"].get("stage")} if event["kind"] == "stage" else {})}), flush=True))
    started = time.monotonic()
    calls = 0

    def budget():
        nonlocal calls
        if calls >= policy.max_provider_calls or time.monotonic() - started >= policy.max_seconds:
            raise TimeoutError("Trial controller-call or elapsed-time budget exhausted")
        calls += 1

    trace.before_call = budget
    (directory / "artifacts").mkdir()
    shutil.copy2(preview, directory / "artifacts/original.png")
    trace.emit("input", {"question": query, "mode": mode, "preview": "artifacts/original.png"})
    manifest = {"run_id": uuid.uuid4().hex, "mode": mode, "offline": False,
                "config": settings.model_dump(), "policy": policy.model_dump(), "elapsed_seconds": 0,
                "call_budget_semantics": "controller API calls plus Codex sessions; Codex internal turns logged separately"}
    write_json(directory / "manifest.json", manifest)
    observations, feedback, chosen = [], [], None
    answer = {"status": "error", "count": None, "review_status": "not_reached"}
    task, environment, facts = None, None, None

    def packet(stage, job, expected, **context):
        value = {"protocol": policy.version, "stage": stage, "original_query": query,
                 "stage_job": job, "expected_output": expected,
                 "task": task.model_dump() if task else None,
                 "observed_input": facts, "environment": environment,
                 "feedback": feedback, "context": context,
                 "constraints": {"no_reference_answers": True, "max_rounds": policy.max_rounds,
                     "documentation_pages_per_candidate": policy.max_document_pages_per_candidate,
                     "elapsed_seconds": round(time.monotonic()-started, 2)}}
        write_json(directory / "stage-packets" / f"{trace.sequence+1:04d}-{stage}.json", value)
        trace.emit("stage", {"stage": stage, "job": job})
        return value

    try:
        astra = Astra(settings, trace)
        images = [image_content(preview)]
        if mode == "vanilla":
            # Same query and preview; no research, tool results, model docs or Jev state.
            astra.instructions = "Answer the user's image question directly from the supplied image. Return the requested JSON schema. Report uncertainty honestly."
            result = astra.structured("answer directly from the image", query, images,
                                      {"counting_rule": "include visible border nuclei"}, ScalarAnswer)
            if result.status == "answered" and result.count is None:
                raise ValueError("Answered status requires a count")
            answer = {**result.model_dump(), "review_status": "not_applicable"}
            return answer
        environment, facts = inventory(), probe(raw)
        candidates = usage = replay_plans = None
        if development_prefix:
            task, candidates, usage, replay_plans, identity = load_prefix(development_prefix, query, raw, settings, policy)
            shutil.copytree(development_prefix, directory / "development-prefix")
            manifest["development_replay"] = identity
            trace.emit("development_prefix_replayed", identity)
        else:
            intake = packet("intake", "Decompose the requested outcome into 3–6 necessary parts and acceptance checks.", Task.__name__)
            task = astra.structured("Structure the task; keep query exactly unchanged. Use unique requirement IDs. "
                "Cover input preparation, instance segmentation/separation, count extraction and verification. "
                "List only necessary requirements; every listed requirement must have required=true. "
                "Put optional conveniences in assumptions or unknowns, not requirements.", query, images, intake, Task)
        if task.query != query or len({r.requirement_id for r in task.requirements}) != len(task.requirements):
            raise ValueError("Intake changed the query or duplicated requirement IDs")
        write_json(directory / "task.json", task.model_dump())
        scorer = Scorer(settings, trace)
        research_count, used_programs = (1 if development_prefix else 0), set()
        for round_index in range(1, policy.max_rounds+1):
            round_dir = directory / f"round-{round_index:02d}"
            round_dir.mkdir()
            research_needed = candidates is None or (feedback and feedback[-1].get("recommended_action") == "research")
            if research_needed:
                if research_count >= policy.max_research_passes:
                    break
                research_count += 1
                research_dir = directory / f"research-{research_count:02d}"
                catalog = discover(astra, task, packet("research", "Discover documented candidates for every task part.", "Catalog"), research_dir)
                score_packet = packet("candidate_scoring", "Score every candidate against each linked task requirement.", "all candidate-role scores")
                scores = scorer.candidates(task, catalog, score_packet, research_dir / "candidate-scores.json")
                candidates = retain_candidates(task, catalog, scores, policy.max_retained_models,
                                                policy.minimum_support_candidate_score)
                selected_ids = {c.candidate_id for c in candidates}
                write_json(research_dir / "retention.json", {
                    "rule": "top model alternatives by mean score; best per requirement; complementary libraries/algorithms with any role score >= support threshold. Coverage can exceed model soft cap",
                    "support_threshold": policy.minimum_support_candidate_score,
                    "candidates": [{"candidate_id": c.candidate_id, "retained": c.candidate_id in selected_ids,
                        "scores": scores[c.candidate_id], "reason": "model alternative, best role coverage, or relevant complementary support" if c.candidate_id in selected_ids else "lower model rank or insufficient support score"}
                                   for c in catalog.candidates]})
                usage, _ = compile_usage(astra, task, candidates,
                    packet("documentation", "Read usage sources and extract precise input, inference and output contracts.", "UsageSet"),
                    research_dir / "documents", policy)
                ready_ids = {u.candidate_id for u in usage.contracts if u.ready_for_trial}
                documented_roles = {r for c in candidates if c.candidate_id in ready_ids for r in c.requirement_ids}
                missing = [r.requirement_id for r in task.requirements if r.required and r.requirement_id not in documented_roles]
                if missing:
                    feedback.append({"stage": "documentation", "recommended_action": "research",
                                     "missing_documented_requirements": missing, "usage": usage.model_dump()})
                    trace.emit("documentation_gap", feedback[-1])
                    continue
            if replay_plans is not None:
                plans, replay_plans = replay_plans, None
                write_json(round_dir / "plans.json", plans.model_dump())
            else:
                plans = propose(astra, task, candidates, usage,
                    packet("planning", "Design complete documented programs addressing task requirements and prior feedback.", "PlanSet"), images, round_dir)
            plan_scores = scorer.plans(plans.plans,
                packet("plan_scoring", "Score every complete plan, including its executable code and previous review conditions.", "all plan scores", usage=usage.model_dump()),
                round_dir / "plan-scores.json")
            ranked = sorted(plans.plans, key=lambda p: (-plan_scores[p.plan_id], p.plan_id))
            novel = [p for p in ranked if program_hash(p.python_program) not in used_programs]
            if not novel:
                trace.emit("stop", {"reason": "no new approved program; no-progress limit"})
                break
            plan = novel[0]
            used_programs.add(program_hash(plan.python_program))
            write_json(round_dir / "selection.json", {"selected_plan_id": plan.plan_id, "scores": plan_scores,
                "astra_preference": plans.preferred_plan_id, "tie_break": "lexicographic plan ID"})
            execution_dir = round_dir / "execution"
            try:
                remaining = policy.max_seconds - (time.monotonic()-started)
                if remaining <= 5:
                    raise TimeoutError("Insufficient trial time left for execution")
                outcome = execute(plan,
                    packet("execution", "Execute the frozen approved plan and return actual outputs or a specific failure.", "ExecutionOutcome"),
                    execution_dir, settings, trace, min(policy.codex_timeout_seconds, remaining))
                measured = inspect_artifacts(execution_dir, outcome, facts["shape"], preview)
            except Exception as error:
                failure = {"plan_id": plan.plan_id, "stage": "execution", "error_type": type(error).__name__,
                           "error": str(error), "recommended_action": "replan"}
                feedback.append(failure)
                write_json(round_dir / "execution-failure.json", failure)
                trace.emit("execution_failed", failure)
                continue
            inspection = astra.structured("Inspect the original image and the measured result overlay. "
                "Identify missed, merged, split or spurious instances and unresolved input conditions. "
                "The second image is an overlay, not ground truth. Don't certify accuracy without evidence.",
                query, images + [image_content(execution_dir / "overlay.png")],
                packet("visual_inspection", "Compare observed artifacts with the requested task and documented assumptions.", "Inspection", measured=measured), Inspection)
            if inspection.plan_id != plan.plan_id:
                raise ValueError("Visual inspection returned the wrong plan ID")
            write_json(round_dir / "inspection.json", inspection.model_dump())
            observed = {**measured, "inspection": inspection.model_dump(),
                        "approved_plan": plan.model_dump(exclude={"python_program"}),
                        "usage_contracts": [u.model_dump() for u in usage.contracts if u.candidate_id in plan.candidate_ids],
                        "round": round_index, "artifact_directory": str(execution_dir)}
            observations.append(observed)
            output_scores = scorer.outputs(observations,
                packet("output_scoring", "Choose among actual observed executions using evidence and review history.", "all observed output scores"),
                round_dir / "output-scores.json")
            proposed_choice = sorted(observations, key=lambda o: (-output_scores[o["plan_id"]], o["plan_id"]))[0]
            review = scorer.review(packet("review", "Assess method compatibility and evidence support; decide whether further work is needed.", "Noul judgments", selected=proposed_choice),
                                   round_dir / "review.json")
            # Only replace the published answer/mask pair after this review succeeds.
            chosen = proposed_choice
            approved = all(a["noul"] >= policy.review_support_threshold for a in review.values())
            answer = {"status": "answered", "count": chosen["count"], "selected_plan_id": chosen["plan_id"],
                      "review_status": "approved" if approved else "provisional", "review": review,
                      "explanation": "Count extracted independently from the selected observed instance map.",
                      "limitations": chosen["inspection"]["suspected_failures"] + chosen["inspection"]["unresolved_requirements"]}
            write_json(directory / "checkpoint-answer.json", answer)
            feedback.append({"plan_id": chosen["plan_id"], "review": review,
                "selected_inspection": chosen["inspection"], "latest_execution": measured,
                "latest_inspection": inspection.model_dump(),
                "recommended_action": chosen["inspection"]["recommended_action"] if chosen["inspection"]["recommended_action"] != "finish" else "replan",
                "next_evidence_needed": chosen["inspection"]["next_evidence_needed"]})
            if approved and chosen["inspection"]["recommended_action"] == "finish":
                trace.emit("stop", {"reason": "review supported and visual inspector recommends finish"})
                break
        if chosen:
            shutil.copy2(Path(chosen["artifact_directory"]) / "labels.npz", directory / "labels.npz")
        if answer["count"] is None:
            answer.update(status="error", error="No complete scored, executed and reviewed result", failures=feedback)
        return answer
    except Exception as error:
        trace.emit("trial_error", {"error_type": type(error).__name__, "error": str(error)})
        (directory / "error.txt").write_text(redact(traceback.format_exc()))
        # A provider error never becomes a Jev rejection. Preserve an earlier fully reviewed result, if any.
        answer.update(error_type=type(error).__name__, error=str(error))
        if answer["count"] is not None:
            answer["review_status"] = "provisional_after_error"
            if chosen:
                shutil.copy2(Path(chosen["artifact_directory"]) / "labels.npz", directory / "labels.npz")
        return answer
    finally:
        answer.update(mode=mode, elapsed_seconds=time.monotonic()-started, controller_calls=calls)
        write_json(directory / "answer.json", answer)
        trace.emit("final", answer)
        manifest.update(elapsed_seconds=answer["elapsed_seconds"], controller_calls=calls)
        write_json(directory / "manifest.json", manifest)
