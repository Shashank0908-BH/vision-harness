"""Bounded review feedback, operation reuse and observable evidence novelty.

No model calls or ground-truth access. A new observation is not proof of correctness.
"""

import hashlib
import json
import time
from pathlib import Path

from .contracts import CandidatePlan, Evidence, Review


class LoopStopped(Exception):
    """An intentional stopping condition, not an infrastructure error."""


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def operation_keys(plan: CandidatePlan) -> dict[str, str]:
    """Normalize names and known inactive parameters, preserving dependency graphs."""
    refs = {"original": "original"}
    keys = {}
    for step in plan.steps:
        args = step.arguments.model_dump(exclude_none=True)
        if step.tool in ("components", "watershed") and args.get("color") == "any":
            # This matches the current OpenCV implementation, not a new image operation.
            args.pop("value_min", None)
        key = digest({"tool": step.tool, "input": refs[step.input_ref], "arguments": args})
        keys[step.step_id] = key
        refs[step.step_id] = key
    return keys


class ReviewLoop:
    def __init__(self, settings, trace, store, clock=time.monotonic):
        self.settings, self.trace, self.store, self.clock = settings, trace, store, clock
        self.started = clock()
        self.calls = 0
        self.history = []
        self.attempted: dict[str, Evidence | None] = {}
        self.observations = set()
        self.no_progress_rounds = 0
        self.check_ids = set(json.loads(Path(settings.loop.checks_path).read_text()))

    def check_time(self):
        if self.clock() - self.started >= self.settings.loop.max_seconds:
            raise LoopStopped("Time budget reached; no further calls or tools will start")

    def before_call(self):
        self.check_time()
        if self.calls >= self.settings.loop.max_provider_calls:
            raise LoopStopped("Provider call budget reached (including format retries)")
        self.calls += 1

    def context(self):
        return {
            "round_history": self.history,
            "provider_calls_remaining": self.settings.loop.max_provider_calls - self.calls,
            "seconds_remaining": max(
                0, self.settings.loop.max_seconds - (self.clock() - self.started)
            ),
            "instruction": "Address the failed checks using additional measured evidence. Prior scores are feedback, not proof. Avoid repeated operations, ignored parameter changes and explanations without new observations. State inability to resolve a gap when the available capabilities cannot do so.",
        }

    def repeated(self, plan):
        return all(key in self.attempted for key in operation_keys(plan).values())

    def observe(self, evidence: Evidence) -> bool:
        # Exclude method names, IDs and parameters: changing these alone is not progress.
        primary = self.store.records.get(evidence.primary_artifact_id, {})
        source = self.store.records[evidence.input_artifact_id]
        key = digest(
            {
                "input": source["sha256"],
                "input_origin": source["origin"],
                "measurements": evidence.measurements,
                "output": primary.get("sha256"),
                "output_origin": primary.get("origin"),
                "status": evidence.status,
            }
        )
        if key in self.observations:
            return False
        self.observations.add(key)
        return True

    def review_feedback(self, review: Review):
        ids = [c.check_id for c in review.checks]
        if set(ids) != self.check_ids or len(ids) != len(self.check_ids):
            raise ValueError("Structured review must return every configured check exactly once")
        threshold = self.settings.review.minimum_support_probability
        # Keep numeric results and actionable gaps in context without repeating full
        # rubric text in every history entry. The complete review stays in the trace.
        failed = [
            {
                "check_id": c.check_id,
                "support_probability": c.support_probability,
                "remediation": c.remediation,
            }
            for c in review.checks
            if c.support_probability < threshold
        ]
        accepted = review.support_probability >= threshold and not failed
        return {
            "review": {
                "support_probability": review.support_probability,
                "check_scores": {c.check_id: c.support_probability for c in review.checks},
            },
            "acceptance_threshold": threshold,
            "failed_checks": failed,
            "accepted": accepted,
            "instruction": "Resolve the failed checks with new measured evidence; do not optimize wording for approval.",
        }

    def record(self, record: dict):
        if self.history and self.history[-1]["round"] == record["round"]:
            self.history[-1] = record
        else:
            self.history.append(record)
        from .tracing import write_json

        write_json(self.trace.directory / "loop-history.json", self.history)
        self.trace.emit("loop_round", record)

    def require_progress(self, count: int):
        self.no_progress_rounds = 0 if count else self.no_progress_rounds + 1
        if self.no_progress_rounds >= self.settings.loop.max_no_progress_rounds:
            raise LoopStopped(
                "No new tool observations; another review would only rescore existing evidence"
            )
