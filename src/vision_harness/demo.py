"""Deterministic stand-ins for plumbing demonstrations, NEVER model-quality evidence."""

import json
from pathlib import Path

from .contracts import (
    Answer,
    Arguments,
    Assessment,
    CandidatePlan,
    PlanSet,
    Review,
    ReviewCheck,
    Step,
)


def demo_plans(color="red") -> PlanSet:
    arguments = dict(
        color=color,
        min_area=10,
        saturation_min=80,
        value_min=40,
        marker_fraction=None,
        box=None,
        points=None,
    )
    return PlanSet(
        observations=["OFFLINE fixture: no model inspected the image"],
        candidates=[
            CandidatePlan(
                plan_id="components",
                description="Count separated colored components",
                assumptions=["Each object corresponds to a separated mask component"],
                intended_output="count",
                steps=[
                    Step(
                        step_id="count",
                        tool="components",
                        input_ref="original",
                        arguments=Arguments(**arguments),
                    )
                ],
            ),
            CandidatePlan(
                plan_id="watershed",
                description="Split touching colored regions",
                assumptions=["Distance peaks identify instances"],
                intended_output="count",
                steps=[
                    Step(
                        step_id="split",
                        tool="watershed",
                        input_ref="original",
                        arguments=Arguments(**{**arguments, "marker_fraction": 0.5}),
                    )
                ],
            ),
        ],
        preferred_id="components",
    )


class DemoAstra:
    def __init__(self, settings, trace):
        self.trace = trace

    def plan(self, question, images, context):
        color = next((c for c in ("red", "green", "blue") if c in question.lower()), "any")
        return demo_plans(color)

    def answer(self, question, images, context):
        candidates = [e for e in context["evidence"] if "component_count" in e["measurements"]]
        if candidates and ("how many" in question.lower() or "count" in question.lower()):
            item = candidates[-1]
            return Answer(
                status="answered",
                value=item["measurements"]["component_count"],
                explanation="OFFLINE fixture copied the measured component count.",
                evidence_ids=[item["evidence_id"]],
                limitations=["No actual Astra inference; not a model-quality result."],
            )
        return Answer(
            status="abstained",
            value=None,
            explanation="Offline fixture cannot answer this task without component evidence.",
            evidence_ids=[],
            limitations=["No actual Astra inference."],
        )


class DemoJev:
    def __init__(self, settings, trace):
        self.trace = trace
        self.checks = (
            json.loads(Path(settings.loop.checks_path).read_text()) if settings.loop.enabled else {}
        )

    def assess(self, state, candidates):
        return [
            Assessment(
                plan_id=p.plan_id,
                score=3 if p.plan_id == "components" else 2,
                confidence=1,
                probabilities={
                    str(i): float(i == (3 if p.plan_id == "components" else 2)) for i in range(4)
                },
            )
            for p in candidates
        ]

    def review(self, state):
        return Review(
            support_probability=0.99,
            checks=[
                ReviewCheck(
                    check_id=k,
                    support_probability=0.99,
                    requirement=v["instructions"],
                    remediation=v["remediation"],
                )
                for k, v in self.checks.items()
            ],
        )
