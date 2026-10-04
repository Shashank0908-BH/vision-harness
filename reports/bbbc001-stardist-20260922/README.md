# BBBC001v1: real microscopy benchmark

Lowest error among modes answering all six images: Astra + StarDist (6.67%).

Complete published six-image cell-counting dataset; 3 modes, one attempt each. Lower percentage error is better. No invented images or labels.

| Mode | Valid counts | Published metric | Answered-subset error | Abstained | Errors | Mean time |
|---|---:|---:|---:|---:|---:|---:|
| Vanilla Astra | 5/6 | Incomplete | 17.64% | 0 | 1 | 90.7s |
| Astra + StarDist | 6/6 | 6.67% | 6.67% | 0 | 0 | 33.2s |
| Full harness: Astra + StarDist + Jev selection/review loop | 0/6 | Incomplete | Incomplete | 6 | 0 | 114.0s |

An incomplete run has no official full-dataset metric. Answered-subset errors use different image subsets and must not be ranked against complete scores.

## Predictions

| Image | Human counts | Reference mean | Vanilla Astra | Astra + StarDist | Full harness: Astra + StarDist + Jev selection/review loop |
|---|---|---|---|---|---|
| BBBC001 field 1 | [350, 362] | 356.0 | 490.0 (37.64% error) | 375.0 (5.34% error) | abstained |
| BBBC001 field 2 | [336, 342] | 339.0 | 391.0 (15.34% error) | 354.0 (4.42% error) | abstained |
| BBBC001 field 3 | [396, 447] | 421.5 | error | 456.0 (8.19% error) | abstained |
| BBBC001 field 4 | [320, 341] | 330.5 | 362.0 (9.53% error) | 349.0 (5.60% error) | abstained |
| BBBC001 field 5 | [398, 533] | 465.5 | 544.0 (16.86% error) | 529.0 (13.64% error) | abstained |
| BBBC001 field 6 | [241, 257] | 249.0 | 271.0 (8.84% error) | 256.0 (2.81% error) | abstained |

## Method and limits

Mean over all six images of 100 * abs(prediction - mean(two human counts)) / mean(two human counts); lower is better.

Same losslessly replicated grayscale PNG for all modes. StarDist normalizes intensities at percentiles 1/99.8 inside its tool; default/sensitive/conservative threshold profiles are fixed in code. Crops are traceable. No benchmark-specific segmentation tuning.

BBBC001 has no official train/test split. 'test' is a local Harbor routing label only.

- Six previously inspected development images, not a held-out sample.
- Prior pretraining exposure to public microscopy images cannot be ruled out.
- Human counts disagree; their mean is the scoring reference.
- One attempt per mode; stochastic baseline variation remains.
- Full chain retains Jev selection and all five review requirements at 0.75 with bounded replanning; abstentions do not earn a full-dataset score.
- Jev sees structured evidence summaries, not image pixels. Astra receives originals and selected overlays/crops.
- Threshold profiles use the same model and do not constitute independent corroboration.
- Count labels alone cannot establish mask precision/recall.
- Standalone baseline is a deterministic default-tool control, reproduced inside the specialist container; new harness modes use independent Astra plans.
- First and last candidate counts will be scored separately from accepted final answers; no best-of-N selection.

Source: [BBBC001v1: StarDist full-chain test with fresh vanilla and Astra+StarDist ablation](https://bbbc.broadinstitute.org/BBBC001). BBBC001v1, Moffat et al. (Cell, 2006), Broad Bioimage Benchmark Collection; Ljosa et al. (Nature Methods, 2012).

[CC BY-NC-SA 3.0; images and ground truth by David Root and Anne Carpenter.](https://creativecommons.org/licenses/by-nc-sa/3.0/)

Token totals include only recorded usage. An interrupted/failed parse may leave an unrecorded call; compare started_calls and calls in results.json. Runtime excludes container setup.

View traces: `uv run harbor view jobs/bbbc001-stardist-20260922`
