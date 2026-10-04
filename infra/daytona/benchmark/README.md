# Full BBBC039 comparison on Daytona

This experiment compares **vanilla Astra**, **fixed pretrained StarDist**, and
**the complete research → JEV candidate scoring → documentation → planning →
JEV plan scoring → execution → inspection → JEV review/replanning harness**.

The cohort is all **50 images in the published BBBC039 test split**, with three
fresh attempts per arm and image: **450 scored attempts**. One separate official
validation image exercises all three arms before the main queue starts. It is
excluded from test scores. No artificial microscopy problems are used.

Source: https://bbbc.broadinstitute.org/BBBC039

## Files you can review

| File | Responsibility |
|---|---|
| `prepare.py` | Freezes cohort membership before opening masks; copies immutable code and inputs; independently checks reference decoding; creates Harbor tasks/configs. |
| `agent.py` | Harbor adapter for the three arms; uploads only code and current input, supplies only needed provider credentials, exports ATIF traces. |
| `environment.py` | Bounds remote metadata/log/file operations and retries idempotent infrastructure calls; uses bounded shell file checks. Never retries inference. |
| `stardist.py` | Fixed StarDist control: original uint16 TIFF, 1/99.8 percentile normalization, native resolution, checkpoint defaults, border nuclei included. No LLM/JEV calls. |
| `Dockerfile` | Identical scientific environment for every agent attempt; TensorFlow and PyTorch in separate virtual environments; unprivileged researcher. |
| `launch.py` | Checks frozen hashes, runs the validation infrastructure check and then the 450-attempt Harbor job, refreshes reports every minute. |
| `collect.py` | Aggregates every finished attempt, shows pending work, computes means, pass@3, segmentation F1, exposure sensitivity and paired bootstrap intervals. |
| `../run_harness.py` | Reports measured GPU/CPU/RAM and applies the preregistered long-horizon budgets to the existing harness. |

The corrected run lives in `runs/daytona/bbbc039-full-20260923-bootstrap5/`.
The original `runs/daytona/bbbc039-full-20260923/` preserves a failed setup run:
no test inference started there. `runs/daytona/current-experiment.json` points to
the active coordinator. `infrastructure-revision.json` records the bootstrap
changes; the cohort, scientific code, model parameters and grading logic are
unchanged. `bootstrap2` verified real Astra inference but caught a missing
`COPY . /tests` in the separate verifier's Dockerfile; `bootstrap3` includes it.
`bootstrap4` adds bounded connector operations after an artifact handoff stalled.
The adapter retrieved that existing answer, and the separate grading container
produced a valid reward before the new queue launched. These are infrastructure
validation attempts; none are included in the 450-attempt test cohort.
`bootstrap4` completed Astra inference, grading and artifact export end to end.
Its StarDist launcher exposed a Python filename collision with the installed
package; `bootstrap5` uses module execution to remove that collision. The fixed
StarDist model, preprocessing and thresholds are unchanged.

The experiment directory contains:

- `selection.json`: cohort, thresholds, budgets, assumptions and model checksum.
- `source-manifest.json`, `task-manifest.json`: SHA256 hashes of frozen materials.
- `frozen/`: code snapshot; parent-thread edits cannot alter this run.
- `tasks/test/`: 50 Harbor tasks. `environment/` contains no reference labels;
  `tests/` contains hidden references for a separate verifier.
- `jobs/test/<trial>/agent/trajectory.json`: Harbor ATIF trace.
- `jobs/test/<trial>/agent/run/`: stage packets, candidates, JEV scores, plans,
  execution logs, masks, inspection and review outputs.
- `jobs/test/<trial>/verifier/grading.json`: reference-based grading.
- `test-summary.md`: readable progress/results.
- `test-summary.json`: all individual counts, errors, stages and aggregates.
- `launcher.log`, `launcher.json`: detached coordinator log and PID.

## What the scores mean

**Pass** means a valid count within **10%** of the annotation-derived count,
including the boundary. For the tool arms, the count must agree with the saved
instance map. Segmentation F1 is measured separately at IoU ≥ 0.5.

