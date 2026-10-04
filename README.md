# Vision harness

[Publication testing and experiment index](docs/publication-testing.md) · [MIT license](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)

A CLI-first research POC: GPT-6 Astra proposes and interprets vision operations, specialist adapters produce measurements, and Jev can score proposed methods and review the evidence behind an answer. StarDist handles fluorescence-nucleus segmentation; the original OpenCV tools remain available in separate configurations. Harbor runs isolated tasks and displays execution traces.

**Current scope:** the connected research/execution harness supports **2D fluorescence microscopy nucleus counting**. The intended architecture is general-purpose, but general images, DICOM/fMRI, video and audio do not yet have domain adapters. The older OpenCV tools remain separate examples, not proof of general-purpose support.

**For team development, start with [the team handoff](docs/team-handoff.md):** implementation boundaries, the current architecture diagram, file responsibilities, local setup and the proposed separation between a shared controller and domain adapters.

The connected flow is query-driven model/library research → JEV candidate scoring → retrieved usage documentation → Astra executable plans → JEV plan scoring → isolated execution → evidence review and bounded replanning. See the [architecture specification](docs/research-execution-harness.md) and [v3 implementation guide](docs/research-execution-v3.md).

The [completed GPU repeat](reports/research-execution-20260922/test-gpu-repair02/summary.md) returned 33/36 harness answers versus 35/36 vanilla answers. Both scored 31/36 within 10% of the true count; conditional mean count error was 4.63% versus 5.75%. All 33 harness answers remained provisional. This was a post-hoc repair comparison on 12 previously inspected images, not evidence of general multimodal superiority. The subsequent [operational fixes](docs/operational-repair-20260924.md) are in development source and passed targeted validation; they have not been evaluated in a new full cohort. Earlier frozen experiments and their reports remain preserved.

The new **specialist routing layer** has a [complete file map and CLI guide](docs/model-routing.md): versioned StarDist/Cellpose-SAM procedures, source-backed model research, Jev scoring of every eligible candidate, frozen decisions, and inspectable instance-map evidence. Use `vision specialist --help`. Research proposals remain advisory until an adapter and checkpoint are validated.

The experimental **observed-output router** adds `vision specialist compare`:
an independent vanilla candidate, actual outputs from up to four registered
procedures, label-free disagreement measurements, Astra inspection of the overlays,
and Jev scoring of every valid completed candidate. Its [design and file map](docs/evidence-routing.md)
explain the boundaries and terminal command. This is a new experiment, not a
measured improvement over v1. The completed repeated benchmark below motivates it.

Start your code review with [the file map](docs/file-map.md), then [the walkthrough](docs/walkthrough.md). The older research and HTML study guide remain in the repository.

The [StarDist and reference audit](reports/stardist-audit-20260922/index.html) corrects the larger **37-image × three-repeat** evaluation. One TIFF reused instance IDs: **55 IDs represented 102 nuclei**. Rescoring every arm gives conditional mean count errors of **8.57% vanilla** (107/111 counts), **14.14% full v1 harness** (101/111), and **11.40% fixed Cellpose** (111/111). All-attempt within-10% success is **70.3%, 58.6%, and 73.0%**, respectively. This does not establish a full-harness advantage. The original predictions and report remain preserved, with the old scores marked superseded.

The audit also ran **555 fresh native StarDist inferences**. All **333 original-setting masks match the worker pixel for pixel**. After the reference repair, default StarDist's mean count error is **23.29%**; uniform half-size input reduces it to **10.57%**, while losing small nuclei in some dense fields. These are post-hoc scale diagnostics, not a new held-out harness result. See [all three run averages](reports/stardist-audit-20260922/three-run-averages.md), exclusion/SVG sensitivities and visual evidence in the audit. The six-image experiments below remain separate historical exploratory results.

The [new routing comparison](reports/bbbc039-routing-20260922/index.html) is complete on six additional BBBC039 test images: **Cellpose-SAM 4.23%**, **vanilla Astra 5.44%**, and **routed harness 5.71%** mean count error, all 6/6 numerical results. Every routed result carries Jev's caution flag under the new provisional-estimate policy. Jev selected a best procedure on 2/6 images, so this run supports specialist access but does not establish a benefit from the routing policy. See [findings and exact counts](reports/bbbc039-routing-20260922/findings.md).

