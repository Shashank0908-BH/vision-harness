import json
import tomllib

import pytest

from evals.generate_dataset import generate
from evals.scoring import score


def test_verifier_tolerance_and_failure_categories():
    assert (
        score({"status": "answered", "value": 9.1}, {"expected": 10, "tolerance": 1})["accuracy"]
        == 1
    )
    assert score({"status": "answered", "value": float("nan")}, {"expected": 10})["accuracy"] == 0
    assert score({"status": "answered", "value": True}, {"expected": 1})["accuracy"] == 0
    assert score({"status": "abstained", "value": 10}, {"expected": 10})["abstained"] == 1
    assert score({}, {"expected": 10})["error"] == 1


def test_published_count_error_and_missing_predictions():
    target = {"expected": 356, "metric": "bbbc001_percentage_error"}
    result = score({"status": "answered", "value": 320}, target)
    assert result["absolute_count_error"] == 36
    assert result["percentage_error"] == pytest.approx(100 * 36 / 356)
    # Invalid/missing answers must never improve the mean by becoming zero error.
    for value in (None, True, -1, float("nan"), float("inf"), "356"):
        result = score({"status": "answered", "value": value}, target)
        assert result["valid_prediction"] == 0
        assert "percentage_error" not in result
    assert "percentage_error" not in score({"status": "abstained", "value": 356}, target)


def test_benchmark_aggregate_requires_every_image():
    from evals.benchmark_report import summarize

    def trial(value, status="answered"):
        answer = {"status": status, "value": value}
        return {
            "mode": "vanilla",
            "answer": answer,
            "metrics": score(answer, {"expected": 100, "metric": "bbbc001_percentage_error"}),
            "infrastructure_error": None,
            "elapsed_seconds": 1,
            "tokens": {
                p: dict(input=0, output=0, started_calls=0, calls=0) for p in ("astra", "jev")
            },
        }

    complete = summarize([trial(90), trial(80)])
    assert complete["benchmark_percentage_error"] == 15
    partial = summarize([trial(90), trial(None, "abstained")])
    assert partial["benchmark_percentage_error"] is None
    assert partial["answered_subset_percentage_error"] == 10
    assert partial["coverage"] == 1


def test_candidate_report_keeps_missing_predictions_out_of_full_metric():
    from evals.candidate_report import aggregate

    rows = [
        {
            "numerical_candidates": [{"percentage_error": 5}, {"percentage_error": 20}],
            "vanilla_percentage_error": 10,
        },
        {"numerical_candidates": [], "vanilla_percentage_error": 30},
    ]
    result = aggregate(rows, -1)
    assert result["mean_percentage_error"] is None
    assert result["coverage"] == 1
    assert result["answered_subset_percentage_error"] == 20
    assert result["matched_vanilla_subset_error"] == 10
    assert result["worse_than_vanilla"] == 1


def test_dataset_determinism_and_split_separation(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generate(a, 5, 5, 42)
    generate(b, 5, 5, 42)
    assert (a / "manifest.jsonl").read_bytes() == (b / "manifest.jsonl").read_bytes()
    rows = [json.loads(x) for x in (a / "manifest.jsonl").read_text().splitlines()]
    assert len({r["sha256"] for r in rows}) == 10
    for row in rows:
        assert (a / row["image"]).read_bytes() == (b / row["image"]).read_bytes()


def test_harbor_task_isolation_and_schema(tmp_path):
    pytest.importorskip("harbor")
    from harbor.models.task.config import TaskConfig

    from evals.build_tasks import build

    generate(tmp_path / "data", 1, 0, 42)
    build(tmp_path / "data", tmp_path / "tasks")
    task = next((tmp_path / "tasks").iterdir())
    TaskConfig.model_validate(tomllib.loads((task / "task.toml").read_text()))
    assert (task / "tests/expected.json").is_file()
    assert not list((task / "environment").rglob("expected.json"))
    assert not list((task / "environment").rglob(".env"))
    assert not list((task / "environment").rglob("manifest.jsonl"))


def test_atif_export_is_valid_and_contains_tool_observations(tmp_path, image_path, settings):
    pytest.importorskip("harbor")
    from evals.atif import export
    from vision_harness.demo import DemoAstra, DemoJev
    from vision_harness.runtime import run

    directory = run(
        image_path,
        "Count red shapes",
        settings,
        "full",
        output=tmp_path / "run",
        astra_factory=DemoAstra,
        jev_factory=DemoJev,
        offline=True,
    )
    trajectory = export(directory, directory / "trajectory.json")
    assert trajectory.extra["offline"]
    assert any(s.tool_calls and s.observation for s in trajectory.steps)
