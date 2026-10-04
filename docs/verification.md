# Verification record

Verified on 2026-09-22 (Asia/Kolkata).

## Repeated external microscopy evaluation — latest verification

The [Kromp report](../reports/kromp-repeated-20260922/index.html) covers all 37
official test images with three fresh repetitions: 111 paired trials, 444
specialist executions and 781 saved provider responses. Zero terminal API,
parsing, worker or orchestration errors occurred. Four vanilla requests used the
configured output-token recovery. All abstentions remain in the results.

Conditional count-error mean ± sample run SD: vanilla 9.68% ± 0.34 pp (107/111
counts), Astra with its preferred specialist 20.78% ± 3.24 pp (98/111), full
current harness 16.90% ± 0.54 pp (101/111), fixed Cellpose 13.41% ± 0.00 pp
(111/111). The pre-review selection stage and full numerical outputs are identical.
All-attempt within-10% success is 70.3% for vanilla/Cellpose and 55.9% for full.
This does not establish a counting advantage for the harness. The
[findings](../reports/kromp-repeated-20260922/findings.md) disclose coverage,
paired intervals, subgroup failures and the shared-stage ablations.

All **333 Harbor ATIF traces validate**. The audit verifies 111 decisions frozen
before execution, 444 instance maps and 66,432 predicted object areas. Current
inference source, frozen scripts, prompts, configuration, catalog, metadata and
input hashes still match the protocol. All fixed procedures produce three
bit-for-bit identical masks on every image. Independent Pillow decoding matches
all 37 expert reference counts. This was native process inference with Harbor
trace export, not a Harbor Docker job. Test labels were decoded after all inference.

All **65 tests pass** and Ruff lint passes. The report loads 224 images and has
564 working local links, no JavaScript errors and no document overflow at 1440,
768, 390 or 320 pixels. All 37 pages and pagination controls work at each width;
desktop/mobile screenshots and both scientific figures were visually inspected.
Actual credential values were absent from 6,589 new report, run and helper text
files. No repository was pushed or published.
See the [file map and reproduction commands](repeated-results.md).

## Adaptive StarDist and condition review — earlier verification

The [BBBC039 experiment](../reports/bbbc039-adaptive-20260922/index.html) has 24 primary live Harbor trials, plus six fixed-default specialist controls. Six official-test filenames were selected before image/annotation downloads. A separate TIFF reader reproduces every display conversion, and all annotation component partitions match the official decoding algorithm. This is a derived count task on segmentation annotations, not the official segmentation metric.

Vanilla scores 10.03%; fixed default and Astra-only tools both score 9.72%; Jev selection changes three counts and scores 9.20%. Full mode accepts two, abstains on three and encounters one Astra structured-output exhaustion after its bounded format retry. It has no complete-cohort score. First/last proposals score 9.20%/9.48%; these are not substituted for final answers. A separately labeled post-hoc uniform-sensitive calculation from existing measurements scores 7.94%, so the experiment does not establish a gain over the simpler fixed profile.

All 24 trajectories validate; all 24 verifier rewards independently reproduce. All 99 started provider calls have recorded responses. All 35 Jev calls succeeded (22 plan assessments, 13 reviews); the Astra error was an output-limit failure, not an API timeout or Jev rejection. All 59 instance maps and 5,133 instance geometries were audited. All 24 live default whole-image maps equal their controls pixel for pixel. Every accepted full answer passed all five 0.75 requirements. Input, source, checkpoint and dependency hashes match, and actual keys are absent from reports/logs. See the [audit](../reports/bbbc039-adaptive-20260922/verification.json).

There are 44 passing local tests. Lint/format checks pass for the runtime, evaluation tools, tests, control worker and audit. The report loads all 18 images and 24 disclosures, has no broken local links or page errors, and has no horizontal page overflow at 1440, 768, 390 or 320 pixels. Desktop/mobile and segmentation previews were visually inspected. No runtime policy was changed after freezing the protocol, and no outcome-driven inference retry was performed.

## StarDist full-chain integration — previous verification

