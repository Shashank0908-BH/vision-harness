import copy
import json

import httpx
import pytest

from vision_harness.artifacts import ArtifactStore
from vision_harness.contracts import Arguments, Step
from vision_harness.demo import DemoAstra, DemoJev, demo_plans
from vision_harness.providers.jev import Jev
from vision_harness.review_loop import LoopStopped, ReviewLoop, operation_keys
from vision_harness.runtime import run
from vision_harness.tracing import Trace


def events(directory):
    return [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]


def crop():
    return Step(
        step_id="region",
        tool="crop",
        input_ref="original",
        arguments=Arguments(
            color=None,
            min_area=None,
            saturation_min=None,
            value_min=None,
            marker_fraction=None,
            box=[0, 0, 100, 100],
            points=None,
        ),
    )


def test_failed_checks_reach_planner_and_selector_and_new_evidence_can_pass(
    settings, tmp_path, image_path
):
    settings.loop.enabled = True
    planner_states, selector_states = [], []

    class Planner(DemoAstra):
        def plan(self, question, images, context):
            planner_states.append(copy.deepcopy(context))
            plans = demo_plans("red")
            plans.candidates = [plans.candidates[0]]
            if context["round"] == 2:
                # Reuse the first operation, then acquire genuinely different input evidence.
                p = plans.candidates[0]
                last = p.steps[0].model_copy(deep=True)
                last.step_id, last.input_ref = "cropped_count", "region"
                p.steps += [crop(), last]
            return plans

    class Reviewer(DemoJev):
        def assess(self, state, candidates):
            selector_states.append(copy.deepcopy(state))
            return super().assess(state, candidates)

        def review(self, state):
            review = super().review(state)
            if len(state["round_history"]) == 1:
                # Overall support is high; one failed check must still force replanning.
                review.checks[0].support_probability = 0.1
            return review

    directory = run(
        image_path,
        "Count red objects",
        settings,
        "full",
        output=tmp_path / "run",
        astra_factory=Planner,
        jev_factory=Reviewer,
        offline=True,
    )
    es = events(directory)
    assert json.loads((directory / "answer.json").read_text())["status"] == "answered"
    assert len(planner_states) == len(selector_states) == 2
    for state in (planner_states[1], selector_states[1]):
        assert state["feedback"][0]["accepted"] is False
        assert state["feedback"][0]["failed_checks"][0]["check_id"] == "method_validity"
        assert state["round_history"][0]["candidate_answer"]["value"] == 2
        assert state["round_history"][0]["selection"]["selected_ids"] == ["components"]
    assert sum(e["kind"] == "tool_reused" for e in es) == 1
    assert sum(e["kind"] == "tool_started" for e in es) == 3
    assert len(json.loads((directory / "loop-history.json").read_text())) == 2
    from evals.atif import export

    trajectory = export(directory, directory / "trajectory.json")
    assert any(s.extra.get("event_kind") == "review_feedback" for s in trajectory.steps)


def test_identical_observations_stop_before_rescoring(settings, tmp_path, image_path):
    settings.loop.enabled = True
    settings.limits.max_rounds = 4

    class Planner(DemoAstra):
        def plan(self, question, images, context):
            p = demo_plans("red")
            p.candidates = [p.candidates[0]]
            # A real parameter change, but it leaves the measured components unchanged.
            p.candidates[0].steps[0].arguments.min_area = 10 + context["round"]
            return p

    class Reject(DemoJev):
        def review(self, state):
            r = super().review(state)
            r.support_probability = 0.1
            return r

    directory = run(
        image_path,
        "Count red objects",
        settings,
        "full",
        output=tmp_path / "run",
        astra_factory=Planner,
        jev_factory=Reject,
        offline=True,
    )
    es = events(directory)
    assert sum(e["kind"] == "candidate_answer" for e in es) == 1
    assert sum(e["kind"] == "answer_review" for e in es) == 1
    answer = json.loads((directory / "answer.json").read_text())
    assert answer["status"] == "abstained" and "No new tool observations" in answer["explanation"]


