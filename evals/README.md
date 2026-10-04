# Evaluation protocol

The current experiment uses a published microscopy counting benchmark. Earlier synthetic examples remain integration checks only. Neither experiment tests AGI, human-like perception, clinical utility, or general visual intelligence.

## Published microscopy benchmark

The latest [requested comparison](../reports/bbbc001-no-review-20260922/index.html) uses `configs/bbbc001-no-review.toml`: **vanilla, tools, select**, all using `configs/poc.toml`. It excludes answer review and the structured loop. All 18 trials returned counts with no execution errors: mean counting error 17.34%, 16.16%, and 14.27% respectively. All six images and every attempt remain included. This single-run ranking does not isolate Jev's effect or establish better segmentation.

The earlier full-harness comparison uses `configs/bbbc001-full-repaired.toml`: **vanilla versus full**. Full includes both Jev plan selection and answer review. Only the separate review-only ablation is omitted. The earlier five-mode experiment remains an archive; the selection-only 11.36% result is not the full-harness result.

The [completed comparison](../reports/bbbc001-full-repaired-20260922/index.html) contains 12 live trials: vanilla returned 6/6 counts with 10.30% mean error; full abstained on all six with no execution errors. Its full-dataset counting error is undefined. Mean runtime: 76.5 s vanilla, 234.4 s full. This is a retest on previously inspected images after integration repairs.

The subsequent structured-loop experiment uses `configs/bbbc001-loop.toml`, whose `runtime_config` explicitly selects `configs/poc-loop.toml` inside the task snapshot. It compares vanilla versus full with structured review checks and bounded replanning. It is another one-attempt retest, not evidence of a stable ranking across every earlier mode. Generate its accepted-output report with `python -m evals.benchmark_report`, then its diagnostic first/last proposal report with `python -m evals.candidate_report REPORT_DIRECTORY`. Re-render the benchmark report to include links to the candidate report. Candidate metrics never replace recorded final answers.

This comparison repeats the same six benchmark images after Jev payload budgeting and Astra format-recovery fixes. They have already been inspected during debugging; it is a documented retest, not a new held-out cohort.