**Mean pass score** is the fraction of all attempts that pass. A timeout,
abstention, API failure, invalid output or missing mask scores zero. Failures
remain visible by stage and are not called JEV rejections.

**pass@3** is the fraction of images for which at least one of the three attempts
passes. With exactly three attempts, no estimator is needed. This is an
evaluation measure that uses ground truth to identify success; it does not prove
the harness can select the best of its three answers without ground truth.

**MAPE** is average absolute percentage count error. Conditional MAPE uses valid
answers and must be read with coverage. Full-cohort MAPE is undefined if an answer
is missing. We also report mean-count ensemble error when all three counts exist,
and a separately named clipped count score, `max(0, 1 - percentage_error/100)`,
with failures set to zero. These are not interchangeable with pass rate.

Partial reports cover completed attempts only. Partial pass@3 includes only
images with all three attempts finished. The final uncertainty intervals resample
images as paired clusters; 150 attempts do not become 150 independent images.

StarDist's fixed inference may give identical masks three times. Those repeated
executions check reproducibility and timing, not extra independent accuracy
evidence. Some test images were used in earlier project pilots, so the report
also separates previously selected images. Public pretrained exposure is unknown.

## Budgets, isolation and persistence

- Astra: `gpt-6-astra`, medium reasoning; JEV: `jev-1.13.0`.
- Four harness rounds, two research passes, 96 controller calls, 7,200 seconds
  per attempt, 1,200 seconds per Codex execution; no outcome retries.
  This research workflow uses its explicit `Policy`; the older POC's
  `[loop].enabled` setting does not disable these research/replanning rounds.
- Each agent attempt has a fresh RTX 4090 container, 8 vCPU, 32 GiB RAM and
  80 GiB allocated storage. One agent trial runs at a time initially.
- The Daytona toolbox starts as root so Harbor can create directories and switch
  users without an interactive password prompt. Agent execution explicitly uses
  `researcher` (UID 1000); install-time checks verify both identities.
- Every attempt starts with the same image environment. Method/package choices
  made inside a full-harness attempt do not persist into another attempt.
- Verification runs in a separate CPU container. No reference labels are placed
  in the agent image or sent to an LLM/JEV provider.
- Harbor downloads logs and output artifacts to this computer. It then stops
  ephemeral workers. The key permits stop but denies explicit delete; Daytona's
  automatic deletion after stop has been checked independently.
- Custom persistent volumes and named snapshots are not required by this
  execution path. Dockerfile sandbox builds use Daytona's supported image build
  and cache mechanism: https://www.daytona.io/docs/en/declarative-builder/
- Keep the local coordinator online. `caffeinate` prevents idle sleep while it
  runs, but closing the laptop/rebooting/network loss can still interrupt it.
  Completed local artifacts survive deletion of cloud workers. In-flight outputs
  are only durable after Harbor downloads them.
- Idle shutdown is 150 minutes, longer than the maximum attempt. The warm lab
  created earlier is separate and is not the worker for these fresh trials.

At the checked rate, this GPU configuration is about **$1.92 per active hour**,
plus model APIs. If every full-harness attempt consumed its two-hour budget, that
arm alone would use 300 GPU-hours, approximately $576 before API calls and setup.
This is a ceiling from the configured time budget, not an expected runtime or a
spend cap. Observe the actual first trials before increasing concurrency.

## Inspect and resume

From the project root, refresh a report without changing running jobs:

```sh
PYTHONPATH=src:. runs/daytona/benchmark-venv/bin/python -B \
  -m infra.daytona.benchmark.collect runs/daytona/bbbc039-full-20260923-bootstrap5
tail -n 30 runs/daytona/bbbc039-full-20260923-bootstrap5/launcher.log
```

The actual launch runs from `frozen/` with that directory and its `src/` on
`PYTHONPATH`. Do not start a second coordinator while its recorded PID is alive.
Harbor can resume the same job/config, retaining completed trials. Inspect any
interrupted trial and remote worker before resuming; do not silently replace a
failed attempt with a successful retry. No benchmark arm or scientific parameter
should change midway through this frozen experiment.
