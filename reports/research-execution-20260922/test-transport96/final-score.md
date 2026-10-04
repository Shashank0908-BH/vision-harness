# Frozen research-execution comparison

> Infrastructure interruption: the laptop repeatedly slept during active requests. All failures remain recorded, but this is not a clean accuracy or latency comparison. See the host-sleep-events.txt evidence in the parent experiment report.

This is the separately frozen 96 KB transport-budget configuration. All 36 full-harness trials are new. The 36 vanilla trials are reused in full from the original experiment; they are not 36 additional baseline calls. Both harness configurations are preserved and reported.

BBBC039: 12 previously unused official-test images, three fresh runs per image
in each arm. All 72 planned attempts remain in the primary denominator.
Failures and missing answers count as unsuccessful. This is a counting task
derived from published instance masks, not the dataset's original benchmark score.

| Arm | Counts returned | Within 10% of reference | Conditional MAPE | Complete-cohort MAPE | Mean runtime |
|---|---:|---:|---:|---:|---:|
| Vanilla Astra | 36/36 | 32/36 (88.89%) | 5.62% | 5.62% | 46.92 s |
| Full research-execution harness | 12/36 | 11/36 (30.56%) | 4.95% | Not defined | 749.51 s |

Full minus vanilla within-10% success: **-58.33 percentage points**. The image-cluster bootstrap 95% interval is [-72.22, -44.44] percentage points. The 12 images, rather than their 36 repetitions, are the resampling units.

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
