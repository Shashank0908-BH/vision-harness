# Larger repeated stress test

Use the entire official 37-image test split of Kromp et al.'s expert-annotated
fluorescence nucleus dataset (BioImage Archive S-BIAD634; original S-BSST265).
The authors deliberately varied sample preparation, magnification, modality and
signal/noise, including clustered and partially overlapping nuclei. No synthetic
images, artificial corruption, outcome-based image selection or new model tuning.

Sources: [paper](https://www.nature.com/articles/s41597-020-00608-w),
[official archive](https://www.ebi.ac.uk/biostudies/BioImages/studies/S-BIAD634).

| File | Role |
|---|---|
| `evals/repeated/data.py` | Download official metadata, freeze all test filenames, prepare identical image-only inputs, save source hashes. |
| `evals/repeated/runner.py` | Three fresh repetitions, shuffled paired execution, bounded local model concurrency, preserved errors, and ablation answers. |
| `evals/repeated/metrics.py` | Read labels after inference; count error, instance matching, run variation, clustered paired bootstrap intervals. |
| `evals/repeated/report.py` | Paginated offline review of aggregate and per-image/repetition outcomes. |
| `tests/test_repeated.py` | Matching, failure accounting, repeated-measure aggregation and cohort integrity checks. |

The existing runtime, catalog, weights, prompts and review threshold are frozen.
Each image gets three fresh hosted-model sequences and three actual executions of
each fixed specialist procedure. No saved prior predictions substitute for repeats.
Model training exposure to this public dataset is unknown.

Comparisons:

1. Fresh vanilla Astra, same image and annotation-aware question.
2. Four fixed specialists, with repeated actual masks and count stability checked.
3. Astra's preferred specialist plus a separately generated, grounded Astra answer.
   This paired ablation shares the full route's initial intent/proposal, but the
   answer sees only that preferred procedure's own evidence, never Jev's selection
   or other masks. It is not an independently replanned arm.
4. Astra + specialist + Jev selection: the saved pre-review candidate answer from
   the full route. This is an exact stage ablation, not an independent full run.
5. Full current route, including review. `supported` and `caution` estimates remain
   distinct; timeouts, unsupported inputs and abstentions count as missing outputs.
6. A strict-support-only diagnostic shows what coverage would be if caution answers
   were suppressed. This is not a rerun of the historical multi-round review loop.

Other procedure outputs are generated only after the selected answer/review. If a
route fails, remaining fixed procedures are still evaluated independently; an already
attempted failed inference is not retried. Failure completion never repairs the
failed harness answer. Every provider request/response and attempt is retained.

The model question describes the published annotation criteria (intact, in-focus
nuclei; damaged nuclei excluded; dividing nuclei combined unless clearly separated).
Only task semantics and pixels are sent. Test-class labels, signal/noise metadata,
reference counts and masks remain outside provider context. Preserving the original
8-bit intensities avoids test-specific contrast tuning. No spatial resizing.

Three repetitions measure model/API variation; they do not make 37 images into 111
independent images. Report each repetition's cohort result, mean and sample standard
deviation, per-image mean absolute percentage error, per-image prediction variation,
and image-clustered bootstrap intervals for paired differences (10,000 draws, fixed
seed). Also report the percentage with count error <=5%, <=10%, and >20%.

Incomplete arms have no unconditional numeric MAPE. Conditional error must be named
as such and shown with coverage. All-attempt <=10% success treats missing outputs as
failures, preventing an abstaining system from appearing better by omission. Compare
errors on paired complete cases separately and disclose that subset. No statistical
claim based on treating repeated calls or correlated tissue fields as new patients.

Instance segmentation uses maximum-cardinality one-to-one matching at IoU >=0.5,
with precision, recall, F1 and TP/(TP+FP+FN) reported. This last quantity is an
instance matching score, not COCO average precision. Vanilla's count-only output
cannot receive a mask-quality score. The published low-SNR/clustered strata are
reported separately, but not used to cherry-pick a winning model.

Concurrency is fixed at six image/repetition jobs, at most three native workers,
and at most one Cellpose MPS worker. Timing includes resource contention and is
therefore a benchmark throughput measurement, not isolated production latency.
Only the already configured schema/output-budget retry is allowed. No outcome,
HTTP error or timeout retries. Completed attempts are immutable and resumable.
