"""Read-only audit of this frozen experiment; run from the repository root."""

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from harbor.utils.trajectory_validator import TrajectoryValidator

ROOT = Path("reports/bbbc001-stardist-20260922")
PRIMARY = Path("jobs/bbbc001-stardist-20260922")
RECOVERY = Path("jobs/bbbc001-stardist-recovery-20260922")


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = read(ROOT / "protocol.json")
    cohort = {t["id"]: t for t in read(ROOT / "cohort.json")}
    for name, expected in protocol["runtime_hashes"].items():
        assert digest(Path(name)) == expected, name
    bundles = Path("evals/tasks/generated/bbbc001-stardist-20260922")
    for task_id, task in cohort.items():
        environment = bundles / task_id / "environment"
        assert digest(environment / "input.png") == task["sha256"]
        assert not list(environment.rglob(".env"))
        for name, expected in protocol["runtime_hashes"].items():
            assert digest(environment / "app" / name) == expected, (task_id, name)
        for name, expected in protocol["checkpoint_hashes"].items():
            assert digest(environment / "app" / name) == expected
        assert (
            digest(environment / "app/requirements-runtime.txt")
            == protocol["specialist_dependency_sha256"]
        )

    recovery_ids = read(ROOT / "recovery-tasks.json")["task_ids"]
    for task_id in recovery_ids:
        original = bundles / task_id
        copied = Path("evals/tasks/generated/bbbc001-stardist-recovery-20260922") / task_id
        assert sorted(
            p.relative_to(original) for p in original.rglob("*") if p.is_file()
        ) == sorted(p.relative_to(copied) for p in copied.rglob("*") if p.is_file())
        for path in original.rglob("*"):
            if not path.is_file():
                continue
            other = copied / path.relative_to(original)
            if path.relative_to(original).as_posix() == "environment/app/configs/poc-stardist.toml":
                assert other.read_text() == path.read_text().replace(
                    "timeout_seconds = 120", "timeout_seconds = 300"
                )
            else:
                assert digest(path) == digest(other)

    totals = Counter()
    rows = []
    result_paths = sorted(PRIMARY.glob("*/*/result.json"))
    recovered = sorted(RECOVERY.glob("*/*/result.json"))
    assert len(result_paths) == 18 and len(recovered) == len(recovery_ids)
    for path in result_paths + recovered:
        result = read(path)
        directory = path.parent / "agent/run"
        manifest = read(directory / "manifest.json")
        answer = read(directory / "answer.json")
        task = cohort[result["task_name"]]
        assert not manifest["offline"]
        assert manifest["input_sha256"] == task["sha256"]
        assert manifest["question"].strip() == task["question"]
        validator = TrajectoryValidator()
        assert validator.validate(path.parent / "agent/trajectory.json"), validator.get_errors()
        totals["validated_trajectories"] += 1
        rewards = (result.get("verifier_result") or {}).get("rewards")
        if rewards is not None:
            # Imported here so direct script invocation also works.
            import sys

            sys.path.insert(0, str(Path.cwd()))
            from evals.scoring import score

            assert rewards == score(answer, task)
            totals["matched_verifier_rewards"] += 1
        events = [json.loads(s) for s in (directory / "events.jsonl").read_text().splitlines()]
        assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
        counts = Counter(e["kind"] for e in events)
        totals["provider_calls_started"] += counts["call_started"]
        totals["provider_responses_recorded"] += counts["call_finished"]
        mode = manifest["mode"]
        failed_checks = None
        feedback_consumers = set()
        star_outputs = 0
        for event in events:
            d = event["data"]
            if event["kind"] == "review_feedback" and d["failed_checks"]:
                failed_checks = d["failed_checks"]
            if event["kind"] == "call_started":
                request = read(directory / "calls" / (d["call_id"] + ".request.json"))
                assert request["model"] == protocol["effective_settings"]["models"][d["provider"]]
                totals[d["provider"] + "_calls"] += 1
                if d["provider"] == "jev":
                    assert mode == "full"
                    totals["jev_" + d["operation"]] += 1
                context = request.get("context", request.get("state", {}))
                if failed_checks and (
                    d["operation"].startswith("propose") or d["operation"] == "plan_assessment"
                ):
                    serialized = json.dumps(context)
                    assert all(
                        c["check_id"] in serialized and c["remediation"] in serialized
                        for c in failed_checks
                    )
                    feedback_consumers.add(d["provider"])
            if event["kind"] != "evidence" or d["tool"] != "stardist":
                continue
            assert mode in {"tools", "full"}
            star_outputs += 1
            measurements = d["measurements"]
            labels_path = directory / measurements["raw_labels_path"]
            assert digest(labels_path) == measurements["raw_labels_sha256"]
            labels = np.load(labels_path)["labels"]
            ids = np.unique(labels)
            ids = ids[ids > 0]
            assert len(ids) == measurements["instance_count"]
            objects = read(directory / measurements["instances_path"])
            assert [o["id"] for o in objects] == ids.tolist()
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
                assert border == obj["touches_border"]
                borders += border
            assert borders == measurements["border_instance_count"]
            assert (
                d["parameters"]["weights_sha256"]
                == protocol["checkpoint_hashes"]["models/stardist/weights_best.h5"]
            )
            totals["verified_instance_maps"] += 1
            totals["verified_instance_geometry"] += len(objects)
        if mode == "vanilla":
            assert star_outputs == 0 and counts["selection"] == 0 and counts["answer_review"] == 0
        else:
            assert star_outputs >= 1
        if mode == "tools":
            assert counts["answer_review"] == 0
        if mode == "full":
            assert counts["selection"] >= 2 and counts["answer_review"] >= 1
            assert feedback_consumers == {"astra", "jev"}
            totals["full_trials_with_feedback_to_planner_and_selector"] += 1
        rows.append(
            {
                "task_id": task["id"],
                "mode": mode,
                "recovery": path in recovered,
                "status": answer["status"],
                "instance_maps": star_outputs,
                "events_sha256": digest(directory / "events.jsonl"),
            }
        )

    load_dotenv(".env", override=True)
    secrets = [
        os.environ[k].encode()
        for k in ("OPENAI_API_KEY", "JEV_API_KEY", "TYPESAFE_API_KEY")
        if os.environ.get(k)
    ]
    for root in [ROOT, PRIMARY, RECOVERY]:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {
                ".json",
                ".jsonl",
                ".html",
                ".md",
                ".log",
                ".toml",
            }:
                raw = path.read_bytes()
                assert not any(secret in raw for secret in secrets), (
                    "Credential found; do not publish"
                )
    output = {
        "primary_trials": 18,
        "separate_recovery_trials": len(recovered),
        "same_original_images": True,
        "frozen_runtime_and_checkpoint_hashes_match": True,
        "recovery_only_changes_timeout": True,
        "modes_isolated": True,
        "keys_found_in_reports_or_logs": False,
        "counts": dict(totals),
        "trials": rows,
    }
    (ROOT / "verification.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({k: v for k, v in output.items() if k != "trials"}, indent=2))


if __name__ == "__main__":
    main()
