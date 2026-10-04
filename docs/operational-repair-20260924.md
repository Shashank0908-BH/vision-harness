# Operational fixes: 24 September 2026

These changes address failures in the running `reuse-gpu-repair02` experiment.
They are development changes for the next frozen protocol, not retroactive
changes to that experiment's code, answers, grades, or JEV decisions.

## Observed failures and fixes

| Failure | Cause confirmed from saved traces | Fix |
|---|---|---|
| `image-04__7Detd9G` | Astra mistyped one retrieved source ID (`bf7defdf96b96b736f5` instead of `bf7defdf96b736f5`). | Supply exact candidate-to-source IDs, preserve proposed contracts/errors, allow one correction with the same retrieved evidence. Validate again; never guess or silently replace a citation. |
| `image-10__AdJZBi7` | JSON support cited another candidate's documentation; hashlib support had no citation despite claiming readiness. | Require at least one own retrieved citation for every ready candidate, including ordinary library support. A candidate without sufficient evidence remains unready. |
| `image-03__BbKyLEu`, first round | Disabling TensorFlow soft placement forced the CPU-only `RangeDataset` operation onto GPU:0. A GPU network probe had already passed. | Reject disabling soft placement in a full StarDist prediction program in the GPU environment. Keep CPU data preparation available and check actual network tensor devices for GPU evidence. |
| Same trial, second round | The fallback used `/opt/venvs/torch/bin/python`, where `skimage` was absent; its only setup command checked imports without installing anything. | Measure module availability per interpreter. Require a selected interpreter and pinned installation for known-missing imported distributions before plan scoring. Generate private-target installation with existing runtime constraints; run actual imports before inference. |

TensorFlow documents soft placement as allowing operations to use a compatible
device when their requested device cannot execute them. It does not establish
that the network ran on a GPU; that still needs explicit evidence.
[TensorFlow API](https://www.tensorflow.org/api_docs/python/tf/config/set_soft_device_placement).
The installable distribution is `scikit-image`, while Python imports use
`skimage`. [Installation documentation](https://scikit-image.org/docs/stable/user_guide/install.html).

## File map

| File | Responsibility |
|---|---|
| `src/vision_harness/research_execution/documents.py` | Candidate source allowlists, strict usage validation, one semantic correction, saved proposals/errors. Total retrieval failure produces unready contracts so the existing bounded controller can research again. |
| `src/vision_harness/research_execution/contracts.py` | Plans declare `python_executable` and `install_requirements`. Defaults preserve archived-plan loading; new measured GPU environments require explicit interpreter selection. Default protocol version is now `research-execution-0.3`. |
| `src/vision_harness/research_execution/preflight.py` | Validate known-missing dependency declarations, reject unpinned installs/overrides of measured versions, generate installation and launch commands, test unconditional top-level imports in the selected interpreter, validate the saved report. |
| `src/vision_harness/research_execution/planning.py` | Apply dependency and GPU-placement guards before JEV plan scoring; existing one-repair plan loop can correct invalid proposals. |
| `src/vision_harness/research_execution/executor.py` | Tell Codex to run declared installation, setup, import preflight, then the frozen program; stop after a failed setup/check. Require a passing import report for successful new GPU executions. |
| `infra/daytona/run_harness.py` | Record package metadata and module locations separately for science and Torch without importing GPU libraries during inventory. Expose GPU placement rules. |
| `infra/daytona/reuse/entry.py` | Give each interpreter a separate private package target and explicit `PYTHONPATH`. Shared environments/checkpoints remain read-only. New GPU protocol: `research-execution-reuse-gpu-operational03`. |
| `prompts/astra-research-execution.md` | Explain interpreter-specific dependencies, pinned installs, import checks and GPU placement to the planner. |
| `tests/test_operational_repairs.py` | Regression checks for malformed/foreign/missing citations, bounded retries, failed retrievals, strict GPU placement, missing packages, interpreter/path handling, and preflight reports. |

The selected Python launcher and pinned dependencies are part of the plan sent to
JEV. These checks do not choose a model, tune scientific thresholds, approve an
answer, or substitute a human count. The original 2-round / 48-call / 1,500-second
controller and 420-second execution budgets remain; repair calls and import
checks consume those budgets.

Import preflight is deliberately limited: it checks unconditional module-level
import statements, including `from cellpose import models`. Conditional/dynamic
imports and binary incompatibilities triggered only during inference can still
fail later. Static device guards catch the observed API pattern, not arbitrary
Python control flow. Codex execution remains traced instruction following plus
artifact checks, not a formal proof of shell behavior.

## Validation

- Full local suite: **131 passed**. Ruff passed for `src`, `evals`, `tests`, the
  GPU inventory, and reusable workspace modules.
- Replayed **both actual failed documentation outputs**, using their saved
  retrieved documents and one live Astra correction each. Both corrected outputs
  passed strict validation. No reference labels, grading data or new research
  were supplied. These are development recovery checks, not new accuracy scores.
- Regression evidence and API traces:
  `runs/daytona/operational-repair-20260924/docs-replay-image-04__7Detd9G/`
  and `docs-replay-image-10__AdJZBi7/`.
- Actual workspace validation **passed** after the original benchmark released
  `workspace-run.lock`: private Torch installation, Torch imports, StarDist imports
  and repaired StarDist inference all exited 0. The StarDist replay changed only
  soft placement and its corresponding metadata, using the same official input.
  Shared environments stayed read-only; the old frozen source hashes matched.
- Completed validation: `/root/vision-benchmarks/operational-repair-20260924`
  (former PID **109164**). No sandbox or snapshot was created. `status.json`,
  `checks.json`, logs and `result.json` record the outcome; summary files are on the existing volume
  under `/persist/artifacts/operational-repair-20260924`.

**GPU execution of the repaired program passed**, confirmed on 24 September at
10:30 UTC. Local evidence: `runs/daytona/operational-repair-20260924/workspace-validation-result.json`.
This operational replay does not prove better cohort accuracy or JEV approval.
A new frozen repeated benchmark is needed for that comparison; the completed
36-attempt experiment stays intact.
