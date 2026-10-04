# Rejected candidate counts: measured against published annotations

Extracted directly from the completed full-harness event logs. No new model calls. Every image contributes its last proposed numerical count; the first attempt is reported separately, with no best-of-two selection.

| Output being measured | Images | Mean percentage counting error ↓ | Difference from vanilla |
|---|---:|---:|---:|
| Vanilla final counts | 6 | 10.30% | — |
| First proposed count | 6 | 13.71% | +3.42 percentage points |
| Last proposed count before final rejection | 6 | 14.49% | +4.19 percentage points |

Error is calculated against the mean of the two published human counts for each image, then averaged over all six images. It is not classification accuracy.

| Image | Human counts | Reference mean | Vanilla count (error) | First candidate (error) | Last candidate (error) | Jev support, first → last |
|---|---|---:|---:|---:|---:|---:|
| BBBC001 field 1 | 350, 362 | 356 | 400 (12.36%) | 390 (9.55%) | 370 (3.93%) | 0.10 → 0.27 |
| BBBC001 field 2 | 336, 342 | 339 | 370 (9.14%) | 370 (9.14%) | 380 (12.09%) | 0.09 → 0.10 |
| BBBC001 field 3 | 396, 447 | 421.5 | 475 (12.69%) | 510 (21.00%) | 510 (21.00%) | 0.08 → 0.11 |
| BBBC001 field 4 | 320, 341 | 330.5 | 340 (2.87%) | 355 (7.41%) | 365 (10.44%) | 0.09 → 0.08 |
| BBBC001 field 5 | 398, 533 | 465.5 | 560 (20.30%) | 590 (26.75%) | 610 (31.04%) | 0.07 → 0.09 |
| BBBC001 field 6 | 241, 257 | 249 | 260 (4.42%) | 270 (8.43%) | 270 (8.43%) | 0.08 → 0.12 |

The last proposed counts have **14.49% mean error**, versus **10.30% for vanilla**: 4.19 percentage points worse, or 40.7% higher relative error. They are closer on 1 image, worse on 5, and tied on 0.

Jev therefore blocked some reasonably close estimates as well as poorer ones. However, releasing all last candidate counts would still have produced worse average counting error than vanilla on this cohort. Low evidence support does not itself establish that a count is incorrect.

These are candidate scores, not accepted full-harness outputs. All six recorded final outputs remain abstentions. The second attempts used Jev feedback; this is not a new run with Jev disabled. This small retrospective comparison does not isolate the causal effect of Jev or establish performance on other datasets.

## Audit trail

Each source log contains the candidate answer followed by its review. Exact event sequence numbers, original answer objects and source-file SHA-256 hashes are preserved in [candidate-counts.json](candidate-counts.json).

- [BBBC001 field 1 event log](../../jobs/bbbc001-full-repaired-20260922/live-full-20260922-044133-424219/72e37a64aca1__eVuGFsc/agent/run/events.jsonl)
- [BBBC001 field 2 event log](../../jobs/bbbc001-full-repaired-20260922/live-full-20260922-044133-424219/f78a1dcba6ae__2wtnooH/agent/run/events.jsonl)
- [BBBC001 field 3 event log](../../jobs/bbbc001-full-repaired-20260922/live-full-20260922-044133-424219/51680b6440c6__SZnoULF/agent/run/events.jsonl)
- [BBBC001 field 4 event log](../../jobs/bbbc001-full-repaired-20260922/live-full-20260922-044133-424219/0bb54dcc4ca2__AWKywQB/agent/run/events.jsonl)
- [BBBC001 field 5 event log](../../jobs/bbbc001-full-repaired-20260922/live-full-20260922-044133-424219/126aeb4762e7__fZ6mAhq/agent/run/events.jsonl)
- [BBBC001 field 6 event log](../../jobs/bbbc001-full-repaired-20260922/live-full-20260922-044133-424219/2b3b6cf9e3af__gMgyRqu/agent/run/events.jsonl)

[Original accepted-output score](final-score.md) · [Original report and traces](index.html)