The [completed experiment](../reports/bbbc001-stardist-20260922/index.html) has 18 primary live Harbor trials and one separately preserved vanilla timeout recovery. Astra + StarDist returned 6/6 measured counts at 6.67% mean error. Full mode proposed identical counts, but all six trials abstained after method/target validity checks failed. All 18 Jev calls succeeded: 12 selections and six reviews. Failed checks reached both planning and selection on all six full trials. The full arm had no execution errors.

Primary vanilla returned 5/6; its Astra API timeout remains recorded. The predeclared separate retry changed only timeout from 120 to 300 seconds. Its count completes a recovered/composite 18.20% vanilla error. It is not reported as six successful primary trials. All 19 trajectories validate and all 19 verifier metrics independently reproduce. There are 62 started calls and 61 recorded responses; the timed-out call has unknown token usage.

All 41 live StarDist instance maps were independently recounted; all 14,339 saved instances match label IDs, areas, centroids, boxes and border flags. Original inputs, frozen inference source, dependency locks and checkpoint hashes match all six task bundles. Mode isolation, feedback propagation and absence of actual credentials in logs/reports were checked. The six default container label arrays exactly match native standalone inference. The integration has 42 passing tests, with source/evaluation/test lint and formatting checks passed before inference. See [machine-readable audit](../reports/bbbc001-stardist-20260922/verification.json) and [preflight](../reports/bbbc001-stardist-20260922/preflight-verification.json).

The HTML report passed layout checks at 1440, 768, 390 and 320 pixels. All 18 images and local links load, disclosure controls work, and no page overflow or JavaScript errors were found. Desktop/mobile and original/segmentation previews were visually inspected.

## Standalone specialists — previous verification

The [native specialist comparison](../reports/bbbc001-specialists-20260922/index.html) produced 12/12 numerical counts derived from saved instance labels. StarDist: 6.6662% mean count error, 0.1387 s mean CPU inference. Cellpose-SAM: 14.0862%, 2.4175 s mean MPS inference. Timings exclude initialization and artifact creation. One StarDist metadata lookup failed before image inference; its startup trace is preserved, the lookup was repaired, and the unchanged segmentation configuration completed all six images. Cellpose was not rerun.

All 12 instance maps were independently recounted. Every instance ID, pixel area and centroid agrees with the saved geometry. Input images, checkpoint files and original/recovery worker snapshots match their recorded hashes; all percentage errors independently reproduce. Both isolated dependency environments pass `uv pip check`; experiment lint and formatting pass. A non-contiguous-label arithmetic check confirms that the worker counts unique positive labels rather than the maximum label ID. HTML checks passed at 1440, 768, 390 and 320 pixels; all 18 images and local links load. Desktop/mobile previews and example overlays were visually inspected.

No Astra or Jev calls were made for this experiment. The comparison to 17.34% vanilla uses the previous run explicitly, without pooling or substitution. This is a previously inspected six-image development cohort, with count labels but no instance-mask ground truth used. These trials run in native specialist processes, not Harbor; the core harness inference files and its existing runtime dependencies were unchanged.

## Requested tools/selection retest

The [no-review comparison](../reports/bbbc001-no-review-20260922/index.html) completed 18/18 live trials with numerical answers, no abstentions and no execution errors. Counting error: vanilla 17.34%, tools 16.16%, selection 14.27%. Mean runtime: 100.3 s, 95.1 s and 107.6 s. One vanilla call needed the existing token-exhaustion recovery; both tool modes completed without format retries.

All 18 trajectories validate and verifier scores independently reproduce. Every mode received matching original-image hashes, and every frozen runtime hash matches the task snapshots and current inference files. There were six Jev plan-assessment calls and zero answer-review calls. The structured loop was disabled. All 37 started calls have response/usage records. Actual API keys were absent from reports and job artifacts. No inference code changed; this is a configuration-only retest of the previously verified runtime, retaining its 39-test verification below.

## Structured-loop experiment

The optional [review loop](review-loop.md) passes **39 local tests**, including failed-check propagation into planning and selection, rejecting high overall support when an individual check fails, operation reuse, duplicate-plan filtering, no-new-observation stopping, call/time guards, and Jev's five-question response validation. Lint and formatting checks pass. The new candidate report independently reproduces the prior run's 13.71% first-proposal and 14.49% last-proposal errors.

