# BBBC001v1: real microscopy benchmark

Lowest error among modes answering all six images: Vanilla Astra (11.64%).

Complete published six-image cell-counting dataset; 2 modes, one attempt each. Lower percentage error is better. No invented images or labels.

| Mode | Valid counts | Published metric | Answered-subset error | Abstained | Errors | Mean time |
|---|---:|---:|---:|---:|---:|---:|
| Vanilla Astra | 6/6 | 11.64% | 11.64% | 0 | 0 | 93.9s |
| Full harness | 0/6 | Incomplete | Incomplete | 3 | 3 | 326.1s |

An incomplete run has no official full-dataset metric. Answered-subset errors use different image subsets and must not be ranked against complete scores.

## Predictions

| Image | Human counts | Reference mean | Vanilla Astra | Full harness |
|---|---|---|---|---|
| BBBC001 field 1 | [350, 362] | 356.0 | 390.0 (9.55% error) | error |
| BBBC001 field 2 | [336, 342] | 339.0 | 385.0 (13.57% error) | error |
| BBBC001 field 3 | [396, 447] | 421.5 | 480.0 (13.88% error) | abstained |
| BBBC001 field 4 | [320, 341] | 330.5 | 360.0 (8.93% error) | abstained |
| BBBC001 field 5 | [398, 533] | 465.5 | 545.0 (17.08% error) | abstained |
| BBBC001 field 6 | [241, 257] | 249.0 | 266.0 (6.83% error) | error |

## Method and limits

Mean over all six images of 100 * abs(prediction - mean(two human counts)) / mean(two human counts); lower is better.

Lossless 8-bit grayscale TIFF to RGB PNG by channel replication. No resize, contrast adjustment, denoising, annotation overlays or synthetic pixels.

BBBC001 has no official train/test split. 'test' is a local Harbor routing label only.

- Only six images from one experiment, not broad multimodal evidence.
- Published human counts disagree; their mean is the reference, not an exact biological truth.
- Current OpenCV tools are color/white-background tools, not microscopy segmentation models.
- Independent plans and different compute per mode prevent a clean causal estimate of Jev selection alone.
- This is a retest of previously inspected benchmark images after integration fixes.
- Incomplete modes receive a completion rate and answered-subset error, not a fabricated full-benchmark error.
- No changes during this run. One attempt per mode per image; no claims of a stable overall ranking.
- The variant jointly changes feedback, acceptance checks, retry budget and repeat detection; it does not isolate one component causally.
- Numerical proposals before review are diagnostic and do not replace rejected final answers.

Source: [BBBC001v1: structured review loop versus vanilla Astra](https://bbbc.broadinstitute.org/BBBC001). BBBC001v1, Moffat et al. (Cell, 2006), Broad Bioimage Benchmark Collection; Ljosa et al. (Nature Methods, 2012).

[CC BY-NC-SA 3.0; images and ground truth by David Root and Anne Carpenter.](https://creativecommons.org/licenses/by-nc-sa/3.0/)

Token totals include only recorded usage. An interrupted/failed parse may leave an unrecorded call; compare started_calls and calls in results.json. Runtime excludes container setup.

View traces: `uv run harbor view jobs/bbbc001-loop-20260922`