def test_repeated_plans_ignore_renaming_and_inactive_parameters(settings, tmp_path, image_path):
    original = demo_plans("any").candidates[0]
    renamed = original.model_copy(deep=True)
    renamed.plan_id = "new_name"
    renamed.steps[0].step_id = "new_step"
    renamed.steps[0].arguments.value_min = 199
    assert list(operation_keys(original).values()) == list(operation_keys(renamed).values())
    renamed.steps[0].arguments.saturation_min = 40
    assert list(operation_keys(original).values()) != list(operation_keys(renamed).values())
    settings.loop.enabled = True

    class Reject(DemoJev):
        def review(self, state):
            r = super().review(state)
            r.support_probability = 0.1
            return r

    directory = run(
        image_path,
        "Count red objects",
        settings,
        "full",
        output=tmp_path / "run",
        astra_factory=DemoAstra,
        jev_factory=Reject,
        offline=True,
    )
    # First round selects components; second excludes it and can select watershed.
    selections = [e["data"] for e in events(directory) if e["kind"] == "selection"]
    assert "components" in selections[1]["rejected"]


def test_call_and_time_budgets_prevent_new_requests(settings, tmp_path):
    settings.loop.max_provider_calls = 1
    trace = Trace(tmp_path)
    now = [0.0]
    loop = ReviewLoop(settings, trace, ArtifactStore(tmp_path), clock=lambda: now[0])
    trace.before_call = loop.before_call
    trace.call("astra", "first", {})
    with pytest.raises(LoopStopped, match="call budget"):
        trace.call("astra", "format retry", {})
    assert len(list((tmp_path / "calls").glob("*.request.json"))) == 1
    now[0] = settings.loop.max_seconds
    with pytest.raises(LoopStopped, match="Time budget"):
        loop.check_time()


def test_exhausted_call_budget_is_an_abstention_not_an_execution_error(
    settings, tmp_path, image_path
):
    settings.loop.enabled = True
    settings.loop.max_provider_calls = 1

    class ChargedAstra(DemoAstra):
        def plan(self, *args):
            self.trace.call("astra", "fixture planning", {})
            return super().plan(*args)

        def answer(self, *args):
            self.trace.call("astra", "fixture answering", {})
            raise AssertionError("The second call must not start")

    directory = run(
        image_path,
        "Count red objects",
        settings,
        "full",
        output=tmp_path / "run",
        astra_factory=ChargedAstra,
        jev_factory=DemoJev,
        offline=True,
    )
    answer = json.loads((directory / "answer.json").read_text())
    assert answer["status"] == "abstained"
    assert "call budget" in answer["explanation"]
    assert not any(e["kind"] == "error" for e in events(directory))


@pytest.mark.parametrize("missing", [False, True])
def test_structured_jev_wire_format_and_missing_checks(settings, tmp_path, monkeypatch, missing):
    settings.loop.enabled = True
    monkeypatch.setenv("JEV_API_KEY", "fixture-key")

    def respond(request):
        data = json.loads(request.content)
        assert set(data["questions"]) == {
            "support",
            "method_validity",
            "coverage",
            "target_validity",
            "answer_grounding",
        }
        assert all(
            q["type"] == "noul" and "remediation" not in q for q in data["questions"].values()
        )
        answers = {k: {"type": "noul", "noul": 0.9} for k in data["questions"]}
        if missing:
            del answers["coverage"]
        return httpx.Response(200, json={"answers": answers})

    provider = Jev(
        settings, Trace(tmp_path), client=httpx.Client(transport=httpx.MockTransport(respond))
    )
    if missing:
        with pytest.raises(ValueError, match="question IDs"):
            provider.review({"evidence": []})
    else:
        review = provider.review({"evidence": []})
        assert len(review.checks) == 4
        assert all(c.remediation for c in review.checks)
