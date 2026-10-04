"""Bounded orchestration; providers, tools and selection remain replaceable."""

import hashlib
import importlib.metadata
import time
import uuid
from pathlib import Path
from typing import Literal

from .artifacts import ArtifactStore
from .config import Settings
from .contracts import Answer, Evidence, PlanSet
from .review_loop import LoopStopped, ReviewLoop, operation_keys
from .selection import select
from .tools.dispatch import execute, probe
from .tools.registry import Registry
from .tracing import Trace, write_json

Mode = Literal["vanilla", "tools", "select", "review", "full"]


def abstain(reason: str, evidence: list[Evidence]) -> Answer:
    return Answer(
        status="abstained",
        value=None,
        explanation=reason,
        evidence_ids=[e.evidence_id for e in evidence],
        limitations=[reason],
    )


def run(
    image: Path,
    question: str,
    settings: Settings,
    mode: Mode = "full",
    *,
    output: Path | None = None,
    observer=None,
    astra_factory=None,
    jev_factory=None,
    checkpoint=None,
    frozen_plans: PlanSet | None = None,
    offline=False,
) -> Path:
    """Factories support deterministic tests without substituting providers in live mode."""
    if mode not in ("vanilla", "tools", "select", "review", "full"):
        raise ValueError("Unknown execution mode")
    if frozen_plans and mode == "vanilla":
        raise ValueError("Vanilla mode cannot receive candidate plans")
    directory = output or Path(settings.paths.runs) / uuid.uuid4().hex[:12]
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("Output directory must be empty; existing runs are never overwritten")
    trace = Trace(directory, observer)
    store = ArtifactStore(directory, settings.limits.max_pixels, settings.limits.max_input_bytes)
    start = time.monotonic()
    manifest = {
        "run_id": directory.name,
        "mode": mode,
        "offline": offline,
        "question": question,
        "config": settings.model_dump(),
        "frozen_plans": frozen_plans.model_dump() if frozen_plans else None,
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("vision-harness", "openai", "opencv-python-headless", "pydantic")
        },
    }
    resources = [
        settings.paths.capabilities,
        settings.paths.astra_prompt,
        settings.paths.plan_rubric,
        settings.paths.review_rubric,
    ]
    if settings.loop.enabled:
        resources.append(settings.loop.checks_path)
    manifest["resource_sha256"] = {
        p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in resources
    }
    write_json(directory / "manifest.json", manifest)
    evidence: list[Evidence] = []
    loop = None
    try:
        store.import_image(image)
        trace.emit(
            "input",
            {"question": question, "artifact_id": "original", "mode": mode, "offline": offline},
        )
        if astra_factory is None:
            from .providers.astra import Astra

            astra_factory = Astra
        astra = astra_factory(settings, trace)
        needs_selection, needs_review = mode in ("select", "full"), mode in ("review", "full")
        jev = None
        if needs_selection or needs_review:
            if jev_factory is None:
                from .providers.jev import Jev

                jev_factory = Jev
            jev = jev_factory(settings, trace)
        if mode == "vanilla":
            answer = astra.answer(
                question,
                [store.image_input("original")],
                {"image_artifact_ids": ["original"], "evidence": []},
            )
            if set(answer.evidence_ids) - {"original"}:
                raise ValueError("Vanilla answer cited evidence it did not receive")
        else:
            registry = Registry(Path(settings.paths.capabilities))
            if settings.loop.enabled and needs_review:
                loop = ReviewLoop(settings, trace, store)
                trace.before_call = loop.before_call
            evidence.append(probe(store, specialist="stardist" in registry.entries))
            trace.emit("evidence", evidence[-1].model_dump())
            feedback = []
            answer = abstain("No eligible plan completed", evidence)
            for round_id in range(1, settings.limits.max_rounds + 1):
                if loop:
                    loop.check_time()
                context = {
                    "evidence": [e.model_dump() for e in evidence],
                    "capabilities": registry.describe(),
                    "feedback": feedback,
                    "max_candidates": settings.limits.max_candidates,
                    "image_artifact_ids": ["original"],
                    "round": round_id,
                }
                if loop:
                    context.update(loop.context())
                plans = (
                    frozen_plans
                    if frozen_plans
                    else astra.plan(question, [store.image_input("original")], context)
                )
                if len(plans.candidates) > settings.limits.max_candidates:
                    raise ValueError("Planner exceeded candidate limit")
                write_json(directory / f"plans-{round_id}.json", plans.model_dump())
                trace.emit("plans", plans.model_dump())
                if checkpoint:
                    checkpoint(
                        "Review candidate plans before selection/execution", plans.model_dump()
                    )
                eligible = []
                excluded = {}
                for candidate in plans.candidates:
                    try:
                        registry.validate(candidate, settings.limits.max_steps_per_plan)
                        if loop and loop.repeated(candidate):
                            excluded[candidate.plan_id] = (
                                "All effective operations were already attempted; renamed steps or inactive parameter changes add no evidence"
                            )
                            continue
                        eligible.append(candidate)
                    except ValueError:
                        pass  # Selection records exact rejection reasons for every candidate.
                assessments = (
                    jev.assess(
                        {
                            "question": question,
                            **context,
                            "astra_observations_unverified": plans.observations,
                        },
                        eligible,
                    )
                    if needs_selection
                    else None
                )
                if assessments is not None:
                    trace.emit("assessments", {"items": [a.model_dump() for a in assessments]})
                selection = select(
                    plans,
                    registry,
                    settings.limits.max_steps_per_plan,
                    settings.selection,
                    assessments,
                    excluded=excluded,
                )
                trace.emit("selection", selection.model_dump())
                round_record = {
                    "round": round_id,
                    "plans": plans.model_dump(),
                    "selection": selection.model_dump(),
                    "assessments": [a.model_dump() for a in assessments]
                    if assessments is not None
                    else [],
                    "new_evidence_ids": [],
                    "new_observations": 0,
                }
                if loop:
                    loop.record(round_record)
                if checkpoint:
                    checkpoint(
                        "Review selected plans before executing tools", selection.model_dump()
                    )
                if not selection.selected_ids:
                    feedback.append(selection.model_dump())
                    answer = abstain(selection.reason, evidence)
                    if loop:
                        raise LoopStopped("No eligible new plan selected: " + selection.reason)
                    if frozen_plans:
                        break
                    continue
                for plan in plans.candidates:
                    if plan.plan_id not in selection.selected_ids:
                        continue
                    refs = {"original": "original"}
                    keys = operation_keys(plan) if loop else {}
                    for step in plan.steps:
                        eid = f"r{round_id}-{plan.plan_id}-{step.step_id}"
                        if loop:
                            loop.check_time()
                            key = keys[step.step_id]
                            if key in loop.attempted:
                                reused = loop.attempted[key]
                                trace.emit(
                                    "tool_reused",
                                    {
                                        "call_id": eid,
                                        "evidence_id": reused.evidence_id if reused else None,
                                        "previous_attempt_failed": reused is None,
                                    },
                                )
                                if reused is None:
                                    break
                                if reused.primary_artifact_id:
                                    refs[step.step_id] = reused.primary_artifact_id
                                continue
                            loop.attempted[key] = None
                        trace.emit(
                            "tool_started",
                            {
                                "call_id": eid,
                                "step": step.model_dump(),
                                "input_artifact_id": refs[step.input_ref],
                            },
                        )
                        try:
                            result = execute(step, refs[step.input_ref], eid, store)
                        except (ValueError, KeyError) as error:
                            trace.emit("tool_error", {"call_id": eid, "error": str(error)})
                            feedback.append({"plan_id": plan.plan_id, "error": str(error)})
                            break
                        evidence.append(result)
                        if loop:
                            loop.attempted[key] = result
                            round_record["new_evidence_ids"].append(result.evidence_id)
                            round_record["new_observations"] += int(loop.observe(result))
                        trace.emit("evidence", result.model_dump())
                        if result.primary_artifact_id:
                            refs[step.step_id] = result.primary_artifact_id
                if loop:
                    loop.record(round_record)
                    loop.require_progress(round_record["new_observations"])
                artifact_ids = ["original"] + [
                    a for e in evidence for a in e.artifact_ids if a.endswith(("-overlay", "-crop"))
                ][-6:]
                answer_context = {
                    "evidence": [e.model_dump() for e in evidence],
                    "feedback": feedback,
                    "image_artifact_ids": artifact_ids,
                }
                if loop:
                    answer_context.update(loop.context())
                answer = astra.answer(
                    question, [store.image_input(a) for a in artifact_ids], answer_context
                )
                # Image artifacts actually supplied to the model are valid evidence too.
                unknown = set(answer.evidence_ids) - (
                    {e.evidence_id for e in evidence} | set(artifact_ids)
                )
                if unknown:
                    raise ValueError(f"Answer cites unknown evidence IDs: {sorted(unknown)}")
                trace.emit("candidate_answer", answer.model_dump())
                if loop:
                    round_record["candidate_answer"] = answer.model_dump()
                    loop.record(round_record)
                if not needs_review or answer.status != "answered":
                    break
                review = jev.review(
                    {"question": question, "answer": answer.model_dump(), **answer_context}
                )
                trace.emit("answer_review", review.model_dump())
                review_feedback = loop.review_feedback(review) if loop else None
                if loop:
                    round_record["review_feedback"] = review_feedback
                    loop.record(round_record)
                    trace.emit("review_feedback", review_feedback)
                accepted = (
                    review_feedback["accepted"]
                    if loop
                    else review.support_probability >= settings.review.minimum_support_probability
                )
                if accepted:
                    if loop:
                        trace.emit(
                            "loop_stopped",
                            {
                                "reason": "All review checks and overall support met the threshold",
                                "accepted": True,
                                "round": round_id,
                            },
                        )
                    break
                feedback.append(
                    review_feedback
                    if loop
                    else {
                        "review": review.model_dump(),
                        "instruction": "Gather additional evidence or abstain; do not merely rewrite the claim.",
                    }
                )
                answer = abstain(
                    "Jev evidence review did not meet the configured support threshold", evidence
                )
                if frozen_plans:
                    break
            if loop and answer.status == "abstained":
                trace.emit(
                    "loop_stopped",
                    {
                        "reason": "Astra abstained, frozen plans ended, or round budget exhausted",
                        "accepted": False,
                        "round": round_id,
                    },
                )
        trace.emit("final_answer", answer.model_dump())
    except LoopStopped as stop:
        answer = abstain(str(stop), evidence)
        trace.emit("loop_stopped", {"reason": str(stop), "accepted": False})
        trace.emit("final_answer", answer.model_dump())
    except Exception as error:
        trace.emit("error", {"type": type(error).__name__, "message": str(error)})
        answer = Answer(
            status="error",
            value=None,
            explanation=str(error),
            evidence_ids=[],
            limitations=["Run did not complete successfully"],
        )
    write_json(directory / "answer.json", answer.model_dump())
    manifest.update(
        {
            "elapsed_seconds": time.monotonic() - start,
            "status": answer.status,
            "input_sha256": store.records.get("original", {}).get("source_sha256"),
        }
    )
    write_json(directory / "manifest.json", manifest)
    return directory
