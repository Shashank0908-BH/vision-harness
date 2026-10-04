"""Read-only verification; run from the repository root after report generation."""

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from harbor.utils.trajectory_validator import TrajectoryValidator

ROOT = Path("reports/bbbc039-adaptive-20260922")
JOBS = Path("jobs/bbbc039-adaptive-20260922")


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_map(directory, evidence, totals):
    m = evidence["measurements"]
    path = directory / m["raw_labels_path"]
    assert digest(path) == m["raw_labels_sha256"]
    labels = np.load(path)["labels"]
    ids = np.unique(labels)
    ids = ids[ids > 0]
    objects = read(directory / m["instances_path"])
    assert len(ids) == len(objects) == m["instance_count"]
    assert ids.tolist() == [o["id"] for o in objects]
    borders = 0
    for obj in objects:
        ys, xs = np.where(labels == obj["id"])
        assert obj["area_pixels"] == len(xs)
        assert np.allclose(obj["centroid"], [xs.mean(), ys.mean()])
        assert obj["box"] == [
            int(xs.min()),
            int(ys.min()),
            int(xs.max() - xs.min() + 1),
            int(ys.max() - ys.min() + 1),
        ]
        border = bool(
            xs.min() == 0
            or ys.min() == 0
            or xs.max() == labels.shape[1] - 1
            or ys.max() == labels.shape[0] - 1
        )
        assert obj["touches_border"] == border
        borders += border
    assert borders == m["border_instance_count"]
    totals["verified_instance_maps"] += 1
    totals["verified_instance_geometry"] += len(objects)
    return labels


