# Repaired full harness versus vanilla Astra

## Follow-up: score the counts before rejection

At the user's request, all 12 candidate counts were extracted directly from the existing six full-harness traces and independently scored against the same published reference means. The first proposals average **13.71%** counting error; the last proposals average **14.49%**, versus **10.30%** for vanilla. Last proposals are closer on one image and worse on five. Choosing the last proposal uniformly avoids selecting whichever attempt happens to match the labels better. No new inference was performed, and the six recorded abstentions are unchanged. See the [per-image counts and audit trail](candidate-counts.md).

## Final outcome

All 12 live Harbor trials completed without execution errors. Vanilla returned six numerical counts with **10.30%** mean percentage counting error and **76.5 s** mean runtime. The complete harness returned **zero of six** final counts: six abstentions, no defined full-dataset counting-error score, and **234.4 s** mean runtime. This experiment provides no performance gain for the full harness.

Every full trial performed two Jev plan assessments and two answer reviews. All 12 support scores were below the unchanged 0.75 threshold (range 0.07–0.27). Astra proposed numerical candidates, but none passed final review. These are policy abstentions, not missing API credentials or failed executions.

Two full trials (fields 1 and 2) exhausted the initial Astra planning output allowance and successfully used the single configured retry at 8192 output tokens. Field 1 also exercised Jev evidence summarization: its review payload shrank from 127,135 to 11,574 bytes and returned successfully. All 56 provider calls across both modes have recorded response/usage events. These live recoveries are retained in the report, including their time and token cost.

In field 1, replanning found a grayscale hue workaround and produced watershed counts of 347 and 326 plus 311 connected components. Astra proposed 370 after visual adjustments; Jev returned support 0.27 and rejected it. The other five final candidates continued to depend on visual counting after unusable segmentation. Thus the tool failure was not universal across every second-round method, but the complete system still accepted no count.

[Final scorecard](final-score.md) · [All paired results and traces](index.html)

## Configuration being evaluated

The full harness retains **both** Jev stages: methodology scoring before tool execution, and evidence review after Astra proposes an answer. The separate review-only ablation is omitted from this comparison. The runtime mode is `full`, not `select`.

The quoted historical result, “Full harness: 5/5, 25.3 s”, came from the earlier synthetic smoke test. It is not a score on microscopy images. Similarly, the previous 11.36% microscopy result used selection-only mode and is not the full architecture's score.

This experiment runs two configurations on all six original [BBBC001v1](https://bbbc.broadinstitute.org/BBBC001) images: vanilla Astra and the complete harness. There is one trial per image and mode, for 12 trials. Images, task instructions and human annotations are unchanged from the published-benchmark import. No synthetic problems were added.

## Repairs included before this run

- Jev receives bounded evidence summaries when individual component geometry makes a request too large. Full geometry remains in local trace artifacts; counts, method parameters and quality warnings remain in the request.
- HTTP error bodies are recorded before raising.
- Astra responses and usage are recorded before JSON/schema parsing. One format retry is allowed for malformed output or explicit output-token exhaustion. Only explicit token exhaustion increases the output allowance; refusals are not retried.

The perception tools, Jev rubrics and acceptance threshold remain unchanged. In particular, the toolset still has no microscopy-specific learned segmentation model. No settings are changed during this run.

## Reading the final score

The published counting metric averages each image's absolute percentage error against the mean of its two human counts. Lower is better. It is not a classification-accuracy percentage.

Completion is reported separately: how many of the six images received a numerical final count. An abstention is not a completed count. A configuration missing any count has no complete-dataset percentage-error score; its answered-subset error, if any, is explicitly labeled and cannot establish a win over a complete run. Intermediate candidate counts rejected by review are not substituted for final answers.

## Why numerical estimates can become abstentions

The initial completed traces show a concrete tool mismatch. In the OpenCV `color_mask` implementation, `color="any"` selects pixels with sufficient saturation **or** brightness below 200. Setting `saturation_min=0` selects every pixel, and `value_min` is ignored in this branch. On these grayscale fluorescence images, connected components then reports one component covering 100% of the image; watershed can report one covering approximately 99.2%. Changing `value_min` does not repair that mask. The tools disclose their light-background assumption in returned quality warnings, but the candidate planner does not receive that complete implementation contract in advance.

Astra can subsequently estimate from the original image and crops. However, Jev's current adapter receives JSON evidence, not those pixels. Its review rubric explicitly says to treat image interpretations as unverified unless supported by independent tool evidence. A crop's coordinates and existence do not independently establish how many nuclei it contains. Consequently, a visual estimate can be useful numerically yet fail this review policy. Noul is being used as an evidence-support gate; this experiment does not calibrate it as the probability that a cell count is correct.

This separates two potential follow-up changes: make the tool contract and grayscale segmentation appropriate for microscopy, and evaluate the acceptance policy separately from count quality. Neither change was applied during this frozen run. Rejected candidate counts remain diagnostic trace entries, not final predictions.

## Interpretation limits

These same six images were already inspected during earlier evaluation and integration debugging. This is a documented retest after repairs, not a fresh held-out evaluation. It covers one small experiment and one attempt per image. The full harness uses additional inference, so differences are whole-system observations rather than a compute-matched estimate of Jev's contribution.

The source images and annotations are attributed to David Root and Anne Carpenter under [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/), via the Broad Bioimage Benchmark Collection. Original provenance, hashes and the frozen runtime are recorded in [protocol.json](protocol.json).
