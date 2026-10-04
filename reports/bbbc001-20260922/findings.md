# BBBC001v1: interpreting the real microscopy experiment

## Completed result

All 30 original trials completed. Among modes providing a count for all six images, Jev selection had the lowest observed error. The review-enabled modes produced no accepted final counts.

| Mode | Valid final counts | Published mean percentage error ↓ | Abstentions | Errors | Mean runtime |
|---|---:|---:|---:|---:|---:|
| Vanilla Astra | 6/6 | 14.08% | 0 | 0 | 67.0 s |
| Astra + OpenCV | 6/6 | 12.78% | 0 | 0 | 82.1 s |
| Tools + Jev selection | 6/6 | 11.36% | 0 | 0 | 85.3 s |
| Tools + Jev review | 0/6 | Incomplete | 4 | 2 | 153.2 s |
| Full harness | 0/6 | Incomplete | 5 | 1 | 170.6 s |

The selection mode's observed error is 2.72 percentage points lower than vanilla. However, its final answers describe visual estimates after unusable segmentation. With six images, one attempt, different plans and additional inference, this does not establish a perception gain or isolate a causal benefit from Jev.

The full harness's additional error was another malformed Astra `PlanSet` response (field 1). All three original errors remain in the comparison. The Jev HTTP failure has since been repaired and retried successfully, as described below; recovery results are deliberately separate.

## What was tested

