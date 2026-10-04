# Research-execution POC: implementation and review guide

This is the connected workflow requested for the next experiment. It uses
`gpt-6-astra` for task interpretation, web research, documentation reading,
program generation, Codex execution and visual inspection. `jev-1.13.0` scores
candidate–requirement pairs, complete programs and observed outputs, and reviews
whether the evidence supports stopping. The numerical benchmark score comes
from an independent reference-mask grader, never from Jev confidence.

Live validation completed through a real measured answer and separate Harbor
grading. The development prefix replay exercised Jev plan scoring, Codex inference,
artifact checks, Astra visual inspection, output scoring, Noul review and renewed
research. Second-round plans failed coverage validation; the first reviewed
answer and matching mask were preserved as `provisional_after_error`. This is a
successful recovery check, not an accuracy claim or two successful executions.
The held-out comparison is now being frozen and launched; no v3 score is reported
until all planned attempts finish. A separately labeled 96 KB transport-budget
follow-up is also running after a development-only probe showed that the original
48 KB local guard rejected requests the service accepts. It adds 36 fresh full
runs and reuses the original 36 baselines: 108 unique trials across both comparisons.
See the [pre-unblinding amendment](../reports/research-execution-20260922/transport-amendment.md). See the [development record](../reports/research-execution-20260922/development-status.md).

The overnight runs were interrupted by repeated host sleep, confirmed in
[macOS sleep/wake logs](../reports/research-execution-20260922/host-sleep-events.txt).
Their attempts and errors are retained, but they cannot establish a clean
accuracy or latency comparison. A complete infrastructure repeat is frozen as
[`test-awake96`](../reports/research-execution-20260922/test-awake96/selection.json):
the identical 96 KB task environments, 12 images × three runs × two arms, with
36 fresh vanilla controls and 36 fresh full-harness trials. No reference accuracy
was inspected before deciding to repeat the experiment. The host must remain
awake; the temporary sleep inhibitor cannot prevent lid-close sleep.

## What each module does

All application paths below are inside `src/vision_harness/research_execution/`.

| File | Responsibility | Review or change this when… |
|---|---|---|
| `contracts.py` | Typed task, candidate, usage, plan, execution and review records; bounded policy. | You want another task type, output format or budget. |
| `runtime.py` | Stage packets, original-query preservation, orchestration, feedback, two-round stopping and final artifact publication. | You want to change the order of decisions or repair behavior. |
| `discovery.py` | Live web research and a request-specific catalog tied to consulted sources and requirement IDs. | You want different research breadth or source rules. |
| `scoring.py` | Every candidate's applicable roles, candidate retention, all-plan scoring, observed-output scoring and Noul review. | You want to change ranking, rubrics or stopping support. |
| `documents.py` | Fetches public documentation, preserves pages and hashes, extracts usage contracts with source IDs. | You want deeper document navigation or other document formats. |
| `planning.py` | Competing executable Python programs; checks candidate IDs, documentation, coverage and syntax. | You want stronger static plan checks. |
| `executor.py` | Runs actual Codex CLI inside the isolated task container; preserves shell events, errors and program hashes. | You want another execution backend or stronger execution-policy enforcement. |
| `evidence.py` | Reads original pixels, checks instance-map geometry and IDs, counts labels, flags fragmentation and renders an overlay. | You want additional independent image checks. |
| `replay.py` | Hash-checked development-only replay of completed research and plans; forbidden in the test benchmark. | You need to debug later stages without repeating a valid prefix. |
| `cli.py` | Runs one fresh trial in a chosen arm. | You want CLI arguments or operator controls. |

| Evaluation file | Responsibility |
|---|---|
| `evals/research_execution/Dockerfile` | Input-free scientific/Codex base environment; CPU deployment. |
| `toolchain.py` | Builds/checks that environment and performs a minimal live Codex health check. |
| `prepare.py` | Selects unused official-test images before reading labels, freezes source hashes, checks reference decoding independently and builds tasks. |
| `harbor_agent.py` | Runs the same application CLI inside Harbor and exports visible events into validated ATIF trajectories. |
| `verifier.py` | Runs in a fresh, separate verifier container. Checks mask-derived counts and computes count error and instance F1. |
| `run.py` | Checks the frozen source/image identities and launches every planned repetition without outcome retries. |
| `status.py` | Shows stages, elapsed time and failure types while keeping reference scores hidden during the run. |
| `report.py` | Collects all attempts, computes coverage/error/success and image-cluster uncertainty, and creates a paginated trace report. |
| `tests/test_research_execution.py` | Checks requirement scoring, feedback flow, source provenance, measurement and evaluation boundaries. These fixtures are not benchmark data. |

Configuration is in `configs/research-execution.toml`; the scientific-program
contract is in `prompts/astra-research-execution.md`. Existing API adapters and
secret-redacting trace utilities are reused. The older experiments are preserved.

## What the query looks like at each stage