The new [adaptive-tool experiment on BBBC039](reports/bbbc039-adaptive-20260922/index.html) removes default-first guidance and makes Jev assess conditions of use. On six preselected official-test images, fixed StarDist and Astra + StarDist score **9.72%** count error; Jev selection changes three counts and improves to **9.20%**. The full loop accepts **2/6**, abstains on three and has one Astra output-limit error. A clearly labeled post-hoc uniform-sensitive calculation scores **7.94%**, so this run does not establish that adaptive orchestration beats a simpler fixed policy. See [findings](reports/bbbc039-adaptive-20260922/findings.md) and [the adaptive file map](docs/adaptive-stardist.md). This is a different dataset from the BBBC001 results below.

The earlier [StarDist full-chain experiment](reports/bbbc001-stardist-20260922/index.html) is complete: **Astra + StarDist returned 6/6 counts at 6.67% mean error**, identical to standalone StarDist. The full Astra → Jev selection → StarDist → Astra → Jev review/replanning chain proposed those same six counts but ultimately abstained on all six, with no execution errors. All overall review scores exceeded 0.75; method/target checks failed. Primary vanilla answered 5/6; a separately recorded timeout retry completes a **recovered/composite baseline of 18.20%**, against which StarDist is closer on all six images. See [exact counts and interpretation](reports/bbbc001-stardist-20260922/final-score.md) and the [integration file map](docs/stardist-harness.md). These are six previously inspected development images, not held-out evidence.

The earlier [standalone specialist experiment](reports/bbbc001-specialists-20260922/index.html) produced 12/12 mask-derived counts: **StarDist 6.67%** mean counting error and **Cellpose-SAM 14.09%** on the six BBBC001 images. StarDist is closer than the explicitly historical vanilla run (17.34%) on five of six images. That native perception experiment did not involve Astra/Jev; the integration above is a separate run. The detachable [experiment directory](experiments/microscopy/README.md) records exact dependencies and commands; masks, numbered overlays, checkpoint hashes and the startup recovery are preserved in the report.

The earlier [requested no-review comparison](reports/bbbc001-no-review-20260922/final-score.md) completed all **18/18** trials with numerical counts and no abstentions or execution errors. Mean counting error: **17.34% vanilla**, **16.16% Astra + OpenCV**, **14.27% Astra + OpenCV + Jev selection**. Use `configs/bbbc001-no-review.toml` to reproduce this configuration. Selection leads this run's average, but both tool modes improve only two of six images; all tool-mode counts are visual estimates after unusable segmentation. This is a small retest, not a stable overall ranking.

The completed [final comparison](reports/bbbc001-full-repaired-20260922/final-score.md) is **vanilla Astra versus the full harness**, including both Jev plan selection and answer review (`--mode full`). On all six original BBBC001v1 images, vanilla returned 6/6 counts with 10.30% mean counting error; full returned 0/6 counts, with six abstentions and no execution errors. Mean runtime was 76.5 s versus 234.4 s. The full harness therefore has no defined full-dataset error score. The [frozen protocol](reports/bbbc001-full-repaired-20260922/protocol.json) records this retest after integration repairs; use `configs/bbbc001-full-repaired.toml` for this configuration.

The earlier [11.36% selection-only result](reports/bbbc001-20260922/final-score.md) disables answer review and is an ablation, not the full-harness score. The user's instruction to skip the review-only comparison does not remove review from the full harness.

The optional [structured review loop](docs/review-loop.md) carries failed checks and previous plans into Astra planning and Jev selection. Use `--config configs/poc-loop.toml --mode full` to enable it. Its separate BBBC001 retest uses `configs/bbbc001-loop.toml`; the original runtime config and prior results are preserved.

