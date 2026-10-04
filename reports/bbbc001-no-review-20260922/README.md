# BBBC001v1: real microscopy benchmark

Lowest error among modes answering all six images: Tools + Jev selection (14.27%).

Complete published six-image cell-counting dataset; 3 modes, one attempt each. Lower percentage error is better. No invented images or labels.

| Mode | Valid counts | Published metric | Answered-subset error | Abstained | Errors | Mean time |
|---|---:|---:|---:|---:|---:|---:|
| Vanilla Astra | 6/6 | 17.34% | 17.34% | 0 | 0 | 100.3s |
| Astra + OpenCV | 6/6 | 16.16% | 16.16% | 0 | 0 | 95.1s |
| Tools + Jev selection | 6/6 | 14.27% | 14.27% | 0 | 0 | 107.6s |

An incomplete run has no official full-dataset metric. Answered-subset errors use different image subsets and must not be ranked against complete scores.

## Predictions

| Image | Human counts | Reference mean | Vanilla Astra | Astra + OpenCV | Tools + Jev selection |
|---|---|---|---|---|---|
| BBBC001 field 1 | [350, 362] | 356.0 | 395.0 (10.96% error) | 400.0 (12.36% error) | 400.0 (12.36% error) |
| BBBC001 field 2 | [336, 342] | 339.0 | 330.0 (2.65% error) | 380.0 (12.09% error) | 370.0 (9.14% error) |
| BBBC001 field 3 | [396, 447] | 421.5 | 495.0 (17.44% error) | 500.0 (18.62% error) | 500.0 (18.62% error) |
| BBBC001 field 4 | [320, 341] | 330.5 | 460.0 (39.18% error) | 370.0 (11.95% error) | 365.0 (10.44% error) |
| BBBC001 field 5 | [398, 533] | 465.5 | 565.0 (21.37% error) | 640.0 (37.49% error) | 580.0 (24.60% error) |
| BBBC001 field 6 | [241, 257] | 249.0 | 280.0 (12.45% error) | 260.0 (4.42% error) | 275.0 (10.44% error) |

## Method and limits

Mean over all six images of 100 * abs(prediction - mean(two human counts)) / mean(two human counts); lower is better.

Lossless 8-bit grayscale TIFF to RGB PNG by channel replication. No resize, contrast adjustment, denoising, annotation overlays or synthetic pixels.

BBBC001 has no official train/test split. 'test' is a local Harbor routing label only.

- Only six images from one experiment, not broad multimodal evidence.
- Published human counts disagree; their mean is the reference, not an exact biological truth.
- Current OpenCV tools are color/white-background tools, not microscopy segmentation models.
- One attempt per image/mode. Execution-to-execution variability prevents a stable overall ranking from one small cohort.
- Different plans, image inputs and inference budgets mean this compares whole systems rather than isolating a causal contribution from Jev.
- No inference changes during this run. All outcomes are retained; failed attempts are not replaced.
- This is a retest of previously inspected images. Earlier experiments are not pooled or substituted for current results.
- Incomplete modes receive coverage and a labeled subset error, not a fabricated full-benchmark error.

Source: [BBBC001v1: vanilla versus tools and Jev selection, answer review disabled](https://bbbc.broadinstitute.org/BBBC001). BBBC001v1, Moffat et al. (Cell, 2006), Broad Bioimage Benchmark Collection; Ljosa et al. (Nature Methods, 2012).

[CC BY-NC-SA 3.0; images and ground truth by David Root and Anne Carpenter.](https://creativecommons.org/licenses/by-nc-sa/3.0/)

Token totals include only recorded usage. An interrupted/failed parse may leave an unrecorded call; compare started_calls and calls in results.json. Runtime excludes container setup.

View traces: `uv run harbor view jobs/bbbc001-no-review-20260922`
