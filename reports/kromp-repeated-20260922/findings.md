# The larger repeated test does not establish a harness advantage

We completed **all 37 official test images × three fresh repetitions**: 111 paired
trials, 444 actual specialist executions and 781 hosted API calls. No image was
replaced after seeing its result. This is the full test split of the
[Kromp fluorescence nucleus dataset](https://www.ebi.ac.uk/biostudies/BioImages/studies/S-BIAD634),
whose [paper](https://www.nature.com/articles/s41597-020-00608-w) describes varied
preparation, imaging conditions and clustered/overlapping nuclei. The test masks
contain 5,086 annotated nuclei across 37 fields, with 12–969 per field.

**Vanilla Astra leads the current full harness on this cohort's measured counting
outcomes.** Specialist access remains useful on particular fields, but the current
selection policy does not reliably identify the right procedure. The previous
six-image result was insufficient to establish a general advantage.

## Three-run averages, with missing answers exposed

MAPE means mean absolute percentage error: an estimate of 90 against a reference
of 100 has 10% error. We calculate each attempt's error before averaging; we do not
average the three predicted counts first, which could hide opposing mistakes.

The numbers below are the mean of three per-run MAPEs, followed by their **sample
standard deviation in percentage points**. For arms with abstentions, each run's
MAPE uses only its returned numeric answers, so these are conditional errors:

- **Vanilla Astra: 9.68% ± 0.34 pp**, 107/111 counts returned; 78/111 attempts
  within 10% of reference (70.3%). Run errors: 9.88%, 9.29%, 9.88%; coverage:
  35/37, 36/37, 36/37.
- **Astra + its preferred specialist: 20.78% ± 3.24 pp**, 98/111 counts;
  57/111 within 10% (51.4%). Run errors: 24.50%, 19.20%, 18.63%; coverage:
  33/37, 32/37, 33/37. This shares the initial proposal with the routed arm but
  makes a separate answer call without Jev scores or competing masks.
- **Astra + Jev selection, before review: 16.90% ± 0.54 pp**, 101/111 counts;
  62/111 within 10% (55.9%). This is the saved pre-review stage of the full route.
- **Full current harness: 16.90% ± 0.54 pp**, 101/111 counts;
  62/111 within 10% (55.9%). Run errors: 16.32%, 16.97%, 17.40%; coverage:
  34/37, 33/37, 34/37.
- **Fixed Cellpose-SAM: 13.41% ± 0.00 pp**, 111/111 counts;
  78/111 within 10% (70.3%).
- **Fixed StarDist conservative: 17.45% ± 0.00 pp**, 111/111 counts;
  69/111 within 10% (62.2%).
- **Fixed StarDist default: 25.80% ± 0.00 pp**, 111/111 counts;
  60/111 within 10% (54.1%).
- **Fixed StarDist sensitive: 32.58% ± 0.00 pp**, 111/111 counts;
  57/111 within 10% (51.4%).

Missing answers are failures in the within-10% rate. An unconditional count MAPE
cannot be calculated when the system gives no count; we show coverage and the
all-attempt success rate instead of inventing an error for abstentions. The HTML
also reports the pooled returned-answer MAPE, which differs slightly from the
equal-weight average of run MAPEs when coverage changes between runs.

## How much confidence does this support?

For full harness minus vanilla, paired count error is **6.69 percentage points
higher**, with an exploratory 95% image-bootstrap interval of **+0.07 to +13.38 pp**,
on the 31 images where both returned numeric answers in all three repetitions.
This comparison favors vanilla on that subset; it does not include the six other
images. Across all 37 images, the harness's within-10% success difference is
**−14.41 pp**, but its interval is **−34.23 to +6.31 pp**, spanning zero.

Cellpose ties vanilla's observed all-attempt success rate. Its paired count-error
difference is +4.10 pp, with a −1.98 to +11.65 pp interval on 35 complete images;
this does not establish a reliable count-accuracy difference between them.

As an additional, explicitly post-scoring check, all compared arms return three
numeric answers on the same 30 images. On that common subset, vanilla has 11.15%
MAPE, full harness 16.76%, Astra-tools 19.50%, and Cellpose 14.51%. The harness's
weaker result therefore persists when all compared arms use exactly the same
complete cases. This selected subset is a diagnostic, not a replacement cohort.

Three repeats measure run variation; they do not turn 37 images into 111
independent examples. Bootstrap intervals resample images after averaging within
each image, using 10,000 draws. Tissue fields can share biological origins, so
these are not patient-level intervals. Comparisons are exploratory, without
multiple-comparison adjustment. Public checkpoint exposure to this dataset is
unknown. Zero run SD for a fixed procedure does not mean zero uncertainty on new
images.

## These images expose real failures, but not every field is difficult

Vanilla produced **15 numeric estimates with more than 20% error**, plus four
abstentions. The full harness produced 28 such estimates, plus ten abstentions.
Cellpose produced 21 estimates with more than 20% error and no abstentions.

The published GNB-II group has three images and nine attempts: vanilla's MAPE is
31.29%, full harness 24.27%, and Cellpose 11.87%, all with complete coverage.
NB-I has three images: vanilla 22.69%, full 18.26%, but Cellpose 53.47%.
The two tissue-section fields have 33.05% vanilla error, 51.65% full-harness error,
and 39.34% Cellpose error. Conversely, several normal-cell groups are easy for
vanilla. We retain all ten published groups rather than selecting only cases
where a desired model wins.

Illustrative cases, selected after scoring for explanation:

- `Ganglioneuroblastoma_6.tif`: reference 75; vanilla 37, 52, 48;
  harness 86, 93, 86; Cellpose 69, 69, 69. A specialist helps substantially here.
- `normal_40.tif`: reference 71; vanilla 59, 58, 61;
  harness 71, 71, 71. The routed specialist resolves this counting failure.
- `otherspecimen_3.tif`: reference 55; vanilla 86, 85, 86;
  harness 111, 111, 111; Cellpose 98, 98, 98. All these approaches fail here.
- `Neuroblastoma_17.tif`: reference 12; vanilla 10, 10, 10;
  harness 13, 13, 13; Cellpose 26, 26, 26. A globally stronger specialist is not
  necessarily the right specialist for a particular image.

## Selection is still weak; review is not an accuracy guarantee

Astra preferred StarDist sensitive on 84/111 trials and default on 27/111; it
never preferred the other two procedures. Jev chose default on 95/111, sensitive
on eight, Cellpose on six, and conservative on two. Jev selected a lowest-count-error
candidate, including ties, on **20/111 trials (18.0%)**. Its selected mask's error
exceeded the hindsight best available candidate by 15.83 pp on average. Hindsight
uses the reference labels and is a diagnostic, not a deployable selector.

Using every raw selected measurement, including those Astra later declined to
endorse, Jev-selected masks have 24.44% MAPE versus 30.95% for Astra-preferred
masks. This supports an improvement over Astra's particular preference in this
run, but fixed Cellpose's 13.41% is lower than either. The lower final harness
error of 16.90% also reflects its withholding ten estimates; it is not evidence
that Astra corrected those mask counts. Numeric answers are constrained to the
selected mask's measured count.

Jev reviewed all 111 selected results: **four supported numeric answers, 97
caution numeric answers, and ten caution abstentions**. The ten abstentions
already existed in Astra's pre-review answer; they are not timeouts or Jev
rejections. All selected numeric counts stayed unchanged through review.
Two of the four supported answers are within 10% of reference. Merely accepting
supported answers would return 4/111 counts with 12.32% conditional error and
2/111 all-attempt successes; this is a diagnostic filter, not a separately run
replanning system.

The current route retains caution estimates. The historical hard-approval,
multi-round replanning loop was not rerun here. Jev sees structured evidence and
Astra's attributed descriptions, not the pixels. Its support scores have not
been calibrated as probabilities of benchmark correctness.

## Repetition and mask quality

Every fixed procedure was actually executed three times per image. All four
procedures produced **bit-for-bit identical label maps on all 37 images** under
these fixed weights, preprocessing, parameters and hardware. This establishes
observed repeatability here, not accuracy or universal determinism.

Vanilla's three numeric counts are identical on only 5/35 images with complete
numeric coverage; the full harness's are identical on 23/33. Mean within-image
count SD is 4.65 nuclei for vanilla and 1.52 for full, on their respective complete
subsets. The harness is more repeatable here while having worse average errors.

Mean per-image instance F1 at IoU ≥0.5 is 0.880 for Cellpose, 0.807 for StarDist
conservative, 0.796 for default and 0.782 for sensitive. Selected harness masks
average 0.805. These use one-to-one object matching against the expert masks;
matching score is TP/(TP+FP+FN), not COCO AP. Vanilla returns counts, not masks,
so it has no comparable segmentation score. Accurate counts alone do not prove
that the correct individual nuclei were found.

## Execution and verification

All 111 scheduled trials finished with **no terminal API, parsing, worker or
orchestration errors**. Four vanilla calls hit the output-token limit and used
the preconfigured single retry; all responses and retry events were retained.
There were 559 Astra and 222 Jev calls, all 781 with saved response records.
No inference prompts, thresholds, candidate weights or code changed mid-run.
Test labels were decoded only after the final inference-finished marker.

All 333 Harbor ATIF trajectories validate. The audit checks 444 masks, 66,432
predicted instance areas and 111 routing decisions frozen before execution.
An independent Pillow decoder reproduces all 37 reference counts. Native Mac
processes performed the inference, with Harbor trace export and validation;
these were not Harbor Docker evaluation jobs.

Observed mean vanilla latency was 41.6 seconds and full input-to-final latency
51.2 seconds. Execution was concurrent and included resource queues, so these
are not isolated production latency measurements. The Astra-tools branch's
8.7 seconds covers its answer call only and is not comparable end-to-end timing.
The full metric excludes subsequent evaluation-only competing model runs.
Token usage is preserved; dollar cost is not inferred without versioned prices.

## What this changes about the project

This is evidence against claiming that the current router improves counting
overall. It is also evidence that specialist gains depend on the image and task:
we have both useful corrections and substantial specialist failures.

A next development experiment should allow the visual-only answer as an explicit
candidate, use observable mask-quality and model-disagreement evidence for routing,
and learn/calibrate decisions on separate development data. Review should be
tested for its ability to predict actual errors, including its coverage tradeoff.
These are hypotheses for the next frozen experiment, not changes applied to this
test. Any policy adjusted using these results needs fresh evaluation data before
claiming a gain.
