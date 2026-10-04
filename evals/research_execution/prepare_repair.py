"""Freeze an all-image full-arm repair repeat, preserving the original controls."""

import argparse
import json
import shutil
from datetime import datetime, timezone

from vision_harness.research_execution.contracts import Policy
from vision_harness.tracing import write_json

from .prepare import REPORT, ROOT, TASKS, sha, source_snapshot


def prepare_repair(source, split):
    source_report, report = REPORT / source, REPORT / split
    old_tasks, tasks = TASKS / source, TASKS / split
    baseline = ROOT / "jobs" / f"research-execution-{source}-vanilla"
    alias = ROOT / "jobs" / f"research-execution-{split}-vanilla"
    if report.exists() or tasks.exists() or alias.exists() or alias.is_symlink():
        raise ValueError("Repeat name already exists; preserve it and choose a fresh name")
    selection = json.loads((source_report / "selection.json").read_text())
    cohort = json.loads((source_report / "cohort.json").read_text())
    expected = len(cohort) * selection["repetitions"]
    if len(list(baseline.glob("*/result.json"))) != expected:
        raise ValueError("Original controls must contain every completed attempt, including failures")
    for field in ("amendment_before_accuracy_inspection", "changed_configuration", "amendment_reason",
                  "infrastructure_repeat", "repeat_before_accuracy_inspection", "concurrent_deployment_note"):
        selection.pop(field, None)
    selection.update({
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "split": "official test images reused for a post-hoc engineering repair repeat",
        "configuration_variant": split, "variant_of": source,
        "rule": "Reuse every image from the declared previous cohort; no filtering by failure or accuracy",
        "policy": Policy().model_dump(), "source_snapshot": source_snapshot(),
        "enforce_source_snapshot": True, "development_prefix_replay": False,
        "post_hoc_repair": True, "previous_outcomes_inspected": True,
        "full_arm_fresh_attempts": expected, "new_baseline_calls": 0,
        "baseline_reuse": {"job": baseline.name, "attempts": expected,
                           "all_failures_retained": True, "contemporaneous": False},
        "baseline_job": baseline.name, "full_job": f"research-execution-{split}-full",
        "concurrency": 4,
        "answer_policy": "Retain independently validated counts if downstream review fails, explicitly labelled unreviewed_after_error. Report full review completion separately; unreviewed output is not JEV approval.",
        "retry_policy": "One configured transient API retry per request, one catalog semantic repair, one research token-limit retry; existing 48-call/1500-second/two-round limits. No whole-trial retries.",
        "repairs": ["traced bounded transport retry", "catalog IDs/source validation with one repair",
                    "research truncation recovery", "verified installed StarDist loader and call contracts",
                    "executor reports execution rather than blocking on a second visual approval",
                    "validated artifact retention with explicit review status"],
        "runtime_condition": "Local Docker CPU workers; cloud benchmark coordinator also active. Caffeinate does not prevent lid-close sleep. Runtime is observational, not a controlled speed comparison.",
    })
    selection["limitations"] += [
        "Previously inspected cohort: repair evidence, not fresh held-out generalization",
        "Existing vanilla controls reused; no new vanilla inference",
        "Coverage with unreviewed fallbacks is distinct from complete-harness review coverage",
    ]
    report.mkdir(parents=True)
    write_json(report / "selection.json", selection)
    shutil.copy2(source_report / "toolchain.json", report / "toolchain.json")
    shutil.copy2(source_report / "cohort.json", report / "cohort.json")
    shutil.copytree(old_tasks, tasks)
    verified = {}
    for row in cohort:
        task = tasks / row["id"]
        old = old_tasks / row["id"]
        for relative in ("instruction.md", "task.toml", "environment/input.tif", "environment/input.png",
                         "environment/Dockerfile", "tests/reference.npz", "tests/verify.py", "tests/test.sh", "tests/Dockerfile"):
            before, after = sha((old / relative).read_bytes()), sha((task / relative).read_bytes())
            if before != after:
                raise ValueError(f"Repeated task changed: {row['id']}/{relative}")
            verified[f"{row['id']}/{relative}"] = after
        app = task / "environment/app"
        shutil.rmtree(app)
        shutil.copytree(ROOT / "src/vision_harness", app / "src/vision_harness",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (app / "configs").mkdir()
        shutil.copy2(ROOT / "configs/research-execution.toml", app / "configs/research-execution.toml")
        (app / "prompts").mkdir()
        for name in ("astra-research-execution.md", "jev_plan_conditions.json", "jev_review_estimate.json"):
            shutil.copy2(ROOT / "prompts" / name, app / "prompts" / name)
        if list((task / "environment").rglob(".env")) or list((task / "environment").rglob("reference.npz")):
            raise ValueError("Secret or reference found in agent build context")
    alias.symlink_to(baseline.name, target_is_directory=True)
    write_json(report / "unchanged-task-hashes.json", verified)
    print(json.dumps({"split": split, "images": len(cohort), "new_full_attempts": expected,
                      "new_vanilla_attempts": 0, "unchanged_files_verified": len(verified)}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="test-awake96")
    parser.add_argument("--split", required=True)
    args = parser.parse_args()
    for name in (args.source, args.split):
        if not name.replace("-", "").replace("_", "").isalnum():
            parser.error("Split names must be simple directory names")
    prepare_repair(args.source, args.split)


if __name__ == "__main__":
    main()
