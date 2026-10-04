"""Generate review artifacts after both frozen jobs finish; no benchmark mutation."""

import argparse
import html
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_REPORT = Path(__file__).resolve().parent
ROOT = BASE_REPORT.parents[1]
SPLIT = "test"
REPORT = BASE_REPORT


def completed():
    for mode in ("vanilla", "full"):
        path = ROOT / "jobs" / f"research-execution-{SPLIT}-{mode}" / "result.json"
        try:
            result = json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return False
        if not result.get("finished_at"):
            return False
        if result["n_total_trials"] != 36:
            raise ValueError("Job differs from the frozen 36-attempt arm")
    return True


def format_number(value, suffix=""):
    return "Not defined" if value is None else f"{value:.2f}{suffix}"


def finish():
    with (REPORT / "report-generation.log").open("w") as stream:
        subprocess.run([sys.executable, "-m", "evals.research_execution.report", "--split", SPLIT], cwd=ROOT,
                       stdout=stream, stderr=subprocess.STDOUT, check=True)
    result = json.loads((REPORT / "results.json").read_text())
    assert len(result["records"]) == 72
    rows = []
    for mode, title in (("vanilla", "Vanilla Astra"), ("full", "Full research-execution harness")):
        summary = result["metrics"][mode]
        rows.append(f"| {title} | {summary['answered']}/{summary['attempts']} | "
                    f"{summary['within_10_percent']}/{summary['attempts']} "
                    f"({summary['all_attempt_success_percent']:.2f}%) | "
                    f"{format_number(summary['conditional_mape_percent'], '%')} | "
                    f"{format_number(summary['complete_cohort_mape_percent'], '%')} | "
                    f"{format_number(summary['mean_seconds'], ' s')} |")
    paired = result["paired_success_difference"]
    text = """# Frozen research-execution comparison

BBBC039: 12 previously unused official-test images, three fresh runs per image
in each arm. All 72 planned attempts remain in the primary denominator.
Failures and missing answers count as unsuccessful. This is a counting task
derived from published instance masks, not the dataset's original benchmark score.

| Arm | Counts returned | Within 10% of reference | Conditional MAPE | Complete-cohort MAPE | Mean runtime |
|---|---:|---:|---:|---:|---:|
""" + "\n".join(rows)
    text += (f"\n\nFull minus vanilla within-10% success: **{paired['mean']*100:+.2f} percentage points**. "
             f"The image-cluster bootstrap 95% interval is [{paired['ci95'][0]*100:+.2f}, "
             f"{paired['ci95'][1]*100:+.2f}] percentage points. "
             "The 12 images, rather than their 36 repetitions, are the resampling units.\n")
    text += """
Conditional MAPE uses only returned, independently validated counts. It must be
read with coverage; complete-cohort MAPE is undefined when counts are missing.
Jev review status is retained separately from grading, and provisional counts
are not represented as Jev-approved answers. The full system has additional
research, code execution, original 16-bit pixels and specialist inference; this
comparison cannot isolate Jev's contribution or establish broad multimodal superiority.

See the [paginated report](index.html), [all repeated results](results.json),
[frozen selection and source hashes](selection.json), and
[development history](development-status.md). Errors, programs, documentation,
model scores, masks and Harbor traces are linked from individual report entries.
"""
    if result["selection"].get("baseline_reuse"):
        notice = ("This is the separately frozen 96 KB transport-budget configuration. "
                  "All 36 full-harness trials are new. The 36 vanilla trials are reused "
                  "in full from the original experiment; they are not 36 additional baseline calls. "
                  "Both harness configurations are preserved and reported.\n\n")
        text = text.replace("BBBC039:", notice + "BBBC039:", 1)
        page = (REPORT / "index.html").read_text()
        page = page.replace("<h1>Research → score → execute → measure</h1>",
                            "<h1>96 KB configuration comparison</h1><p>" + notice.strip() + "</p>")
        (REPORT / "index.html").write_text(page)
    if SPLIT in ("test", "test-transport96") and (BASE_REPORT / "infrastructure-interruption.json").exists():
        note = ("Infrastructure interruption: the laptop repeatedly slept during active requests. "
                "All failures remain recorded, but this is not a clean accuracy or latency comparison. "
                "See the host-sleep-events.txt evidence in the parent experiment report.")
        text = text.replace("\n\n", "\n\n> " + note + "\n\n", 1)
        page = (REPORT / "index.html").read_text()
        page = page.replace("</h1>", "</h1><p><strong>" + html.escape(note) + "</strong></p>", 1)
        (REPORT / "index.html").write_text(page)
    (REPORT / "final-score.md").write_text(text)
    (REPORT / "completion.json").write_text(json.dumps({
        "status": "reports_generated", "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "planned_attempts": 72, "artifacts": ["results.json", "index.html", "final-score.md"]}, indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="test")
    SPLIT = parser.parse_args().split
    REPORT = BASE_REPORT if SPLIT == "test" else BASE_REPORT / SPLIT
    while not completed():
        time.sleep(30)
    finish()
