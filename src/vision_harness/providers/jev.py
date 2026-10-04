"""TypeSafe HTTP adapter. Preserves scores, distributions and Noul separately."""

import hashlib
import json
import math
import time
from pathlib import Path
from typing import Protocol, Sequence

import httpx

from ..config import Settings, require_key
from ..contracts import Assessment, Review, ReviewCheck
from ..tracing import Trace, redact, write_json
from .evidence_budget import bounded_request


class Scorable(Protocol):
    plan_id: str

    def model_dump_json(self) -> str: ...


class Jev:
    def __init__(self, settings: Settings, trace: Trace, client=None):
        self.settings, self.trace = settings, trace
        self.client = client or httpx.Client(timeout=settings.models.timeout_seconds)
        self.plan_rubric = json.loads(Path(settings.paths.plan_rubric).read_text())
        self.review_rubric = json.loads(Path(settings.paths.review_rubric).read_text())
        self.review_checks = (
            json.loads(Path(settings.loop.checks_path).read_text()) if settings.loop.enabled else {}
        )
        if settings.loop.enabled and (
            len(self.review_checks) != 4 or "support" in self.review_checks
        ):
            raise ValueError("Structured review requires four distinct checks besides support")
        if len(self.plan_rubric["criteria"]) != 4:
            raise ValueError("v1 selection thresholds use a four-level rubric (0..3)")

    def _request(self, operation: str, state: dict, questions: dict) -> dict:
        request = {"model": self.settings.models.jev, "state": state, "questions": questions}
        original = request
        request, projection = bounded_request(request, self.settings.limits.jev_max_request_bytes)
        if projection:
            digest = hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest()
            relative = f"evidence/jev-source-{digest}.json"
            write_json(self.trace.directory / relative, original)
            self.trace.emit(
                "evidence_compacted",
                {**projection, "full_request_artifact": relative, "source_sha256": digest},
            )
        call_id = self.trace.call("jev", operation, request)
        start = time.monotonic()
        response = self.client.post(
            "https://api.typesafe.ai/v1/systemone",
            json=request,
            headers={"Authorization": f"Bearer {require_key('TYPESAFE_API_KEY')}"},
        )
        try:
            data = response.json()
        except ValueError:
            data = {"non_json_body": response.text}
        self.trace.response(
            call_id, {**data, "http_status": response.status_code}, time.monotonic() - start
        )
        if response.is_error:
            detail = json.dumps(redact(data))[:1500]
            raise httpx.HTTPStatusError(
                f"Jev HTTP {response.status_code}: {detail}",
                request=response.request,
                response=response,
            )
        if set(data.get("answers", {})) != set(questions):
            raise ValueError("Jev response question IDs do not match the request")
        return data["answers"]

    def assess(self, state: dict, candidates: Sequence[Scorable]) -> list[Assessment]:
        if not candidates:
            return []
        questions = {}
        loop_instruction = (
            " Use round_history and feedback: assess whether this plan addresses previously failed review checks with additional measurable evidence. Penalize repeating failed assumptions or changing parameters without an effective measurement change. A prior low review score identifies unresolved support, not proof that its count was wrong. A plan need not resolve every gap alone, but must make concrete progress on an unresolved requirement."
            if self.settings.loop.enabled
            else ""
        )
        for candidate in candidates:
            questions[candidate.plan_id] = {
                "type": "score",
                "instructions": self.plan_rubric["instructions"]
                + loop_instruction
                + f" Evaluate exactly this candidate: {candidate.model_dump_json()}",
                "criteria": self.plan_rubric["criteria"],
            }
        answers = self._request("plan_assessment", state, questions)
        results = []
        for candidate in candidates:
            raw = answers[candidate.plan_id]
            if raw.get("type") != "score":
                raise ValueError("Expected a Score answer from Jev")
            probabilities = raw["probabilities"]
            if set(probabilities) != {"0", "1", "2", "3"} or any(
                not 0 <= p <= 1 for p in probabilities.values()
            ):
                raise ValueError("Invalid Jev score distribution")
            if not math.isclose(sum(probabilities.values()), 1, abs_tol=0.01):
                raise ValueError("Jev score probabilities must sum to one")
            results.append(
                Assessment(
                    plan_id=candidate.plan_id,
                    score=raw["score"],
                    confidence=raw["confidence"],
                    probabilities=probabilities,
                )
            )
        return results

    def review(self, state: dict) -> Review:
        questions = {"support": {"type": "noul", **self.review_rubric}}
        for key, check in self.review_checks.items():
            questions[key] = {
                "type": "noul",
                "instructions": check["instructions"],
                "criteria": check["criteria"],
            }
        answers = self._request("answer_review", state, questions)
        if any(a.get("type") != "noul" for a in answers.values()):
            raise ValueError("Expected a Noul answer from Jev")
        return Review(
            support_probability=answers["support"]["noul"],
            checks=[
                ReviewCheck(
                    check_id=key,
                    support_probability=answers[key]["noul"],
                    requirement=check["instructions"],
                    remediation=check["remediation"],
                )
                for key, check in self.review_checks.items()
            ],
        )
