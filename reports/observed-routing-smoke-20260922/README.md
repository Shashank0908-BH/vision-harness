# Observed-output routing v2: integration smoke test

The new `vision specialist compare` path completed on one previously inspected
BBBC001 development image. This verifies integration only. No reference count was
decoded or used for this smoke test, and no accuracy gain is claimed.

| Check | Result |
|---|---|
| Hosted calls | 3 Astra + 2 Jev; all five responses recorded |
| Specialist executions | All four completed |
| Candidate observations | All five candidates described once |
| Jev scores | All five valid candidates scored |
| Independent vanilla | Saved before intent interpretation and specialist outputs |
| Selected count | Copied exactly from the selected saved candidate |
| Review | Completed; supported status is uncalibrated |
| Harbor | ATIF trajectory validates |
| Retries / failed candidates | Zero / zero in the completed run |
| Runtime | 111.1 seconds, including model initialization |

Jev selected Cellpose-SAM's count of 387, with selection score 2.20/3 and review
Noul 0.79. Vanilla proposed 490; StarDist default/sensitive/conservative proposed
375/378/370. These are **unscored observations**, not a leaderboard or a finding
that Jev selected the most accurate candidate.

The [verification record](verification.json) includes source/catalog hashes,
candidate values, scores and integrity checks. Full local artifacts are under
[`runs/observed-v2-smoke-network-20260922`](../../runs/observed-v2-smoke-network-20260922),
including the [decision](../../runs/observed-v2-smoke-network-20260922/decision.json),
[visual observations](../../runs/observed-v2-smoke-network-20260922/inspection.json),
and [trace](../../runs/observed-v2-smoke-network-20260922/trajectory.json).
An actual-credential scan found no leaked key values in 46 run text files.

The first attempt was blocked by the network-restricted sandbox. Its API connection
errors remain under `runs/observed-v2-smoke-20260922`. After network permission,
the entire smoke run used a new output directory. This was an infrastructure
recovery, not a discarded poor accuracy result.

The suite passes 87 tests, including independent candidate inputs, exact count
grounding, checksum/count/coordinate failures, missing/duplicate candidate
judgments, provider failures, abstentions, unsupported tasks, high-bit-depth
rejection, budget enforcement, the actual Jev request format via a mock transport,
and Harbor trace export. Tests use explicit stand-ins; only the run above used
live APIs and specialist weights.

Next capability evaluation: a new frozen external cohort, at least three runs per
task, fixed specialists and vanilla controls, failure-aware accuracy and coverage,
and selection/review ablations. The completed Kromp test has already informed
this design and must not be presented as fresh held-out evidence after tuning.