The original question is always retained unchanged. The intake stage turns it
into explicit requirements with acceptance checks. Later requests contain:

```json
{
  "protocol": "research-execution-0.1",
  "stage": "plan_scoring",
  "original_query": "Count the nuclei ... including visible border nuclei.",
  "stage_job": "Score every complete plan, including its executable code and previous review conditions.",
  "expected_output": "all plan scores",
  "task": {"requirements": ["structured IDs, purposes and checks"]},
  "observed_input": {"shape": [520, 696], "dtype": "uint16"},
  "environment": {"accelerator": "CPU only"},
  "feedback": ["actual prior failures, review scores and missing evidence"],
  "context": {"usage": "source-backed model input and output contracts"}
}
```

This is an explanatory shortened example, not the exact schema. The full packets
are saved in each trial's `agent/run/stage-packets/` directory. Candidate scores
are indexed by both candidate ID and requirement ID. Requests are split by their serialized size without dropping candidate subjects
or truncating executable plans. Selecting a good file-reader
does not make it a good segmentation model: role scores are ranked separately.

## The measured comparison

The primary pilot uses 12 previously unused images from BBBC039's official
50-image test split, excluding the 12 test images already used by earlier runs.
Selection is deterministic and independent of reference counts. Each arm gets
three fresh runs per image: **36 vanilla and 36 full-harness attempts**.

Both arms receive the same question and the same 1st/99.8th-percentile display
preview, without spatial resizing. The harness additionally reads the original
16-bit TIFF and can use models and Python libraries. This compares the complete
capability package, including extra inference, rather than isolating Jev's effect.
No benchmark labels, source filenames or previous result reports are placed in
the agent image. Harbor stops the agent and runs grading in a separate container.

Primary outcome: proportion of all planned attempts within 10% of the
annotation-derived count. Missing answers and failures count as unsuccessful.
Secondary outcomes: coverage, conditional MAPE, complete-cohort MAPE only when
all attempts answer, instance F1 for actual masks, runtime and token use. Repeated
observations of the same image are not independent images; uncertainty resamples
images after averaging their repetitions.

The full arm publishes a measured count with `approved` or `provisional` review
status. Failure to obtain a final scored/reviewed execution is an error, not a Jev
rejection. The grader checks that the final count matches the final saved mask.
Provisional outputs remain provisional even if they happen to grade well.

## Running and reviewing

```bash
# Build once; needs Docker and public dependency downloads.
.venv/bin/python -m evals.research_execution.toolchain build
.venv/bin/python -m evals.research_execution.toolchain health

# Development uses an official validation image, never the held-out test cohort.
.venv/bin/python -m evals.research_execution.prepare --split dev-example
.venv/bin/python -m evals.research_execution.run --split dev-example --concurrency 1

# Freeze only after development checks, then run all recorded attempts.
.venv/bin/python -m evals.research_execution.prepare --split test
.venv/bin/python -m evals.research_execution.run --split test --concurrency 4
.venv/bin/python -m evals.research_execution.status --split test --summary
.venv/bin/python -m evals.research_execution.report

# Existing Harbor traces can also be inspected in Harbor's UI.
.venv/bin/harbor view jobs
```

A development replay is explicitly marked as a partial replay, never an independent
full trial. The held-out task builder rejects that option; each benchmark repetition
performs its own research, scoring, documentation and execution.

These commands intentionally refuse to overwrite frozen cohorts or silently
repeat completed jobs. For a separately labeled follow-up experiment, use a new
protocol and selection rather than replacing unfavorable outcomes.

## Current limits

- This implementation supports 2D fluorescence nucleus counting. It is not yet
  a general DICOM/fMRI framework or a persistent universal model catalog.
- Research has a finite search and catalog budget. “All candidates scored” means
  all candidates actually discovered in this run, not all models on the internet.
- Documentation retrieval currently supports HTML/plain text, three pages per
  retained candidate, and labeled excerpts. Full pages are preserved, but a
  model reading an excerpt has not read an entire documentation site. Unresolved
  required usage information must block that candidate or trigger more research.
  Readiness means a documented, testable procedure; it does not require proving
  accuracy or runtime before inference. Standard array and file operations are
  checked by executable assertions rather than requiring a web page per function.
- Codex runs Linux shell/Python inside Docker, not arbitrary host macOS access.
  The scientific program is frozen and checked after execution; the instruction
  to run only that program is not a formal semantic execution proof. Shell traces
  are available for review. No host filesystem or Docker socket is exposed.
- Jev receives structured text and attributed visual observations. It does not
  independently view the pixels. Its scores are decision evidence, not validated
  probabilities that the count is correct.
- The two-round, 48-controller-call, 25-minute budget bounds investigation.
  Call capacity allows renewed research and lossless scoring batches in round two;
  Codex internal turns are logged separately from controller calls. It cannot
  guarantee enough time to install or run every possible specialist.
- Public test images may have appeared in model pretraining. This pilot cannot
  establish general multimodal superiority or clinical performance.
