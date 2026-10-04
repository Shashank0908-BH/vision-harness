"""Summarize operational failures and clock gaps without reading reference scores."""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parents[1]


def diagnose(job):
    rows = []
    reach = Counter()
    for trial in sorted(job.iterdir()):
        path = trial / "agent/run/events.jsonl"
        if not path.exists():
            continue
        events = []
        for line in path.read_text().splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # A live writer may have an incomplete last line.
        if not events:
            continue
        final = next((e["data"] for e in reversed(events) if e["kind"] == "final"), {})
        stages = [e["data"]["stage"] for e in events if e["kind"] == "stage"]
        reach.update(set(stages))
        wall = (datetime.fromisoformat(events[-1]["time"]) -
                datetime.fromisoformat(events[0]["time"])).total_seconds()
        active = final.get("elapsed_seconds")
        rows.append({
            "trial": trial.name, "status": final.get("status", "running"),
            "returned_count": final.get("count") is not None,
            "review_status": final.get("review_status", "not_reached"),
            "last_stage": stages[-1] if stages else "direct_baseline",
            "error_type": final.get("error_type"), "error": final.get("error"),
            "wall_seconds_between_events": round(wall, 2),
            "controller_elapsed_seconds": active,
            "wall_minus_controller_seconds": round(wall-active, 2) if active is not None else None,
        })
    terminal = [r for r in rows if r["status"] != "running"]
    failures = [r for r in terminal if r["error_type"]]
    return {
        "job": job.name, "trials_with_events": len(rows), "terminal_trials": len(terminal),
        "counts_returned": sum(r["returned_count"] for r in terminal),
        "stage_reached_trials": dict(reach),
        "errors_by_type": dict(Counter(r["error_type"] for r in failures)),
        "errors_by_last_stage": dict(Counter(r["last_stage"] for r in failures)),
        "review_statuses": dict(Counter(r["review_status"] for r in terminal)),
        "terminal_trials_with_wall_gap_over_60_seconds": sum(
            r["wall_minus_controller_seconds"] > 60 for r in terminal
            if r["wall_minus_controller_seconds"] is not None),
        "interpretation": "Clock gaps are operational evidence, not proof of any individual failure's cause. No reference labels or accuracy scores are read.",
        "trials": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", required=True)
    split = parser.parse_args().split
    target = REPORT if split == "test" else REPORT / split
    results = [diagnose(ROOT / "jobs" / f"research-execution-{split}-{mode}")
               for mode in ("vanilla", "full")
               if (ROOT / "jobs" / f"research-execution-{split}-{mode}").exists()]
    (target / "operational-diagnostics.json").write_text(json.dumps(results, indent=2)+"\n")
    print(json.dumps([{k: v for k, v in row.items() if k != "trials"} for row in results], indent=2))