The [structured-loop retest](reports/bbbc001-loop-20260922/final-score.md) is complete: vanilla 11.64% counting error; loop first/last numerical proposals 14.09%/14.56%. The loop accepted no counts (three abstentions, three Astra timeouts). This run did not establish a gain; the interrupted trials limit conclusions about completed-loop performance.

The [full real microscopy benchmark](reports/bbbc001-20260922/index.html) preserves all original trials, images, human annotations and traces. Its [frozen protocol](reports/bbbc001-20260922/protocol.json) records provenance and the published percentage-error scoring rules.

The earlier [synthetic smoke test](reports/cohort-five-20260922/index.html) contains 25 live trials. Those easy examples check integration; they do not establish a capability advantage. They remain separate from the published benchmark.

## Get started

Run commands from the repository root. Python 3.12 and `uv` are used; dependencies are pinned in `uv.lock`.

```bash
uv sync --extra eval --extra research
```

Copy `.env.example` to `.env` on a new checkout, then fill in your credentials locally:

```dotenv
OPENAI_API_KEY=your_openai_key
JEV_API_KEY=your_typesafe_key
```

`TYPESAFE_API_KEY` is also accepted. If both Jev variables exist, `JEV_API_KEY` wins. The project's `.env` deliberately takes precedence over inherited environment variables. `.env`, runs, and jobs are Git-ignored. Credentials are passed to the providers at runtime and redacted from harness logs. Do not put them in configuration, prompts, screenshots, or Git.

```bash
uv run vision doctor
uv run vision doctor --check-api
```

The second command makes small billed API requests. The configured models are `gpt-6-astra` and `jev-1.13.0`; change them in `configs/poc.toml`.

## Try it

```bash
# No API calls: deterministic stand-ins exercise the full pipeline.
uv run vision run --offline --mode full --image examples/shapes.png \
  --prompt 'How many red circles are in this image? Return a number.'

# Actual hosted models, with pauses for your review.
uv run vision run --mode full --image examples/shapes.png \
  --prompt 'How many red circles are in this image? Return a number.' --step

# Debug a tool independently, with no model calls.
uv run vision tool run components --request examples/components.json
```

Every run prints its saved directory. Use that directory or its run ID:

```bash
uv run vision inspect runs/RUN_ID
uv run vision replay runs/RUN_ID
uv run vision export runs/RUN_ID
```

`replay` is log playback, not re-execution. `export` creates a validated Harbor ATIF trajectory. Images, masks, and overlays are ordinary PNG files in the run's `artifacts/` directory. `--step` pauses before selection and tool execution; it is an interactive inspection feature, not a resumable debugger.

## Execution modes

| Mode | Image to Astra | Fixed probes and tools | Jev plan scoring | Jev answer review |
|---|---|---|---|---|
| `vanilla` | Yes | No | No | No |
| `tools` | Yes | Yes | No | No |
| `select` | Yes | Yes | Yes | No |
| `review` | Yes | Yes | No | Yes |
| `full` | Yes | Yes | Yes | Yes |

Astra uses the Responses API with strict structured outputs. Its plans are explicit tool commands interpreted by our runtime; this POC does not expose arbitrary Python or shell execution to the model. Both the original image and selected derived images are sent through the actual image-input interface.

Jev receives structured text evidence. It does not receive raw pixel arrays or independently inspect images. Python validates structure, enforces limits, executes tools, and preserves measurements. Jev scores never become a universal probability that an answer is correct.

Jev requests now have a conservative 24,000-byte serialized budget (`limits.jev_max_request_bytes`). Large component lists become explicit aggregate summaries; original geometry is retained under the run's `evidence/` directory. Counts, quality warnings, parameters, questions and answers remain intact. The trace records each projection and the HTTP response, including API error bodies. This change follows the original BBBC001 run and is recorded as a separate recovery experiment.

Astra saves responses before schema parsing. `models.format_retries=1` allows one additional request for malformed structured output or reported output-token exhaustion. Only token exhaustion doubles the output budget, capped at 32,000; refusals and content-filter interruptions are not retried. The extra request, allowance and usage are recorded. This behavior was added after the frozen benchmark, following a separate recovery run that exposed another malformed-plan failure.

