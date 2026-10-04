"""Audit all repeated trials without interpreting private model reasoning."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
from harbor.utils.trajectory_validator import TrajectoryValidator

from vision_harness.routing.catalog import sha256
from vision_harness.routing.runtime import source_hash
from vision_harness.tracing import write_json

from .data import DATA, REPORT, RUNS


def audit():
    result = json.loads((REPORT / "results.json").read_text())
    protocol = json.loads((REPORT / "protocol.json").read_text())
    assert source_hash() == protocol["source_sha256"]
    for group in ["resources_sha256", "script_sha256", "metadata_sha256"]:
        for filename, expected in protocol[group].items():
            assert sha256(Path(filename)) == expected, filename
    assert sha256(Path("docs/repeated-benchmark.md")) == protocol["protocol_document_sha256"]
    assert (
        sha256(DATA / "inputs.json")
        == json.loads((REPORT / "input-freeze.json").read_text())["sha256"]
    )
    inputs = {r["id"]: r for r in json.loads((DATA / "inputs.json").read_text())}
    ids = {
        p["plan_id"]
        for p in json.loads(Path("catalog/microscopy-v1.json").read_text())["procedures"]
    }
    counters = Counter()
    status = Counter()
    latencies = {k: [] for k in ["vanilla", "full_input_to_final", "astra_tools_answer_only"]}
    errors, missing = [], []
    for row in result["records"]:
        parent = RUNS / f"repeat-{row['repeat']}" / row["id"]
        for arm in ["vanilla", "routing", "astra-tools"]:
            folder = parent / arm
            if not (folder / "manifest.json").exists():
                missing.append(str(folder))
                continue
            manifest = json.loads((folder / "manifest.json").read_text())
            assert sha256(folder / "artifacts/original.png") == inputs[row["id"]]["image_sha256"]
            counters["identical_input_images_verified"] += 1
            if arm == "routing":
                assert manifest["source_sha256"] == protocol["source_sha256"]
                assert (
                    manifest["catalog_sha256"]
                    == protocol["resources_sha256"]["catalog/microscopy-v1.json"]
                )
            validator = TrajectoryValidator()
            assert validator.validate(folder / "trajectory.json"), validator.get_errors()
            counters["valid_trajectories"] += 1
            events = [
                json.loads(line) for line in (folder / "events.jsonl").read_text().splitlines()
            ]
            started = [e for e in events if e["kind"] == "call_started"]
            finished = {e["data"]["call_id"] for e in events if e["kind"] == "call_finished"}
            counters["provider_calls_started"] += len(started)
            counters["provider_responses_saved"] += len(finished)
            for event in started:
                status[event["data"]["provider"] + "_calls"] += 1
                if event["data"]["call_id"] not in finished:
                    counters["calls_without_response"] += 1
            for event in events:
                if event["kind"] == "error":
                    errors.append(
                        {
                            "id": row["id"],
                            "repeat": row["repeat"],
                            "arm": arm,
                            "stage": event["data"].get("stage"),
                            "error_type": event["data"].get("error_type"),
                            "error": event["data"].get("error"),
                        }
                    )
                if event["kind"] == "format_retry":
                    counters["schema_or_output_budget_retries"] += 1
            if arm == "routing":
                decisions = [e for e in events if e["kind"] == "routing_decision"]
                if decisions:
                    d = decisions[0]
                    assert len(d["data"]["assessments"]) == 4
                    assert {a["plan_id"] for a in d["data"]["assessments"]} == ids
                    assert sha256(folder / "decision.json") == d["data"]["sha256"]
                    tool_events = [e for e in events if e["kind"] == "tool_started"]
                    assert all(e["sequence"] > d["sequence"] for e in tool_events)
                    counters["decisions_frozen_before_execution"] += 1
                    final = [e for e in events if e["kind"] == "final_answer"]
                    if final:
                        assert all(e["sequence"] > final[0]["sequence"] for e in tool_events[1:])
                        latencies["full_input_to_final"].append(
                            (
                                datetime.fromisoformat(final[0]["time"])
                                - datetime.fromisoformat(events[0]["time"])
                            ).total_seconds()
                        )
                for evidence_path in (folder / "specialists").glob("*/evidence.json"):
                    evidence = json.loads(evidence_path.read_text())
                    instances = json.loads(evidence_path.with_name("instances.json").read_text())
                    with np.load(evidence_path.with_name("labels.npz"), allow_pickle=False) as z:
                        labels = z["labels"]
                    unique, counts = np.unique(labels, return_counts=True)
                    areas = {int(k): int(v) for k, v in zip(unique, counts, strict=True) if k > 0}
                    assert len(areas) == evidence["count"] == len(instances)
                    assert areas == {o["id"]: o["area_pixels"] for o in instances}
                    assert labels.shape == (
                        evidence["coordinates"]["height"],
                        evidence["coordinates"]["width"],
                    )
                    assert (
                        sha256(evidence_path.with_name("labels.npz"))
                        == evidence["worker"]["labels_sha256"]
                    )
                    assert evidence["worker"]["image_sha256"] == sha256(
                        folder / "artifacts/original.png"
                    )
                    counters["instance_maps_audited"] += 1
                    counters["instance_areas_audited"] += len(instances)
            elif arm == "vanilla":
                latencies["vanilla"].append(manifest["elapsed_seconds"])
            else:
                latencies["astra_tools_answer_only"].append(manifest["elapsed_seconds"])
    # Independent published counts are checked separately with Pillow/tifffile.
    output = {
        "checks": dict(counters),
        "provider_counts": dict(status),
        "errors": errors,
        "missing_artifacts": missing,
        "timing": {
            k: {
                "n": len(v),
                "mean_seconds": float(np.mean(v)) if v else None,
                "median_seconds": float(np.median(v)) if v else None,
            }
            for k, v in latencies.items()
        },
        "timing_scope": "concurrent benchmark including resource queues; branch timing covers answer stage only",
        "source_hashes_match_frozen_protocol": True,
        "inputs_sha256": sha256(DATA / "inputs.json"),
    }
    write_json(REPORT / "audit.json", output)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    audit()
