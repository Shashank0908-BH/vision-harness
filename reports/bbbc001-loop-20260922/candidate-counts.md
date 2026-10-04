# Proposed counts before final review

First and last numerical candidate per image, regardless of error or review score. No best-of-N selection. An unreviewed candidate is explicitly marked by the absence of a review.

Mean over all six images of 100 * abs(prediction - mean(two human counts)) / mean(two human counts); lower is better.

| Output | Numerical counts | Full-dataset error ↓ | Candidate-subset error | Vanilla on that subset |
|---|---:|---:|---:|---:|
| Vanilla final answers | 6/6 | 11.64% | — | — |
| first numerical candidate | 6/6 | 14.09% | 14.09% | 11.64% |
| last numerical candidate | 6/6 | 14.56% | 14.56% | 11.64% |

| Image | Reference | Vanilla | Proposed numerical counts by round | Actual final status |
|---|---:|---:|---|---|
| BBBC001 field 1 | 356 | 390.0 | r1: 390 (9.55% error); r2: 400 (12.36% error) | error |
| BBBC001 field 2 | 339 | 385.0 | r1: 390 (15.04% error) | error |
| BBBC001 field 3 | 421.5 | 480.0 | r1: 500 (18.62% error) | abstained |
| BBBC001 field 4 | 330.5 | 360.0 | r1: 365 (10.44% error) | abstained |
| BBBC001 field 5 | 465.5 | 545.0 | r1: 570 (22.45% error); r2: 570 (22.45% error) | abstained |
| BBBC001 field 6 | 249 | 266.0 | r1: 270 (8.43% error) | error |

Candidate scores do not replace actual final outputs. Later proposals depend on previous review feedback, so this is not a run with Jev disabled. Missing candidates have no full-dataset error; matched-subset metrics are separately labeled.

Exact checks, event sequence numbers, trace hashes, and stopping reasons are in [candidate-counts.json](candidate-counts.json).

## Source traces

- [BBBC001 field 1](../../jobs/bbbc001-loop-20260922/live-full-20260922-053122-422256/72e37a64aca1__xpNvnLT/agent/run/events.jsonl)
- [BBBC001 field 2](../../jobs/bbbc001-loop-20260922/live-full-20260922-053122-422256/f78a1dcba6ae__mFt95AZ/agent/run/events.jsonl)
- [BBBC001 field 3](../../jobs/bbbc001-loop-20260922/live-full-20260922-053122-422256/51680b6440c6__nj3E4vo/agent/run/events.jsonl)
- [BBBC001 field 4](../../jobs/bbbc001-loop-20260922/live-full-20260922-053122-422256/0bb54dcc4ca2__LWoRXFy/agent/run/events.jsonl)
- [BBBC001 field 5](../../jobs/bbbc001-loop-20260922/live-full-20260922-053122-422256/126aeb4762e7__R7w8CUE/agent/run/events.jsonl)
- [BBBC001 field 6](../../jobs/bbbc001-loop-20260922/live-full-20260922-053122-422256/2b3b6cf9e3af__TJU7fqN/agent/run/events.jsonl)

[Accepted-output report](index.html) · [Findings](findings.md)