[BBBC001v1](https://bbbc.broadinstitute.org/BBBC001) contains six actual 512×512 fluorescence microscopy fields and counts from two human observers. We use the entire dataset, not selected images or invented tasks. The instruction asks for the dataset's original cell-counting objective; labels come unchanged from the published annotation file.

For each image, the published metric is `100 × abs(predicted count − mean of the two human counts) / mean of the two human counts`. Average those six percentages; lower is better. The original source reports disagreement between human counters, so exact-match accuracy is not the comparison metric. Harbor also retains the generic accuracy field for compatibility, but use **`evals.benchmark_report`**, not the generic accuracy report, to compare this benchmark.

A missing, negative, nonfinite or invalid prediction has no defined percentage error. A mode gets a full-benchmark score only when all six predictions are available. Coverage, abstentions, errors and answered-subset error are reported separately. This missing-answer policy is ours; the original benchmark assumes a count for every image. Partial scores are not ranked against full scores.

The source has no official train/test partition. `split=test` in the imported manifest is only a local task-builder routing label. The six images were not used for tuning this harness. Prior foundation-model exposure to this public benchmark cannot be ruled out.

`import_bbbc001.py` records download URLs, SHA-256 hashes, attribution, source filenames and both human counts. It converts grayscale TIFF to RGB PNG by replicating the same 8-bit pixels in all channels and verifies equality. It does not resize, enhance, recolor, simulate cells or add markings. The dataset lives under the existing ignored `evals/datasets/generated/` workspace directory; **the images are downloaded, not generated**. Only the neutral question and opaque-named PNG reach the agent; source metadata and annotations stay outside its environment.

The runtime, prompts, thresholds and color-based OpenCV operations remain unchanged from the earlier POC. This tests their transfer to real microscopy, including whether the coordinator rejects unsuitable tools. It does not evaluate a microscopy specialist such as Cellpose, which is not installed.

To import into new, empty directories:

```bash
uv run python -m evals.import_bbbc001 evals/datasets/generated/NEW reports/NEW
uv run vision build-tasks --dataset evals/datasets/generated/NEW --output evals/tasks/generated/NEW --split test
# Copy configs/bbbc001.toml and point tasks/jobs to new directories before a repeat.
uv run vision eval --config configs/bbbc001.toml
uv run python -m evals.benchmark_report reports/bbbc001-20260922 jobs/bbbc001-20260922
```

Images and annotations: David Root and Anne Carpenter, [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/). Dataset attribution: BBBC001v1, Moffat et al., Cell (2006), Broad Bioimage Benchmark Collection; Ljosa et al., Nature Methods (2012).

## Earlier synthetic integration dataset

The generator creates 20 development and 60 held-out samples by default, balanced across five families: red-circle counting, red counting among other colors, left/right position, center-to-center pixel distance, and touching-circle counting. Labels come from scene construction; they do not call the harness's vision tools. Counts/positions are exact; distance allows a two-pixel tolerance.

Image IDs are opaque hashes. Images are PNGs without answer metadata. The same seed reproduces the same manifest and image bytes. Dev/test random streams are separate. This narrow generator does not cover medical images, realistic clutter, arbitrary object identity, broad lighting variation or all counting ambiguities.

Ground truth lives in the dataset manifest and generated verifier files. The agent image is built from an explicit allowlist of source/config/prompt files and the input PNG. It does not contain the manifest, expected answers, reference solutions, `.env`, or this test suite. The model has no filesystem or shell tool that could fetch them during its attempt.

## Comparisons

All modes receive the same original image, question and final-answer schema. Astra model/effort settings are fixed within an experiment. Tool modes receive additional measured evidence. Jev variants perform additional inference and may run competing plans or review retries; record this extra work rather than claiming compute equivalence.

The normal Harbor comparison covers vanilla, tools, select, review and full. Planning is stochastic and regenerated per trial. Therefore `select` versus `tools` in that comparison measures the whole configured system, not pure selector quality. To isolate selection, use the CLI's `--plans` replay with the same image/question/candidates and disable answer review. Frozen-plan mode does not replan on failure.

Use the development split for changing rubrics and thresholds. Freeze settings, resource hashes and dependency versions before scoring the held-out split. Use multiple repetitions when estimating variability. A single smoke example is only an integration check.

## Grading

The verifier uses known answers, not Jev or Astra judgments. It records accuracy, whether an answer was supplied, abstention, and runtime/error status. A confident incorrect answer scores zero. Abstentions also score zero overall accuracy; coverage and accuracy among answered examples are reported separately so abstaining cannot silently inflate overall performance.

Harbor infrastructure failures are listed separately and must remain visible when comparing modes. Inspect per-family and per-example outcomes, including cases where tools or Jev harm a previously correct answer. The current JSON report gives raw trial details and aggregate coverage/accuracy; statistical confidence intervals and calibrated confidence plots are future analysis, not implemented claims.

Token usage and wall time are recorded. Dollar costs remain null unless explicit pricing is added; do not infer cost from equal token totals across different providers.

## Commands

```bash
uv run vision dataset --output evals/datasets/generated --dev 20 --test 60
uv run vision build-tasks --output evals/tasks/generated/current --limit 1
uv run vision eval --offline
uv run vision eval
uv run harbor view jobs
uv run vision report
```

Generators refuse to overwrite output. If directories already exist, use them or choose a new path and update the evaluation config. To validate a task's verifier with its reference solution, Harbor's oracle agent can run the generated `solution/solve.sh`; our own agent never sees this script during execution.

Offline runs use clearly labeled deterministic providers. Their apparent accuracy says nothing about Astra or Jev. They are useful for Docker, CLI, artifact, scoring and viewer checks.
