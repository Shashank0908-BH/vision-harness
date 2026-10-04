"""Read-only progress; deliberately never reads benchmark labels."""

import json
from collections import Counter
from datetime import datetime, timezone

from .data import REPEATS, RUNS


def progress():
    trials = list(RUNS.glob("repeat-*/*/complete.json"))
    folders = list(RUNS.glob("repeat-*/*/schedule.json"))
    statuses = {arm: Counter() for arm in ["routing", "vanilla", "astra-tools"]}
    for arm in statuses:
        for path in RUNS.glob(f"repeat-*/*/{arm}/answer.json"):
            try:
                data = json.loads(path.read_text())
            except json.JSONDecodeError:
                continue
            statuses[arm][data["status"]] += 1
    earliest = min(
        (datetime.fromisoformat(json.loads(p.read_text())["started_at"]) for p in folders),
        default=None,
    )
    elapsed = (datetime.now(timezone.utc) - earliest).total_seconds() if earliest else 0
    masks = len(list(RUNS.glob("repeat-*/*/routing/specialists/*/evidence.json")))
    summary = {
        "completed_paired_trials": len(trials),
        "scheduled_trials": 37 * REPEATS,
        "started_trials": len(folders),
        "repetitions_completed": {
            str(n): len(list((RUNS / f"repeat-{n}").glob("*/complete.json")))
            for n in range(1, REPEATS + 1)
        },
        "arm_statuses": {k: dict(v) for k, v in statuses.items()},
        "completed_specialist_masks": masks,
        "elapsed_minutes": round(elapsed / 60, 1),
        "all_inference_finished": (RUNS / "inference-finished.json").exists(),
        "this_progress_command_reads_labels": False,
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    progress()
