import json
from pathlib import Path

import pytest

from vision_harness.contracts import Answer, Assessment, Review
from vision_harness.demo import DemoAstra, DemoJev, demo_plans
from vision_harness.runtime import run
from vision_harness.selection import select
from vision_harness.tools.registry import Registry


@pytest.mark.parametrize("mode", ["vanilla", "tools", "select", "review", "full"])
def test_modes_and_component_isolation(mode, tmp_path, image_path, settings):
    class GuardJev(DemoJev):
        def __init__(self, *args):
            assert mode in ("select", "review", "full")
            super().__init__(*args)

        def assess(self, *args):
            assert mode in ("select", "full")
            return super().assess(*args)

        def review(self, *args):
            assert mode in ("review", "full")
            return super().review(*args)

    directory = run(
        image_path,
        "How many red objects?",
        settings,
        mode,
        output=tmp_path / mode,
        astra_factory=DemoAstra,
        jev_factory=GuardJev,
        offline=True,
    )
    answer = json.loads((directory / "answer.json").read_text())
    assert answer["status"] == ("abstained" if mode == "vanilla" else "answered")
    if mode != "vanilla":
        assert answer["value"] == 2
    events = (directory / "events.jsonl").read_text()
    if mode == "vanilla":
        assert "fixed_probes" not in events and "tool_started" not in events


def test_failed_reviews_stop_at_round_budget(tmp_path, image_path, settings):
    class RejectJev(DemoJev):
        def review(self, state):
            return Review(support_probability=0.1)

    directory = run(
        image_path,
        "Count red objects",
        settings,
        "full",
        output=tmp_path / "run",
        astra_factory=DemoAstra,
        jev_factory=RejectJev,
        offline=True,
    )
    events = [json.loads(s) for s in (directory / "events.jsonl").read_text().splitlines()]
    assert sum(e["kind"] == "plans" for e in events) == settings.limits.max_rounds
    assert json.loads((directory / "answer.json").read_text())["status"] == "abstained"


def test_provider_errors_saved_and_secrets_redacted(tmp_path, image_path, settings, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-sensitive-value")

    class BrokenAstra(DemoAstra):
        def answer(self, *args):
            raise RuntimeError("Failed using test-sensitive-value")

    directory = run(
        image_path, "Count", settings, "vanilla", output=tmp_path / "run", astra_factory=BrokenAstra
    )
    assert json.loads((directory / "answer.json").read_text())["status"] == "error"
    assert "test-sensitive-value" not in (directory / "events.jsonl").read_text()
    assert "test-sensitive-value" not in (directory / "answer.json").read_text()


def test_unknown_evidence_is_rejected(tmp_path, image_path, settings):
    class InventingAstra(DemoAstra):
        def answer(self, *args):
            return Answer(
                status="answered",
                value=2,
                explanation="Unsupported",
                evidence_ids=["imaginary"],
                limitations=[],
            )

    directory = run(
        image_path,
        "Count",
        settings,
        "tools",
        output=tmp_path / "run",
        astra_factory=InventingAstra,
    )
    assert json.loads((directory / "answer.json").read_text())["status"] == "error"


def test_close_scores_run_bounded_comparison(settings):
    registry = Registry(Path(settings.paths.capabilities))
    scores = [
        Assessment(plan_id=p, score=s, confidence=0.8, probabilities={"2": 0.8, "3": 0.2})
        for p, s in [("components", 2.2), ("watershed", 2.3)]
    ]
    chosen = select(demo_plans(), registry, 3, settings.selection, scores)
    assert chosen.selected_ids == ["watershed", "components"]
    scores[0].score = scores[1].score = 0.5
    assert not select(demo_plans(), registry, 3, settings.selection, scores).selected_ids


def test_frozen_plans_bypass_planner(tmp_path, image_path, settings):
    class NoPlan(DemoAstra):
        def plan(self, *args):
            raise AssertionError("Frozen comparison must not regenerate plans")

    directory = run(
        image_path,
        "Count red objects",
        settings,
        "select",
        output=tmp_path / "run",
        frozen_plans=demo_plans(),
        astra_factory=NoPlan,
        jev_factory=DemoJev,
    )
    assert json.loads((directory / "answer.json").read_text())["value"] == 2


@pytest.mark.parametrize("mode", ["vanilla", "tools"])
def test_supplied_original_image_is_valid_evidence(mode, tmp_path, image_path, settings):
    class ImageCitingAstra(DemoAstra):
        def answer(self, *args):
            return Answer(
                status="answered",
                value=2,
                explanation="Visible in supplied image",
                evidence_ids=["original"],
                limitations=[],
            )

    directory = run(
        image_path, "Count", settings, mode, output=tmp_path / "run", astra_factory=ImageCitingAstra
    )
    assert json.loads((directory / "answer.json").read_text())["status"] == "answered"
