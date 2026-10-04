# Research-execution repair repeat

The previous `test-awake96` full arm returned 17 of 36 final counts. None of the
19 missing answers reached final JEV review. Six had already produced valid
masks, but execution/replanning errors prevented a final handoff. The failure
audit is preserved in `reports/research-execution-20260922/test-awake96/`.

## Changes and review locations

| Location | Change |
|---|---|
| `src/vision_harness/providers/transport.py` | Retries transient network/service failures once when enabled, respects bounded server retry delays, records failures and counts each retry toward the provider-call budget. Authentication, billing and quota failures are not retried. |
| `providers/astra.py`, `config.py`, `configs/research-execution.toml` | Wire the bounded transport policy into requests. Older configurations default to zero additional retries. |
| `research_execution/discovery.py` | Records incomplete web research and permits one larger output allowance after token-limit truncation. Validates unique candidate IDs and consulted source URLs, with one semantic repair opportunity. |
| `research_execution/runtime.py`, `planning.py` | Expose verified installed StarDist 0.9.2 loader/API facts. Validate known incompatible generated calls before execution; do not choose thresholds or force a specialist based on benchmark labels. |
| `research_execution/contracts.py`, `executor.py` | Require program exit status. Successful frozen execution and existing artifacts proceed to independent checking, with the executor's visual concerns retained for review. |
| `research_execution/evidence.py`, `runtime.py` | Check artifact shape, dtype, count, provenance and execution report. Save validated measurements before downstream review. Preserve a measured count if review fails, explicitly marking it unreviewed. |
| `evals/research_execution/report.py` | Show unreviewed output coverage separately from outputs that completed JEV review. Neither provisional nor unreviewed means approved. |
| `evals/research_execution/prepare_repair.py` | Copy all 12 original tasks, verify input/reference hashes, refresh only the agent application, freeze current source, and alias all 36 existing vanilla attempts. |

The existing two-round, 48-call, 1,500-second controller limits remain. Internal
repair calls consume those limits. The original specialist image, model IDs,
question, input images and reference labels remain fixed. No whole-trial retries
are selected by accuracy. This changes reliability and the answer policy, so
raw count coverage must be distinguished from successful completion of all
review stages.

## Validation and execution

The repair tests cover transient retries, catalog repairs, output handoff,
StarDist call compatibility, preserved review status and report denominators.
An offline forward pass on an official validation image confirmed the installed
StarDist loader and `predict_kwargs={"b": 0}` invocation work. That inference is
an API compatibility check, not evidence of improved benchmark accuracy.

`dev-repair01` stopped at Docker preflight before model calls: Docker Desktop
listed and ran the tag but failed to inspect it by tag. Preflight now separately
verifies tag-to-digest mapping and inspects the immutable digest. `dev-repair02`
is a fresh full-chain trial on the same official validation image.

After the development trial reaches final review, the intended repeat is:

```bash
.venv/bin/python -m evals.research_execution.prepare_repair --split test-repair01
.venv/bin/python -m evals.research_execution.run --split test-repair01 --arms full --concurrency 4
.venv/bin/python -m evals.research_execution.report --split test-repair01
```

This is **36 new full-harness attempts**, 12 images × 3 fresh runs, compared with
all 36 original vanilla attempts. The reused controls include their failure.
The old 17/36 result is preserved. This is a post-hoc repair study on an already
inspected cohort, not a new held-out result or a controlled speed comparison.

The separate 50-image Daytona benchmark has its own frozen source and policies.
These edits do not change that running experiment, move its local coordinator
into the cloud, or provision persistent cloud storage.
