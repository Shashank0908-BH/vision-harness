# Review the repeated external benchmark

Open [the paginated report](../reports/kromp-repeated-20260922/index.html), then
[the findings](../reports/kromp-repeated-20260922/findings.md). The report contains
aggregate results, all three repetitions, uncertainty intervals, the ten published
test groups, and 37 image pages. Each page shows the original, expert reference
outlines, all four specialist overlays, counts and links to three traces per
repetition. Reference overlays are evaluation artifacts made after inference.

The [frozen protocol](repeated-benchmark.md) remains unchanged. This document records
the completed run and subsequent reporting checks.

## What ran

- 37 official test fields, each with three fresh paired trials: 111 trials total.
- Four actual specialist executions per trial: 444 masks, without prediction reuse.
- Vanilla Astra, the current full routing chain, and a separate Astra answer using
  its preferred specialist. The latter shares the full chain's initial proposal.
- A saved pre-review stage for the Jev selection ablation; no independent replan.
- Strict-support and measurement-only diagnostics, clearly separated from runs.
- 781 provider calls, including four allowed output-token recovery calls. All
  response records exist. Zero terminal execution errors; abstentions are retained.
- Native Mac execution and 333 validated Harbor ATIF traces, not Docker jobs.

Mean ± SD averages three run error scores, not the three predicted counts before
scoring. Conditional scores exclude missing numeric answers and must be read with
coverage. All-attempt within-10% success penalizes missing answers. The bootstrap
uses image clusters rather than treating 111 calls as independent images.

## File map

| File or directory | Purpose |
|---|---|
| `evals/repeated/data.py` | Frozen cohort, provenance, downloads and identical inputs. |
| `evals/repeated/runner.py` | Frozen repeated inference and paired ablation requests. |
| `evals/repeated/metrics.py` | Frozen reference decoding, scoring, repeated aggregation and bootstrap. |
| `evals/repeated/progress.py` | Read-only inference status; never reads reference labels. |
| `evals/repeated/audit.py` | Source/resource checks, trace validation, decision ordering, mask/area consistency and call accounting. |
| `evals/repeated/verify_annotations.py` | Independent Pillow count decoder, separate from OpenCV used in scoring. |
| `evals/repeated/diagnostics.py` | Post-scoring complete-case comparisons, choices, review/accuracy cross-tab and repeatability. |
| `evals/repeated/plots.py` | Standalone PNG/SVG scientific figures. |
| `evals/repeated/report.py` | Score tables, reference previews and paginated HTML. |
| `evals/repeated/qa_report.py` | Browser checks of pages, images, links and four viewport widths. |
| `reports/kromp-repeated-20260922/` | Frozen protocol, outcomes, findings, audits, figures and review pages. |
| `runs/kromp-repeated-20260922/repeat-N/IMAGE_ID/` | Per-attempt traces, responses, decisions and masks; Git-ignored. |
| `evals/datasets/generated/kromp-repeated-20260922/` | Downloaded originals/annotations and image-only input manifest; Git-ignored. |

Hashes in `protocol.json` identify source snapshots. The inference, scoring and
protocol files stayed frozen. Reporting, diagnostics and audit helpers were
developed after the freeze without changing saved predictions or the cohort.

## Recompute reports without calling APIs

Run from the repository root after `inference-finished.json` exists:

```bash
.venv/bin/python -m evals.repeated score
.venv/bin/python -m evals.repeated.audit
.venv-stardist/bin/python evals/repeated/verify_annotations.py
.venv/bin/python -m evals.repeated.diagnostics
python3 evals/repeated/plots.py
.venv/bin/python -m evals.repeated report
python3 evals/repeated/qa_report.py
```

The system Python has matplotlib and Playwright/Chromium; the StarDist environment
has Pillow. These are reporting dependencies, not additional hosted model calls.
`qa_report.py` saves screenshots under `/tmp/vision-repeated-*.png`.
Images/previews are checked at 1440, 768, 390 and 320 pixels. Trace and original
TIFF links require the local Git-ignored run/dataset directories, while PNG
previews and aggregate results are checked into this repository.

`prepare` refuses to overwrite an existing cohort. `infer` resumes only unfinished
work and verifies frozen inputs; it does not create fresh repetitions in this
completed experiment. A new experiment needs a separately named output directory
and a new frozen protocol. Do not tune parameters on these scored test images and
describe a rerun as a new held-out test.

## Startup recovery

The first official download endpoint dropped a connection before inference began.
The downloader switched to the archive's direct HTTPS file service with bounded
download retries, retaining exactly the same official filenames. The original
download protocol is preserved as `protocol-initial-download.json`; the final
protocol and complete input hashes were frozen before any inference. No model
outcome was discarded or replaced through this recovery.