## Evaluation with Harbor

Docker must be running. Harbor 0.23.0 is pinned because its adapter interfaces and trajectory schema are version-sensitive.

For the real benchmark, task bundles are already prepared locally:

```bash
uv run vision eval --config configs/bbbc001-full-repaired.toml
uv run harbor view jobs/bbbc001-full-repaired-20260922
uv run python -m evals.benchmark_report reports/bbbc001-full-repaired-20260922 jobs/bbbc001-full-repaired-20260922
```

The report requires exactly one attempt per image/mode. To run another experiment, first choose a new `jobs` directory in a copied config; do not mix repetitions into this frozen cohort. See [the import and scoring protocol](evals/README.md#published-microscopy-benchmark).

The synthetic commands below are retained for local plumbing checks only:

```bash
# Creates 20 development and 60 held-out synthetic examples.
uv run vision dataset

# Start with one development task and check the machinery.
uv run vision build-tasks --limit 1
uv run vision eval --offline
uv run harbor view jobs

# Once the offline check works, run actual models on those tasks.
uv run vision eval
uv run vision report
```

The generated dataset and one-task bundle already exist on this machine. The generators refuse to overwrite existing output. To create another task bundle, choose a new directory and update `tasks` in `configs/evaluation.toml`:

```bash
uv run vision build-tasks --split test --output evals/tasks/generated/heldout
```

The evaluation configuration controls modes, repetitions, concurrency, and model. Each image/question is identical across modes. Ground truth is provided only to the verifier after the agent runs. Offline stand-ins are clearly tagged and must never be interpreted as Astra/Jev benchmark performance.

For a controlled selection experiment, replay the exact same saved candidate plans in both `tools` and `select` modes:

```bash
uv run vision run --mode tools --image examples/shapes.png \
  --prompt 'How many red circles are in this image? Return a number.' \
  --plans runs/ORIGINAL_RUN/plans-1.json
uv run vision run --mode select --image examples/shapes.png \
  --prompt 'How many red circles are in this image? Return a number.' \
  --plans runs/ORIGINAL_RUN/plans-1.json
```

Frozen-plan runs never regenerate candidates or retry a rejected plan set. Standard Harbor runs independently generate plans per mode; they measure whole-system behavior and do not by themselves isolate the selector from planning variation. See [evaluation protocol](evals/README.md).

## What v1 supports

- Fixed probes: dimensions, grayscale contrast, Laplacian variance, and color-mask coverage sensitivity.
- Connected components after named-color segmentation, with boxes, centroids, areas, masks, and overlays.
- Watershed separation as an alternative method.
- Cropping with original-image coordinate offsets.
- Pixel distance between supplied points.
- Bounded candidate comparisons and optional evidence-review retries.
- CLI inspection, credential-redacted event logs, actual provider responses, usage, and validated ATIF export.
- Five-mode Harbor evaluation with independent numeric/categorical grading.

This is a narrow vision POC. StarDist and Cellpose-SAM are integrated in the newer specialist routing CLI; the original `vision run` modes have separate adapters/configurations. It does not yet handle DICOM, fMRI, TRIBE, OCR, general object detectors, or physical-unit calibration. Adding these requires real adapters and domain-specific tests, not just capability descriptions. OpenCV and StarDist run on CPU; the registered Cellpose-SAM procedure uses this Mac's MPS GPU. Astra and Jev inference are hosted.

## Review and verify

```bash
uv run pytest -q
uv run ruff check src evals tests
uv run ruff format --check src evals tests
```

Tests cover pixel measurements, crop coordinates, execution-mode isolation, retry limits, bad evidence references, provider wire formats, key redaction, scoring, dataset reproducibility, task isolation, and trajectory validation. Mocked API tests verify integration contracts; they do not substitute for the live health check.

The harness records token usage and latency. Dollar cost is left unknown until explicit versioned provider pricing is supplied. Run and output-token limits bound calls, not an exact dollar spend.

See [architecture and policy](docs/architecture.md) and [verification status](docs/verification.md) for the current evidence and limitations.