The [new live report](../reports/bbbc001-loop-20260922/index.html) contains 12 paired trials on the six original BBBC001 images. All 12 trajectories validate, image hashes match across modes, and frozen runtime hashes match every task bundle and the current inference source. All verifier rewards reproduce. Both Jev stages ran on every full trial; eight structured reviews returned, six later selection calls contained prior failed checks, and six repeated operations reused evidence. Live runs did not exercise total-budget or no-new-observation stopping; those branches have local test coverage.

Vanilla: six counts, 11.64% mean error, 93.9 s mean runtime. Full loop: zero accepted counts, three abstentions, three Astra timeouts, 326.1 s mean runtime. Diagnostic first/last numerical proposals have 14.09%/14.56% mean error; they do not replace final outputs. The 58 started provider calls have 55 response/usage records; timed-out-call usage is unknown. No keys were found in report/job artifacts. No inference changes or threshold adjustments occurred during the frozen run. This is a previously inspected six-image retest, not a stable overall ranking.

## Provider health

- The key in the project's `.env` successfully called `gpt-6-astra` through the Responses API. The minimal health request completed with `OK`.
- The Jev key successfully called `jev-1.13.0` with HTTP 200 and valid Noul and Score answers. `JEV_API_KEY` and `TYPESAFE_API_KEY` are supported aliases.
- Local evidence: `runs/api-health.json`. No credentials are contained in that file.

## Application

- 20 automated tests passed, including actual SDK serialization through mock HTTP transports.
- Ruff lint and formatting checks passed.
- A standalone OpenCV request measured nine components in `examples/shapes.png`, with masks, boxes, areas and overlays saved under `runs/standalone-check/`.
- A live full run selected and executed both connected components and watershed, produced the correct count of nine, and completed Jev's evidence-support review. Saved under `runs/live-comparison/`; this used the frozen candidates from the initial development run.
- The first development run at a 2.0 selection threshold abstained before execution. It remains under `runs/live-smoke/`. The documented read-only exploration threshold is now 1.5; this change was made on development data, not held-out results.
- The live trace exported successfully and passed Harbor's trajectory validator.

## Harbor

- Real Docker task execution completed in all five offline modes: vanilla, tools, select, review, full. Offline providers are explicit stand-ins; these results are plumbing checks only.
- Live vanilla and full Harbor trials each completed without an infrastructure error on the same one-image development smoke task. Both received an independent accuracy reward of 1.0. This verifies integration, not an improvement over vanilla.
- Harbor generated agent logs, verifier rewards and validated ATIF trajectories for these trials.
- The local Harbor viewer returned HTTP 200 and its HTML application at `http://127.0.0.1:8091` during verification. Start it again with `uv run harbor view jobs` to inspect traces.
- Job directories are under `jobs/`, labeled `offline-*` and `live-*`. `vision report` rebuilds the comparison from authoritative trial results and groups differing configurations separately.

## Credentials and repository

- `.env` is ignored by Git and has owner-only read/write permissions.
- A scan for the actual key values in application source, configuration, prompts, tests, documentation, run logs and Harbor outputs found no occurrences.
- No repository was published or pushed remotely.

## What these checks do not establish

The full 60-example held-out evaluation has not been run. The one-image smoke comparison cannot demonstrate a gain, calibrate Jev scores, or support medical/real-world claims. DICOM/fMRI and specialist deep-learning adapters are not implemented in this POC. Dollar pricing is not guessed; token usage and time are recorded, and report cost fields remain unknown.

## Subsequent five-task cohort

The [five-task report](../reports/cohort-five-20260922/index.html) records 25 live trials across all modes. Vanilla, tools, selection and full scored 5/5; review-only scored 4/5 after rejecting a correct answer and encountering invalid structured output on retry. Vanilla was fastest at a mean 6.4 seconds versus 25.3 seconds for full.

An initial batch exposed a supplied-image citation validator bug. The original batch is preserved, the bug was fixed for all modes, and the entire comparison restarted. The final source version is recorded in the cohort protocol. There are now 22 passing tests, including regression coverage for image citations.

