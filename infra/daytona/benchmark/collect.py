"""All-attempt means and image-level pass@3; failures never disappear from scores."""

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def average(values):
    return statistics.mean(values) if values else None


def score_groups(rows, expected_images, repetitions):
    groups = {name: [] for name in expected_images}
    for row in rows:
        groups[row["image"]].append(row)
    if any(len(group) > repetitions for group in groups.values()):
        raise ValueError("More than the preregistered number of attempts")
    complete = [group for group in groups.values() if len(group) == repetitions]
    errors = [r["percentage_error"] for r in rows if r["answered"]]
    valid_means = [abs(statistics.mean(r["count"] for r in g)-g[0]["expected"])/g[0]["expected"]*100
                   for g in complete if all(r["answered"] for r in g)]
    total = len(expected_images)*repetitions
    return {"completed_attempts": len(rows), "expected_attempts": total, "pending_attempts": total-len(rows),
        "answered": len(errors), "failed_attempts": len(rows)-len(errors),
        "passes": sum(r["passed"] for r in rows),
        "mean_pass_score": average([float(r["passed"]) for r in rows]),
        "mean_clipped_count_score": average([max(0, 1-r["percentage_error"]/100) if r["answered"] else 0 for r in rows]),
        "pass_at_3": average([float(any(r["passed"] for r in g)) for g in complete]) if repetitions == 3 else None,
        "images_with_all_attempts": len(complete), "total_images": len(expected_images),
        "conditional_mape_percent": average(errors),
        "conditional_ape_sd_percent": statistics.stdev(errors) if len(errors) > 1 else None,
        "complete_cohort_mape_percent": average(errors) if len(errors) == total else None,
        "mean_count_ensemble_mape_percent": average(valid_means),
        "mean_count_ensemble_images": len(valid_means),
        "mean_instance_f1": average([r["instance_f1"] for r in rows if r["instance_f1"] is not None]),
        "mean_agent_seconds": average([r["agent_seconds"] for r in rows if r["agent_seconds"] is not None]),
        "total_input_tokens": sum(r.get("input_tokens") or 0 for r in rows),
        "total_output_tokens": sum(r.get("output_tokens") or 0 for r in rows)}


def collect(run, split="test"):
    selection = read(run / "selection.json")
    cohort = {r["id"]: r for r in read(run / "cohort.json") if r["split"] == split}
    repetitions = 3 if split == "test" else 1
    rows = []
    for path in sorted((run / "jobs" / split).glob("*/result.json")):
        result = read(path)
        if not result.get("finished_at"):
            continue
        arm = result["config"]["agent"]["kwargs"]["mode"]
        task = result["task_name"]
        grade = read(path.parent / "verifier/grading.json", {})
        answer = read(path.parent / "agent/run/answer.json", {})
        timing = result.get("agent_execution") or {}
        seconds = None
        if timing.get("finished_at") and timing.get("started_at"):
            seconds = (datetime.fromisoformat(timing["finished_at"])-datetime.fromisoformat(timing["started_at"])).total_seconds()
        events = path.parent / "agent/run/events.jsonl"
        stage = None
        if events.exists():
            for line in events.read_text().splitlines():
                event = json.loads(line)
                if event["kind"] == "stage":
                    stage = event["data"].get("stage")
        agent_result = result.get("agent_result") or {}
        rows.append({"trial": path.parent.name, "image": task, "arm": arm,
            "source_filename": cohort[task]["source_filename"], "previously_used": cohort[task]["previously_used"],
            "expected": cohort[task]["expected"], "count": grade.get("count"),
            "answered": grade.get("answered", False), "passed": grade.get("within_10_percent", False),
            "percentage_error": grade.get("percentage_error"),
            "instance_f1": (grade.get("segmentation") or {}).get("f1"),
            "agent_seconds": seconds, "review_status": answer.get("review_status"), "last_stage": stage,
            "error": grade.get("error") or answer.get("error") or (result.get("exception_info") or {}).get("exception_message"),
            "input_tokens": agent_result.get("n_input_tokens"), "output_tokens": agent_result.get("n_output_tokens")})
    summaries = {arm: score_groups([r for r in rows if r["arm"] == arm], cohort, repetitions) for arm in selection["arms"]}
    sensitivity = {}
    for label, exposed in (("previously_used", True), ("not_previously_selected", False)):
        names = {k for k, v in cohort.items() if v["previously_used"] == exposed}
        if names:
            sensitivity[label] = {a: score_groups([r for r in rows if r["arm"] == a and r["image"] in names], names, repetitions)
                                  for a in selection["arms"]}
    intervals = {}
    if len(rows) == len(cohort)*repetitions*3:
        names = sorted(cohort)
        matrices = {a: np.array([[float(r["passed"]) for r in rows if r["arm"] == a and r["image"] == n] for n in names])
                    for a in selection["arms"]}
        rng = np.random.default_rng(20260923)
        draws = rng.integers(0, len(names), size=(10000, len(names)))
        for left, right in (("full", "vanilla"), ("full", "stardist"), ("stardist", "vanilla")):
            for metric, transform in (("mean_pass", lambda x: x.mean(axis=1)), ("pass_at_3", lambda x: x.max(axis=1))):
                delta = transform(matrices[left])-transform(matrices[right])
                intervals[f"{left}_minus_{right}:{metric}"] = {"difference": float(delta.mean()),
                    "paired_image_bootstrap_95_percent": np.quantile(delta[draws].mean(axis=1), [.025, .975]).tolist()}
    result = {"updated_at": datetime.now(timezone.utc).isoformat(), "split": split,
        "complete": len(rows) == len(cohort)*repetitions*3, "arms": summaries,
        "exposure_sensitivity": sensitivity, "paired_intervals": intervals, "attempts": rows,
        "interpretation": "Partial means describe completed attempts only. pass@3 includes only images with all 3 finished; never an estimate over pending images."}
    target = run / f"{split}-summary.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    temporary.replace(target)
    def pct(value):
        return "—" if value is None else f"{value*100:.1f}%"
    lines = [f"# BBBC039 {split} — {'complete' if result['complete'] else 'in progress'}", "",
        "| Arm | Finished | Answered | Mean pass score | pass@3 | Images with all attempts | MAPE of returned answers |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for arm, item in summaries.items():
        mape = item["conditional_mape_percent"]
        lines.append(f"| {arm} | {item['completed_attempts']}/{item['expected_attempts']} | {item['answered']} | {pct(item['mean_pass_score'])} | {pct(item['pass_at_3'])} | {item['images_with_all_attempts']}/{item['total_images']} | {'—' if mape is None else f'{mape:.2f}%'} |")
    lines += ["", "Pass: count within 10% of the annotation-derived total. Failed attempts score zero.",
        "pass@3: at least one pass among three attempts; this needs the reference answer to identify success and is not a deployable selector.",
        "Partial results are not a final ranking. Conditional MAPE excludes missing answers; consult coverage.",
        "The JSON includes counts, segmentation F1, review status, failure stage, tokens and image-paired intervals.", ""]
    (run / f"{split}-summary.md").write_text("\n".join(lines))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--split", default="test", choices=["test", "canary"])
    args = parser.parse_args()
    print(json.dumps(collect(args.run, args.split)["arms"], indent=2))
