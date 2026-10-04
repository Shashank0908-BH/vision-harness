"""Label-blind CLI progress: stages and execution failures, never accuracy results."""

import argparse
import json
from collections import Counter
from datetime import datetime, timezone

from .prepare import ROOT


def status(split):
    jobs = []
    for job in sorted((ROOT / "jobs").glob(f"research-execution-{split}*")):
        trials = []
        for config in sorted(job.glob("*/config.json")):
            directory = config.parent
            path = directory / "agent/run/events.jsonl"
            events = []
            if path.exists():
                lines = path.read_text().splitlines()
                for index, line in enumerate(lines):
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        if index != len(lines)-1:
                            raise
                        # A live writer may be partway through the final line.
            result_path = directory / "result.json"
            result = json.loads(result_path.read_text()) if result_path.exists() else {}
            external_failure = result.get("exception_info")
            stages = [e["data"]["stage"] for e in events if e["kind"] == "stage"]
            final = next((e["data"] for e in reversed(events) if e["kind"] == "final"), None)
            elapsed = None
            if events:
                elapsed = round((datetime.now(timezone.utc)-datetime.fromisoformat(events[0]["time"])).total_seconds())
            if final:
                elapsed = round(final["elapsed_seconds"])
            trials.append({"trial": directory.name,
                "stage": "finished" if final or result.get("finished_at") else stages[-1] if stages else "starting",
                "status": final["status"] if final else "error" if external_failure else "running",
                "elapsed_seconds": elapsed,
                "error_type": final.get("error_type") if final else external_failure.get("exception_type") if external_failure else None})
        jobs.append({"job": job.name, "stage_counts": dict(Counter(t["stage"] for t in trials)), "trials": trials})
    return jobs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="test")
    parser.add_argument("--summary", action="store_true", help="Only aggregate stages, answer statuses and failure types")
    args = parser.parse_args()
    jobs = status(args.split)
    if args.summary:
        jobs = [{"job": job["job"], "stage_counts": job["stage_counts"],
                 "status_counts": dict(Counter(t["status"] for t in job["trials"])),
                 "error_types": dict(Counter(t["error_type"] for t in job["trials"] if t["error_type"]))}
                for job in jobs]
    print(json.dumps(jobs, indent=2))
