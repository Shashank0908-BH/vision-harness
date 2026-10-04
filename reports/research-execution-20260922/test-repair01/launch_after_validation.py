"""Launch the declared repair repeat only after the validation chain completes."""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORT = Path(__file__).resolve().parent
SPLIT = "test-repair01"
VALIDATION = ROOT / "jobs/research-execution-dev-repair02-full"


def read(path):
    return json.loads(path.read_text()) if path.exists() else {}


def status(stage, **details):
    record = {"stage": stage, "updated_at": datetime.now(timezone.utc).isoformat(), **details}
    temporary = REPORT / "launch-status.tmp"
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    temporary.replace(REPORT / "launch-status.json")
    print(json.dumps(record), flush=True)


def main():
    status("waiting_for_validation", validation_job=VALIDATION.name,
           planned_new_full_attempts=36, planned_new_vanilla_attempts=0)
    deadline = time.monotonic() + 3600
    while not read(VALIDATION / "result.json").get("finished_at"):
        if time.monotonic() >= deadline:
            status("validation_wait_expired", full_cohort_started=False)
            return
        time.sleep(10)
    trials = list(VALIDATION.glob("*/result.json"))
    if len(trials) != 1:
        status("validation_incomplete", full_cohort_started=False)
        return
    folder = trials[0].parent
    answer = read(folder / "agent/run/answer.json")
    grading = read(folder / "verifier/grading.json")
    # Gate on the execution/review chain, never on count accuracy or approval.
    if not grading.get("answered") or not answer.get("review_completed"):
        status("validation_chain_failed", full_cohort_started=False,
               trial=folder.name, review_status=answer.get("review_status"),
               error=answer.get("error") or read(trials[0]).get("exception_info"))
        return
    status("launching_full_cohort", validation_trial=folder.name,
           validation_review_status=answer.get("review_status"),
           planned_new_full_attempts=36, planned_new_vanilla_attempts=0)
    command = [sys.executable, "-m", "evals.research_execution.run", "--split", SPLIT,
               "--arms", "full", "--concurrency", "4"]
    result = subprocess.run(command, cwd=ROOT, check=False)
    job = read(ROOT / "jobs" / f"research-execution-{SPLIT}-full/result.json")
    if not job.get("finished_at") or job.get("n_total_trials") != 36:
        status("full_cohort_incomplete", launcher_exit_code=result.returncode,
               completed=job.get("stats", {}).get("n_completed_trials"))
        return
    with (REPORT / "report-generation.log").open("w") as output:
        subprocess.run([sys.executable, "-m", "evals.research_execution.report", "--split", SPLIT],
                       cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
    report = read(REPORT / "results.json")
    lines = ["# Repair repeat: all 12 images, three fresh full-harness runs each", "",
             "36 new full-harness trials; all 36 original vanilla controls reused, including failures.",
             "This is a post-hoc repair comparison on previously inspected images. It is not an unseen-cohort result.", "",
             "| Arm | Counts returned | Within 10% | Conditional MAPE | Completed JEV review | Unreviewed counts |",
             "|---|---:|---:|---:|---:|---:|"]
    for mode, metrics in report["metrics"].items():
        mape = metrics["conditional_mape_percent"]
        value = "Unavailable" if mape is None else f"{mape:.2f}%"
        lines.append(f"| {mode} | {metrics['answered']}/36 | {metrics['within_10_percent']}/36 | {value} | "
                     f"{metrics['review_completed_answered'] if mode == 'full' else 'N/A'} | "
                     f"{metrics['unreviewed_answered'] if mode == 'full' else 'N/A'} |")
    lines += ["", "Missing counts stay in the denominator. Provisional and unreviewed counts are not JEV-approved.",
              "Conditional MAPE compares answered subsets; it must be read with coverage.",
              "[Inspect all counts and traces](index.html) · [Frozen protocol](selection.json)", ""]
    (REPORT / "final-score.md").write_text("\n".join(lines))
    status("complete", metrics=report["metrics"], launcher_exit_code=result.returncode)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        status("runner_error", error_type=type(error).__name__, error=str(error))
        raise