All 25 final trial trajectories validated. Input hashes confirmed identical source images across modes; every trial used live providers. The HTML report passed desktop/mobile layout checks and local link checks. Five initially held-out test-split examples were used; they were seen during the documented infrastructure debugging, so these exploratory results should not be presented as a pristine large held-out evaluation. One failed call has unrecorded token usage, explicitly noted in the report.

## Published microscopy benchmark and recovery — 22 September 2026

The [BBBC001 report](../reports/bbbc001-20260922/index.html) contains the complete six-image published dataset across five modes: 30 original live trials. The source TIFF pixels match the supplied PNG pixels, annotations were isolated from agent containers, original runtime snapshots were checked, and all 30 Harbor trajectories validate. The report recomputes and checks the official percentage-error metric against verifier outputs.

Mean counting error: vanilla 14.08%, tools 12.78%, Jev selection 11.36%. Review and full produced no accepted counts and therefore have no complete-dataset score. Original errors and abstentions remain visible.

Following the user's retry request, Jev's context-limit failure was reproduced and repaired using bounded evidence summaries with full geometry retained locally. The same failed review then returned HTTP 200 with support 0.56. A first Harbor recovery exposed a separate malformed Astra plan; after adding raw-response logging and one bounded format retry, a second Harbor recovery completed with an abstention and no API/parsing exception. These two attempts are separate from the frozen benchmark. The successful live run did not need the format retry; that branch is verified by mocked tests.

Current local verification: **31 tests pass**, lint and formatting checks pass. Two recovery trajectories also validate. The report has six source images, 30 expandable original trials, no broken local links, no JavaScript errors, and no horizontal page overflow at 1440, 768, 390 or 320 pixels. Actual keys were not found in reports or logs.

## Requested full-harness comparison — 22 September 2026

The [completed full-harness report](../reports/bbbc001-full-repaired-20260922/index.html) contains a fresh paired retest on all six BBBC001 images: 12 live trials, vanilla versus `full`. Both Jev method selection and answer review were verified in every full trial; the standalone review-only ablation was omitted. Frozen runtime hashes match every task bundle, and all original image hashes match across modes.

Vanilla returned 6/6 counts with 10.30% mean counting error and 76.5 s mean runtime. Full abstained on 6/6, with zero execution errors and 234.4 s mean runtime. Its complete-dataset error is undefined because no final numerical counts were accepted.

All 12 Harbor trajectories validate and verifier metrics independently reproduce. All 56 started provider calls have recorded responses and usage. Two live output-token recovery attempts succeeded; one large Jev request was successfully summarized and reviewed. These recovery events did not convert abstentions into accepted counts.

The two-mode HTML report has six original images and 12 expandable trials. Local links, disclosure controls, desktop/mobile screenshots and page widths 1440, 768, 390 and 320 were checked. No JavaScript errors or horizontal page overflow were found. Actual API keys were absent from the new report and job artifacts. The report-only changes pass lint, formatting and whitespace checks; no inference code changed during this run. The most recent runtime test suite remains the 31-test verification above.

## Specialist routing v1 — 2026-09-22

Implementation `813030f`; [frozen cohort/protocol](../reports/bbbc039-routing-20260922/selection.json).
Six further BBBC039 official-test images, excluding the prior cohort. All 24
specialist procedure executions, six routed answers and six vanilla answers completed.
Cellpose-SAM count MAPE 4.23%; vanilla 5.44%; routed harness 5.71%. All six routed
answers are caution estimates under a new policy, not historical full-harness
approvals. Jev picked a best candidate on 2/6 images; review Noul 0.64–0.71.

The [audit](../reports/bbbc039-routing-20260922/audit.json) recomputes 24 masks and
2,311 instance geometries, validates 12 Harbor ATIF traces and 36 completed provider
calls, and verifies frozen-decision ordering. An independent scikit-image annotation
decoder matched all six counts. All 57 tests passed. Live sourced research also
completed with four proposals and four Jev scores. This was native process execution
with Harbor trace validation, not a Harbor container job. See the
[file map and CLI guide](model-routing.md) and [paginated report](../reports/bbbc039-routing-20260922/index.html).
