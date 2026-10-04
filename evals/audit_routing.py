"""Recompute measurements and inspect decision/trace ordering after the run."""

import json
import statistics
from datetime import datetime

import cv2
import numpy as np
from harbor.utils.trajectory_validator import TrajectoryValidator

from evals.routing import REPORT, RUNS
from vision_harness.routing.catalog import sha256
from vision_harness.tracing import write_json


def audit():
    results = json.loads((REPORT / "results.json").read_text())
    selection = json.loads((REPORT / "selection.json").read_text())
    expected_ids = set(selection["procedure_ids"])
    maps = objects = calls = traces = 0
    route_seconds, vanilla_seconds, review_values = [], [], []
    worker_seconds = {p: [] for p in expected_ids}
    native_seconds = {p: [] for p in expected_ids}
    score_rows = []
    for row in results["rows"]:
        route = RUNS / row["id"] / "routing"
        manifest = json.loads((route / "manifest.json").read_text())
        assert manifest["source_sha256"] == selection["source_sha256"]
        assert manifest["catalog_sha256"] == selection["catalog_sha256"]
        original = cv2.imread(str(route / "artifacts/original.png"))
        decoded_input = cv2.imread(row["image"])
        assert np.array_equal(original, decoded_input)
        decision = json.loads((route / "decision.json").read_text())
        assert len(decision["assessments"]) == 4
        assert {s["plan_id"] for s in decision["assessments"]} == expected_ids
        assert decision["jev_ranking"] == [s["plan_id"] for s in sorted(decision["assessments"], key=lambda s: (-s["score"], s["plan_id"]))]
        assert sha256(route / "decision.json") == row["harness"]["decision_sha256"]
        events = [json.loads(x) for x in (route / "events.jsonl").read_text().splitlines()]
        frozen = next(e for e in events if e["kind"] == "routing_decision")
        executions = [e for e in events if e["kind"] == "tool_started"]
        final = next(e for e in events if e["kind"] == "final_answer")
        assert len(executions) == 4
        assert frozen["sequence"] < min(e["sequence"] for e in executions)
        assert executions[0]["data"]["call_id"] == decision["selected_id"]
        assert all(e["sequence"] > final["sequence"] for e in executions[1:])
        route_seconds.append((datetime.fromisoformat(final["time"]) - datetime.fromisoformat(events[0]["time"])).total_seconds())
        for pid in expected_ids:
            output = route / "specialists" / pid
            evidence = json.loads((output / "evidence.json").read_text())
            with np.load(output / "labels.npz", allow_pickle=False) as data:
                labels = data["labels"]
            geometry = json.loads((output / "instances.json").read_text())
            ids = [int(i) for i in np.unique(labels) if i > 0]
            assert labels.shape == original.shape[:2] and labels.dtype.kind in "iu"
            assert len(ids) == evidence["count"] == row["procedure_counts"][pid] == len(geometry)
            assert set(ids) == {o["id"] for o in geometry}
            assert evidence["worker"]["labels_sha256"] == sha256(output / "labels.npz")
            for obj in geometry:
                ys, xs = np.where(labels == obj["id"])
                assert obj["area_pixels"] == len(xs)
                assert np.allclose(obj["centroid_xy"], [xs.mean(), ys.mean()])
                assert obj["box_xywh"] == [int(xs.min()), int(ys.min()), int(xs.max()-xs.min()+1), int(ys.max()-ys.min()+1)]
                assert obj["touches_border"] == bool(xs.min() == 0 or ys.min() == 0 or xs.max() == labels.shape[1]-1 or ys.max() == labels.shape[0]-1)
                objects += 1
            maps += 1
            worker_seconds[pid].append(evidence["elapsed_seconds"])
            native_seconds[pid].append(evidence["worker"]["inference_seconds"])
        assert row["harness"]["value"] == row["procedure_counts"][decision["selected_id"]]
        review_values.append(row["harness"]["review_support"])
        score_rows.append({"id": row["id"], "scores": {s["plan_id"]: s["score"] for s in decision["assessments"]}})
        for arm in ("routing", "vanilla"):
            directory = RUNS / row["id"] / arm
            assert np.array_equal(original, cv2.imread(str(directory / "artifacts/original.png")))
            validator = TrajectoryValidator()
            assert validator.validate(directory / "trajectory.json"), validator.get_errors()
            traces += 1
            events_arm = [json.loads(x) for x in (directory / "events.jsonl").read_text().splitlines()]
            starts = {e["data"]["call_id"] for e in events_arm if e["kind"] == "call_started"}
            finishes = {e["data"]["call_id"] for e in events_arm if e["kind"] == "call_finished"}
            assert starts == finishes
            calls += len(finishes)
            if arm == "vanilla":
                vanilla_seconds.append(json.loads((directory / "manifest.json").read_text())["elapsed_seconds"])
    summary = {
        "instance_maps_recomputed": maps, "instance_geometry_records_checked": objects,
        "valid_harbor_trajectories": traces, "completed_provider_calls": calls,
        "all_scores_frozen_before_inference": True, "comparison_withheld_from_answer": True,
        "source_and_catalog_match_frozen_protocol": True,
        "mean_input_to_final_answer_seconds": statistics.mean(route_seconds),
        "mean_vanilla_elapsed_seconds": statistics.mean(vanilla_seconds),
        "mean_worker_seconds_including_startup_and_artifacts": {k: statistics.mean(v) for k, v in worker_seconds.items()},
        "mean_native_inference_seconds": {k: statistics.mean(v) for k, v in native_seconds.items()},
        "review_support_values": review_values, "jev_scores_by_task": score_rows,
    }
    write_json(REPORT / "audit.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    audit()