All six original images from the [published BBBC001v1 benchmark](https://bbbc.broadinstitute.org/BBBC001), using its cell-counting task and two human counts per image. No synthetic images, invented ground-truth labels, difficulty filtering or selective image exclusions were used.

The question is a plain-language wrapper for that existing counting task. Its wording is ours; the underlying images, target counts and percentage-error formula are the benchmark's. The only pixel conversion is lossless grayscale TIFF to RGB PNG. Source hashes and the exact instruction are in `protocol.json` and `cohort.json`.

## How to read the score

For each image, average its two published human counts. Compute the absolute difference between the prediction and this reference, divide by the reference, then multiply by 100. Average those six percentages. Lower is better. This is not classification accuracy or a confidence score.

An abstention is not a correct count. An incomplete mode receives no full-dataset score; its answered-subset error is shown separately. Do not rank a partial score against a complete score. A numeric estimate still counts as a prediction even if the model lists uncertainty, provided it returns `answered` rather than `abstained`.

The human counts themselves disagree. They are an independently supplied reference, not certainty about every ambiguous nucleus.

## Scope of the conclusion

This is a transfer test of the existing POC. Its OpenCV operations, model settings, rubrics and thresholds were not tuned on these images. The color-mask tools were initially built for the synthetic integration examples. No microscopy-specific segmentation model was added for this run.

The experiment can show whether this particular runtime improves or harms cell counting on this dataset. It cannot establish that specialist vision tools generally help or that they generally fail. All images come from one small experiment, and public-dataset exposure during foundation-model training cannot be ruled out.

Each mode generates its own plans. Tool modes also consume additional inference and may perform competing plans or review retries. Differences are whole-system observations, not a controlled causal estimate of Jev's selector alone.

The original synthetic smoke-test report remains under `reports/cohort-five-20260922/` and is not pooled into this benchmark.

## Observed method mismatch

The six answers in the Astra + OpenCV mode explicitly describe visual estimates. Their segmentation attempts did not yield reliable nucleus instances. The common failure was a single foreground region spanning almost the whole frame, rather than separate cell nuclei.

The cause is specific to the current adapter: `color="any"` uses a foreground rule designed around a light background. Setting `saturation_min=0` on these grayscale images admits the whole image. Changing the requested brightness threshold or watershed marker fraction cannot repair that foreground mask. This is not evidence that OpenCV itself cannot segment fluorescence images; it is evidence that our exposed operation and its parameters do not implement the method Astra thought it was requesting.

Review [`color_mask` in the OpenCV adapter](../../src/vision_harness/tools/opencv.py) alongside [the capability descriptions](../../configs/capabilities.toml). In the `any` branch, `value_min` is accepted but not used. The method description does not fully expose this restriction before planning; the white-background warning appears in returned tool evidence. This mismatch should be addressed before interpreting planner or Jev scores as meaningful method validation.

For example, the selection-mode trial on field 4 gave three proposed methods scores of 1.95, 1.95 and 1.96 (on the configured 0–3 rubric). Two passed into execution, but components returned one region covering 100% of the image and watershed returned one region covering about 99.2%. Astra then estimated 340 cells visually. The full trace and the two human counts are in the report. Jev's plan scores did not independently validate segmentation quality.

These observations suggest a concrete architecture requirement: the tool registry must expose actual foreground assumptions and parameter semantics, and executed masks need validity checks before their counts can support an answer. A plan score is a judgment about supplied descriptions; it cannot replace checking the produced evidence. Any fix should be evaluated in a new, separately recorded experiment, without changing this run's frozen results.

## Review can change the method, but evidence size can break the pipeline

On field 4, answer review rejected the initial visual estimate with support probability 0.08. Astra's second plan then used `color="red"` with zero minimum saturation. For these grayscale pixels, hue is zero, so this happened to activate a brightness threshold through the named-color branch. Components returned 266 regions; two watershed settings returned 297 and 295. Astra proposed an estimate of 300. Those regions are still not individually verified nuclei, but this was a material change from the earlier one-region masks.

The next Jev review failed with HTTP 400. The saved request was 317,269 bytes on disk because the accumulated evidence included hundreds of component records. A single, separate replay captured the server's explicit `max_tokens_exceeded` error; see [the diagnostic record](rejected-request-diagnostic.json). That replay is diagnostic only and does not replace the failed trial or enter benchmark metrics. The original adapter raises on HTTP errors before saving the response body, which is why this separate check was necessary.

This identifies a second concrete requirement: bounded evidence payloads. Full component geometry should remain in inspectable artifacts, while each model receives an explicit, size-limited set of relevant measurements and references. The runtime also needs to save error responses before raising. These changes were not introduced during this frozen experiment.

### User-requested Jev recovery

After the user requested a retry, the unchanged request again returned HTTP 400 with `max_tokens_exceeded`; see [that retry](user-requested-jev-retry.json). The account/key was not the problem. [TypeSafe documents](https://docs.typesafe.ai/models) a 32k-token limit for the state plus its longest question, and 64k for the complete request.

The adapter now projects oversized component lists into explicitly labeled aggregates while preserving counts, parameters, quality flags, questions and answers. Full geometry remains in a hashed local trace artifact. It also records HTTP error bodies before raising, so the CLI can show the server's actual reason. Requests that still exceed the local 24,000-byte budget fail explicitly instead of silently dropping important fields.

Replaying the failed review through this adapter reduced the compact serialized request from 109,475 to 8,361 bytes and returned HTTP 200 with support probability **0.56**. That is below the unchanged 0.75 acceptance threshold: the API now works, but the reviewer still does not approve this answer. See [the recovery result](jev-recovery-field4/result.json) and [events](jev-recovery-field4/events.jsonl). The original benchmark failure is preserved. A separate one-task Harbor recovery run uses [its own protocol](retry-protocol.json); it is not pooled into the frozen comparison.

The first Harbor recovery passed Jev (support 0.06) but subsequently failed on malformed Astra planning JSON. The Astra adapter was then changed to save responses before parsing and permit one bounded format retry. Only an explicit `max_output_tokens` incomplete reason increases the allowance; refusals and content-filter interruptions are not retried. See the [official OpenAI structured-output guidance](https://developers.openai.com/api/docs/guides/structured-outputs) for the response states being handled. The additional request and any budget change are logged.

The second Harbor recovery completed without an API/parsing exception. It returned **abstained**, citing inconsistent counts of 269–301 pixel regions and unresolved merged/dim nuclei. No format retry was needed in this successful live run; the malformed-output retry path is covered by mocked regression tests, not claimed as exercised here. Both Harbor recovery traces are validated and preserved in [recovery-results.json](recovery-results.json). This is an operational recovery, not a correct cell-count prediction or a replacement benchmark score.

## Answer-review mode did not complete the benchmark

With Jev answer review and Astra's own plan selection, four images ended in abstention and two in errors. The second error was an invalid/incomplete `PlanSet` JSON response on a retry (field 2). Its parser reported an unexpected end of a list. The existing adapter records a response after parsing, so the original failed response and its usage were not retained; a more specific cause cannot be established from the saved trace.

Consequently this mode has zero completed count predictions, not a zero-percent error. Its intermediate proposed answers remain visible for diagnosis but are not substituted into the final score. Review can increase caution or prompt a different method; this run does not show a usable counting improvement from that gate.
