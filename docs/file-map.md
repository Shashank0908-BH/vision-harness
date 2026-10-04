# File-by-file review guide

For the connected full workflow, start with the
[implemented research-execution file map](research-execution-v3.md#what-each-module-does).
The [architecture specification](research-execution-harness.md) preserves the original
design and broader targets. The tables below describe the earlier runtimes.

The current repair adds `providers/transport.py` for bounded, recorded transient
request retries; `research_execution` now retains valid counts with explicit
review status when later stages fail. `evals/research_execution/prepare_repair.py`
freezes a complete repeat of the existing cohort and reuses every original
vanilla control. It does not select only failed trials. See the
[repair protocol](research-execution-repair.md) for the changed behavior.
For Daytona, [PERSISTENCE.md](../infra/daytona/PERSISTENCE.md) explains each storage
and lifecycle setting; `infra/daytona/doctor.py` checks access without provisioning.

Read the files in this order: `contracts.py`, `runtime.py`, `selection.py`, `tools/opencv.py`, then the two providers. The interfaces and flow should be understandable before reading packaging or Harbor integration.

## Application

| File | Responsibility | Change it when… |
|---|---|---|
| `src/vision_harness/contracts.py` | Pydantic data formats and provider protocols. Defines typed steps, candidate plans, evidence, assessments and answers. | You want to change what modules exchange. |
| `src/vision_harness/runtime.py` | Coordinates image import, fixed probes, candidate generation, eligibility, Jev selection, execution, answer synthesis and optional review. Saves failures as well as successes. | You want to change execution order or retry behavior. |
| `src/vision_harness/selection.py` | Filters ineligible plans, ranks scores, handles close/uncertain choices, and bounds comparisons. | You want to change selection policy. |
| `src/vision_harness/review_loop.py` | Optional review history, failed-check feedback, operation reuse, observation novelty and call/time budgets. Never reads evaluation labels. | You want to change how the structured loop progresses or stops. |
| `src/vision_harness/config.py` | Validates TOML settings, loads `.env`, resolves key aliases, and defines numeric limits. | You want another setting or credential convention. |
| `src/vision_harness/artifacts.py` | Reads/writes images, hashes input, tracks crop origins, and encodes actual image inputs for Astra. | You want another image format or storage backend. |
| `src/vision_harness/tracing.py` | Writes JSON/JSONL, redacts key values, records requests, responses and ordered events. | You want additional observability. |
| `src/vision_harness/tools/registry.py` | Loads capability descriptions, rejects disabled tools and invalid step references. | You add/remove a callable tool. |
| `src/vision_harness/tools/opencv.py` | Implements fixed probes, color masks, components, watershed, crop and distance. No API calls. | You want to change image-processing behavior. |
| `src/vision_harness/providers/astra.py` | Makes structured Responses requests, logs before parsing, and permits one bounded format retry. Refusals are not retried. No tool execution. | You change OpenAI request handling. |
| `src/vision_harness/providers/jev.py` | Calls TypeSafe's HTTP endpoint for Score/Noul and validates returned assessments. | You change Jev integration. |
| `src/vision_harness/providers/evidence_budget.py` | Fits Jev requests within a conservative byte budget by summarizing component geometry. Preserves counts, quality flags, parameters, questions and answers; full geometry stays in trace artifacts. | You change what evidence Jev receives. |
| `src/vision_harness/cli.py` | Commands, terminal output, step pauses, inspection, and lazy loading of evaluation commands. | You change the user interface. |
| `src/vision_harness/demo.py` | Explicit deterministic stand-ins for offline plumbing tests. Cannot establish model quality. | You extend the credential-free demonstration. |
| `src/vision_harness/__init__.py` | Package description and version. | You release a version. |
| Other `__init__.py` files | Identify provider, tool and evaluation packages; no workflow logic. | You change package structure. |

The initial proposal mentioned separate `policy.py` and `tools/images.py`. In the implementation, policy is concentrated in `selection.py` plus runtime limits; image handling is in `artifacts.py`, with crop execution beside the other OpenCV operations. These avoid duplicate layers at the current scale.

## Configuration and prompts

| File | Responsibility |
|---|---|
| `.env` | Your credentials; ignored, local only. |
| `.env.example` | Blank variable names and alias documentation. |
| `configs/poc.toml` | Exact model IDs, effort, per-call timeout/output limit, round/step limits, selection thresholds and resource paths. |
| `configs/poc-loop.toml` | Opt-in structured-loop experiment: four rounds, 24 provider calls, 600-second admission deadline, five review propositions at the same 0.75 threshold. |
| `configs/capabilities.toml` | Available operations and their requirements/limitations. Adding a description alone cannot add an implementation. |
| `configs/evaluation.toml` | Harbor task directory, modes, repetitions, concurrency and model. |
| `configs/cohort-five.toml` | Frozen five-task comparison: one test-split item per task family and all five modes. |
| `prompts/astra.md` | Astra's instructions for planning, evidence use and final answers. |
| `prompts/jev_plan_score.json` | The shared four-level methodology rubric. |
| `prompts/jev_review.json` | The yes/no proposition and criteria for evidence support. |
| `prompts/jev_review_checks.json` | Four explicit evidence checks with fixed remediation hints. Jev returns a Noul for each; the hints are authored rules, not invented model explanations. |
| `docs/review-loop.md` | Loop design, stopping rules, limitations and CLI commands. |

Changing a rubric may require recalibrating selection/review thresholds. Jev Score is an expected position on descriptive levels; a Noul is a yes-probability. Do not treat these as interchangeable.

## Evaluation

| File | Responsibility |
|---|---|
| `evals/harbor_agent.py` | Installs/checks our CLI in the task environment, invokes it, forwards only required provider credentials, and exports logs after Harbor syncs them. |
| `evals/atif.py` | Converts visible events into ATIF steps, associates calls/results, includes the original image, and validates the exported trajectory. |
| `evals/generate_dataset.py` | Renders synthetic scenes with labels obtained from construction parameters. |
| `evals/build_tasks.py` | Copies an explicit allowlist into each agent image; keeps expected answers and reference solutions outside it. |
| `evals/scoring.py` | Pure Python exact/tolerance/categorical grading; no LLM or perception code. |
| `evals/run.py` | Creates Harbor jobs, one per mode, and reports execution errors. |
| `evals/report.py` | Aggregates rewards, coverage, timing and token counts; separates offline/live runs and reports infrastructure errors. |
| `evals/cohort_report.py` | Builds the paired HTML/Markdown cohort report, checks verifier scores against saved answers, and links each task to its traces. |
| `evals/import_bbbc001.py` | Downloads the complete published six-image microscopy benchmark and human counts, verifies lossless PNG conversion, records source hashes, and freezes the protocol. Creates no synthetic images or labels. |
| `evals/benchmark_report.py` | Uses BBBC001's published count-error metric, keeps incomplete runs unranked, and creates HTML/Markdown reports with every trial trace for the configured modes. |
| `evals/candidate_report.py` | Extracts first/last numerical proposals from existing full-harness traces, scores them independently, and reports review checks and missing coverage without replacing final outputs. |
| `configs/bbbc001.toml` | Fixed six-image/five-mode Harbor run; independent plans, one attempt, concurrency two. |
| `configs/bbbc001-jev-retry.toml` | Separately labeled recovery run for the original Jev context-limit failure after adding evidence budgeting. |
| `configs/bbbc001-recovery-v2.toml` | Second, separately labeled recovery run after the first recovery exposed malformed Astra planning output; includes the bounded format-retry fix. |
| `configs/bbbc001-full-repaired.toml` | Requested final comparison: all six images, vanilla versus the repaired full harness. Retains both Jev selection and answer review; skips other ablations. |
| `configs/bbbc001-loop.toml` | Separate six-image vanilla/full retest using the opt-in loop runtime config, with all old results preserved. |
| `configs/bbbc001-no-review.toml` | Fresh comparison of vanilla, Astra + OpenCV, and Astra + OpenCV + Jev selection on the six original images. Uses the original POC settings and excludes answer review. |
| `evals/README.md` | Experimental protocol, interpretation and leakage controls. |

A generated task's `instruction.md` is the question, `task.toml` contains Harbor settings, `environment/Dockerfile` builds the runtime, `environment/input.png` is the input, `tests/expected.json` is verifier-only ground truth, `tests/score.py` and `tests/test.sh` grade outputs, and `solution/solve.sh` is a reference answer for task validation.

## Tests and packaging

| File | Responsibility |
|---|---|
| `tests/conftest.py` | Known synthetic image and configuration fixtures. |
| `tests/test_tools.py` | Counts, pixel areas, boxes, distance, crop offsets, and invalid requests. |
| `tests/test_runtime.py` | Mode isolation, round budgets, frozen plans, selection decisions, errors and evidence references. |
| `tests/test_review_loop.py` | Feedback propagation, per-check acceptance, duplicate operations, lack of new observations, call/time budgets, and structured Jev HTTP contracts. |
| `tests/test_providers.py` | Mocked HTTP contract tests using the actual SDK/HTTP adapters. No paid calls. |
| `tests/test_evaluation.py` | Grading edge cases, deterministic datasets, task isolation, and ATIF validation. |
| `pyproject.toml` | Package metadata, dependencies, CLI entry point, test/lint settings. |
| `uv.lock` | Resolved dependency versions across supported platforms. |
| `requirements-runtime.txt` | Generated, hashed runtime dependency export for task Docker images. Refresh after changing dependencies. |
| `.python-version` | Python 3.12 selection for uv. |
| `.gitignore` | Excludes keys, virtual environments, caches and generated output. |
| `examples/shapes.png` | An inspectable synthetic counting input. |
| `examples/components.json` | Standalone OpenCV request for that image. |

## Generated evidence

The optional [StarDist harness](stardist-harness.md) adds a lazy specialist adapter and dispatcher, separate capability/prompt/runtime files, pinned container dependencies and checkpoint packaging. The linked file table explains each addition. `configs/bbbc001-stardist.toml` compares vanilla, Astra + StarDist and the complete StarDist/Jev loop in Harbor.

The [adaptive StarDist experiment](adaptive-stardist.md) removes default-first guidance and adds condition-based Jev selection/review. Its file table covers the separate prompts/configuration, BBBC039 importer, fixed adapter control and `evals/adaptive_report.py` report generator. Previous configurations remain reproducible.

The detachable `experiments/microscopy/` directory evaluates pretrained perception without Astra/Jev. `worker.py` creates masks and measurements from image-only requests; `evaluate.py` freezes inputs, runs workers, independently scores counts and builds reports. Separate pinned dependency files and environments isolate Cellpose/PyTorch from StarDist/TensorFlow. See its README for commands and output files. These native specialist trials are separate from Harbor harness evaluations.

`runs/<id>/manifest.json` records effective settings, resource hashes and versions. `events.jsonl` records ordered events. `calls/` contains provider request/response JSON. `plans-N.json` is reusable for a controlled selection comparison. `answer.json` is the final machine-readable result. `artifacts/index.json` records image dimensions, hashes and original-image offsets; PNGs contain the actual visual evidence.

With the optional loop, `loop-history.json` records plans, selections, evidence IDs, candidate answers and per-check reviews by round. `review_feedback`, `tool_reused` and `loop_stopped` events explain subsequent decisions. Provider-call guards count actual adapter calls, including format retries; the deadline prevents starting more work and does not cancel an in-flight request.

`jobs/<job>/<trial>/agent/trajectory.json` is the Harbor viewer trace. The adjacent `agent/run/` holds the original harness trace. `verifier/reward.json` holds independent scores. A task's `result.json` and `trial.log` describe Harbor execution status.

`research/` and `vision-harness-study-guide.html` predate this implementation and provide the broader study material. Their claims are not automated evidence that this harness works.

The separate specialist-routing path is documented in
[model-routing.md](model-routing.md): versioned StarDist/Cellpose-SAM procedures,
source-backed research proposals, Jev scoring of every eligible procedure, isolated
workers, and a later label-based comparison. The historical runtime above is unchanged.

The reusable GPU benchmark adapter is documented in
[infra/daytona/reuse/README.md](../infra/daytona/reuse/README.md), with a file-by-file
map and CLI commands. Its Harbor coordinator runs inside the existing Daytona
workspace, isolates each attempt's files and processes, and checkpoints completed
traces to the mounted volume. It does not change the frozen local CPU repair run.

The [24 September operational repair](operational-repair-20260924.md) documents
strict documentation repair, interpreter-specific dependencies and import
preflight, GPU-placement guards, regression evidence and queued workspace replay.
