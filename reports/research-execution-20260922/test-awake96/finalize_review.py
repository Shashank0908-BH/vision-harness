"""Audit the completed repeat and publish a review summary without more model calls."""

import html
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parents[2]


def finalize():
    result = json.loads((REPORT / "results.json").read_text())
    assert len(result["records"]) == 72
    assert result["cohort_images"] == 12 and result["repetitions"] == 3
    assert all(result["metrics"][mode]["attempts"] == 36 for mode in ("vanilla", "full"))
    assert not result["selection"].get("baseline_reuse")
    source = ROOT / "evals/tasks/generated/research-execution/test-transport96"
    frozen = ROOT / "evals/tasks/generated/research-execution/test-awake96"
    checked = 0
    for path in frozen.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            assert path.read_bytes() == (source / path.relative_to(frozen)).read_bytes()
            checked += 1
    subprocess.run([sys.executable, str(REPORT.parent / "diagnose_runs.py"),
                    "--split", "test-awake96"], cwd=ROOT, check=True, capture_output=True)
    diagnostics = json.loads((REPORT / "operational-diagnostics.json").read_text())
    start = datetime.fromisoformat(json.loads((REPORT / "started.json").read_text())["started_at_utc"])
    end = datetime.now().astimezone()
    log = subprocess.run(["pmset", "-g", "log"], capture_output=True, text=True)
    entries = []
    parsed_events = 0
    for line in log.stdout.splitlines():
        if not any(word in line for word in ("Entering Sleep", "Wake from", "DarkWake from")):
            continue
        try:
            timestamp = datetime.strptime(line[:25], "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            continue
        parsed_events += 1
        if start <= timestamp <= end:
            entries.append(line)
    (REPORT / "host-sleep-events.txt").write_text("\n".join(entries)+"\n")
    gaps = sum(d["terminal_trials_with_wall_gap_over_60_seconds"] for d in diagnostics)
    interrupted = any("Entering Sleep" in line for line in entries)
    audit_available = log.returncode == 0 and parsed_events > 0
    if not audit_available:
        condition = "Host sleep audit unavailable; infrastructure validity is unconfirmed."
    elif interrupted or gaps:
        condition = (f"Infrastructure caution: host sleep events={sum('Entering Sleep' in s for s in entries)}, "
                     f"trials with wall/controller gaps over 60 seconds={gaps}. "
                     "Do not interpret this as a clean comparison until these interruptions are reviewed.")
    else:
        condition = ("No host sleep or wall/controller gap over 60 seconds was observed during this repeat. "
                     "API, planning and execution failures still remain in its score.")
    vanilla, full = result["metrics"]["vanilla"], result["metrics"]["full"]
    difference = result["paired_success_difference"]
    verdict = (
        f"Full harness: {full['within_10_percent']}/36 attempts within 10% of the reference "
        f"({full['all_attempt_success_percent']:.2f}%), with {full['answered']}/36 counts returned. "
        f"Vanilla Astra: {vanilla['within_10_percent']}/36 "
        f"({vanilla['all_attempt_success_percent']:.2f}%), with {vanilla['answered']}/36 counts returned."
    )
    conclusion = ("The full harness did not improve all-attempt success in this pilot."
                  if difference["mean"] <= 0 else
                  "The full harness had higher all-attempt success in this pilot; this does not establish broad superiority.")
    summary = ("# Completed infrastructure repeat\n\n" + condition + "\n\n" + verdict + "\n\n" +
               conclusion + "\n\n" +
               f"Full minus vanilla: {difference['mean']*100:+.2f} percentage points; "
               f"descriptive image-cluster bootstrap 95% interval "
               f"[{difference['ci95'][0]*100:+.2f}, {difference['ci95'][1]*100:+.2f}].\n\n" +
               "Cohort: the same 12 BBBC039 official-test images, three fresh runs per arm. "
               "No previous answers or research prefixes were reused. The 96 KB task environments "
               f"remain byte-identical to the frozen configuration ({checked} files checked). "
               "The interrupted earlier experiments remain separate and are not pooled.\n\n" +
               "[Interactive traces and all counts](index.html) · [Full score table](final-score.md) · "
               "[Operational failures](operational-diagnostics.json) · [Host audit](host-sleep-events.txt) · "
               "[Frozen protocol](selection.json)\n")
    (REPORT / "review-summary.md").write_text(summary)
    page = (REPORT / "index.html").read_text()
    notice = "<p><strong>" + html.escape(condition) + "</strong></p><p>" + html.escape(verdict) + "</p>"
    page = page.replace("</h1>", "</h1>" + notice, 1)
    page = page.replace("</style>", ".scroll{overflow:auto;max-width:100%}"
                        "@media(max-width:700px){body{padding:16px}article{overflow-wrap:anywhere}}"
                        "</style>")
    page = page.replace("<table>", '<div class="scroll"><table>').replace("</table>", "</table></div>")
    (REPORT / "index.html").write_text(page)
    (REPORT / "review-complete.json").write_text(json.dumps({
        "finished_at": end.isoformat(), "host_log_available": audit_available,
        "host_sleep_observed": interrupted, "large_clock_gaps": gaps,
        "frozen_files_checked": checked, "planned_trials": 72,
        "condition": condition, "summary": verdict,
    }, indent=2)+"\n")
    print(summary, flush=True)


if __name__ == "__main__":
    while not (REPORT / "completion.json").exists():
        time.sleep(30)
    finalize()