def main():
    protocol, report = read(ROOT / "protocol.json"), read(ROOT / "results.json")
    dataset = Path(protocol["dataset_directory"])
    cohort = {r["id"]: r for r in report["cohort"]}
    totals = Counter()
    for name, expected in protocol["runtime_hashes"].items():
        assert digest(Path(name)) == expected
    assert digest(Path("evals/scoring.py")) == protocol["scoring_sha256"]
    assert (
        digest(Path("experiments/microscopy/harness_control.py"))
        == protocol["control_worker_sha256"]
    )
    for tid, task in cohort.items():
        bundle = Path("evals/tasks/generated/bbbc039-adaptive-20260922") / tid
        for name, expected in protocol["runtime_hashes"].items():
            assert digest(bundle / "environment/app" / name) == expected
        for name, expected in protocol["checkpoint_hashes"].items():
            assert digest(bundle / "environment/app/models/stardist" / name) == expected
        assert (
            digest(bundle / "environment/app/requirements-runtime.txt")
            == protocol["specialist_dependency_sha256"]
        )
        assert digest(bundle / "tests/score.py") == protocol["scoring_sha256"]
        assert digest(bundle / "environment/input.png") == task["sha256"]
        assert not list((bundle / "environment").rglob(".env"))
        labels_path = dataset / "annotations" / f"{tid}.npz"
        assert digest(labels_path) == task["annotation_labels_sha256"]
        labels = np.load(labels_path)["labels"]
        assert int(np.count_nonzero(np.unique(labels) > 0)) == task["expected"]
        totals["annotation_counts_reproduced"] += 1
    baseline_labels = {}
    diagnostic = read(ROOT / "fixed-sensitive-diagnostic.json")
    assert len(diagnostic["rows"]) == len(cohort)
    diagnostic_errors = []
    for row in diagnostic["rows"]:
        path = ROOT / row["source_events"]
        assert digest(path) == row["events_sha256"]
        events = [json.loads(s) for s in path.read_text().splitlines()]
        evidence = next(
            e["data"]
            for e in events
            if e["kind"] == "evidence" and e["data"]["evidence_id"] == row["evidence_id"]
        )
        assert evidence["parameters"]["segmentation_profile"] == "sensitive"
        assert evidence["input_artifact_id"] == "original"
        assert evidence["measurements"]["instance_count"] == row["count"]
        expected = cohort[row["task_id"]]["expected"]
        error = 100 * abs(row["count"] - expected) / expected
        assert error == row["metrics"]["percentage_error"]
        diagnostic_errors.append(error)
    assert np.isclose(np.mean(diagnostic_errors), diagnostic["mean_percentage_error"])
    totals["fixed_sensitive_diagnostic_counts_verified"] = len(diagnostic_errors)
    for row in report["standalone"]:
        baseline_labels[row["id"]] = check_map(
            ROOT / "standalone" / row["id"], row["evidence"], totals
        )
        error = (
            100 * abs(row["count"] - cohort[row["id"]]["expected"]) / cohort[row["id"]]["expected"]
        )
        assert error == row["metrics"]["percentage_error"]
    paths = list(JOBS.glob("*/*/result.json"))
    assert len(paths) == len(cohort) * len(protocol["modes"]) == 24
    rows = []
    for path in paths:
        result = read(path)
        directory = path.parent / "agent/run"
        manifest, answer = read(directory / "manifest.json"), read(directory / "answer.json")
        mode, tid = manifest["mode"], result["task_name"]
        assert not manifest["offline"] and manifest["config"] == protocol["effective_settings"]
        assert manifest["input_sha256"] == cohort[tid]["sha256"]
        validator = TrajectoryValidator()
        assert validator.validate(path.parent / "agent/trajectory.json"), validator.get_errors()
        totals["validated_trajectories"] += 1
        report_trial = next(
            t for t in report["trials"] if t["task_id"] == tid and t["mode"] == mode
        )
        reward = (result.get("verifier_result") or {}).get("rewards")
        if reward is not None:
            assert reward == report_trial["metrics"]
            if reward.get("valid_prediction"):
                assert (
                    reward["percentage_error"]
                    == 100
                    * abs(answer["value"] - cohort[tid]["expected"])
                    / cohort[tid]["expected"]
                )
            totals["matched_verifier_rewards"] += 1
        events = [json.loads(s) for s in (directory / "events.jsonl").read_text().splitlines()]
        assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
        counts = Counter(e["kind"] for e in events)
        totals["provider_calls_started"] += counts["call_started"]
        totals["provider_responses_recorded"] += counts["call_finished"]
        failed_checks, consumers, reviews, jev_calls, star_maps = None, set(), 0, 0, 0
        for event in events:
            d = event["data"]
            if event["kind"] == "review_feedback":
                expected_checks = set(
                    read(Path(protocol["effective_settings"]["loop"]["checks_path"]))
                )
                assert set(d["review"]["check_scores"]) == expected_checks
                scores = [d["review"]["support_probability"], *d["review"]["check_scores"].values()]
                assert d["accepted"] == all(s >= 0.75 for s in scores)
                if d["failed_checks"]:
                    failed_checks = d["failed_checks"]
            if event["kind"] == "answer_review":
                reviews += 1
            if event["kind"] == "call_started":
                request = read(directory / "calls" / (d["call_id"] + ".request.json"))
                assert request["model"] == protocol["effective_settings"]["models"][d["provider"]]
                if d["provider"] == "jev":
                    assert mode in {"select", "full"}
                    jev_calls += 1
                    totals["jev_" + d["operation"]] += 1
                else:
                    assert request["instructions"].startswith(
                        Path("prompts/astra-adaptive.md").read_text()
                    )
                if failed_checks and (
                    d["operation"].startswith("propose") or d["operation"] == "plan_assessment"
                ):
                    context = json.dumps(request.get("context", request.get("state", {})))
                    assert all(
                        c["check_id"] in context and c["remediation"] in context
                        for c in failed_checks
                    )
                    consumers.add(d["provider"])
            if event["kind"] == "evidence" and d["tool"] == "stardist":
                star_maps += 1
                labels = check_map(directory, d, totals)
                if (
                    d["input_artifact_id"] == "original"
                    and d["parameters"]["segmentation_profile"] == "default"
                ):
                    assert np.array_equal(labels, baseline_labels[tid])
                    totals["live_default_maps_identical_to_control"] += 1
        if mode == "vanilla":
            assert star_maps == 0 and jev_calls == 0 and reviews == 0
        if mode == "tools":
            assert jev_calls == 0 and reviews == 0
        if mode == "select":
            assert jev_calls >= 1 and reviews == 0
        if mode == "full":
            assert jev_calls >= 1
            if answer["status"] == "answered":
                review = report_trial["numerical_candidates"][-1]["review"]
                assert review["support_probability"] >= 0.75
                assert len(review["checks"]) == 4
                assert all(c["support_probability"] >= 0.75 for c in review["checks"])
                totals["accepted_full_answers_pass_all_conditions"] += 1
        rows.append(
            {
                "mode": mode,
                "task_id": tid,
                "status": answer["status"],
                "reviews": reviews,
                "jev_calls": jev_calls,
                "maps": star_maps,
                "feedback_consumers": sorted(consumers),
                "events_sha256": digest(directory / "events.jsonl"),
            }
        )
    load_dotenv(".env", override=True)
    secrets = [
        os.environ[k].encode()
        for k in ("OPENAI_API_KEY", "JEV_API_KEY", "TYPESAFE_API_KEY")
        if os.environ.get(k)
    ]
    for directory in (ROOT, JOBS):
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in {
                ".json",
                ".jsonl",
                ".md",
                ".html",
                ".log",
                ".toml",
            }:
                data = path.read_bytes()
                assert not any(s in data for s in secrets), "Credential found; do not publish"
    output = {
        "primary_trials": len(paths),
        "all_live": True,
        "modes_isolated": True,
        "frozen_sources_checkpoints_inputs_match": True,
        "keys_found": False,
        "counts": dict(totals),
        "trials": rows,
    }
    (ROOT / "verification.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({k: v for k, v in output.items() if k != "trials"}, indent=2))


if __name__ == "__main__":
    main()
