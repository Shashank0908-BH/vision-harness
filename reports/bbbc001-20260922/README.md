# BBBC001v1: real microscopy benchmark

Lowest error among modes answering all six images: Tools + Jev selection (11.36%).

Complete published six-image cell-counting dataset; five modes, one attempt each. Lower percentage error is better. No invented images or labels.

| Mode | Valid counts | Published metric | Answered-subset error | Abstained | Errors | Mean time |
|---|---:|---:|---:|---:|---:|---:|
| Vanilla Astra | 6/6 | 14.08% | 14.08% | 0 | 0 | 67.0s |
| Astra + OpenCV | 6/6 | 12.78% | 12.78% | 0 | 0 | 82.1s |
| Tools + Jev selection | 6/6 | 11.36% | 11.36% | 0 | 0 | 85.3s |
| Tools + Jev review | 0/6 | Incomplete | Incomplete | 4 | 2 | 153.2s |
| Full harness | 0/6 | Incomplete | Incomplete | 5 | 1 | 170.6s |

An incomplete run has no official full-dataset metric. Answered-subset errors use different image subsets and must not be ranked against complete scores.

## Predictions

| Image | Human counts | Reference mean | Vanilla Astra | Astra + OpenCV | Tools + Jev selection | Tools + Jev review | Full harness |
|---|---|---|---|---|---|---|---|
| BBBC001 field 1 | [350, 362] | 356.0 | 410.0 (15.17% error) | 390.0 (9.55% error) | 385.0 (8.15% error) | abstained | error |
| BBBC001 field 2 | [336, 342] | 339.0 | 390.0 (15.04% error) | 375.0 (10.62% error) | 375.0 (10.62% error) | error | abstained |
| BBBC001 field 3 | [396, 447] | 421.5 | 480.0 (13.88% error) | 510.0 (21.00% error) | 505.0 (19.81% error) | abstained | abstained |
| BBBC001 field 4 | [320, 341] | 330.5 | 370.0 (11.95% error) | 360.0 (8.93% error) | 340.0 (2.87% error) | error | abstained |
| BBBC001 field 5 | [398, 533] | 465.5 | 540.0 (16.00% error) | 550.0 (18.15% error) | 560.0 (20.30% error) | abstained | abstained |
| BBBC001 field 6 | [241, 257] | 249.0 | 280.0 (12.45% error) | 270.0 (8.43% error) | 265.0 (6.43% error) | abstained | abstained |

## Method and limits

Mean over all six images of 100 * abs(prediction - mean(two human counts)) / mean(two human counts); lower is better.

Lossless 8-bit grayscale TIFF to RGB PNG by channel replication. No resize, contrast adjustment, denoising, annotation overlays or synthetic pixels.

BBBC001 has no official train/test split. 'test' is a local Harbor routing label only.

- Only six images from one experiment, not broad multimodal evidence.
- Published human counts disagree; their mean is the reference, not an exact biological truth.
- Current OpenCV tools are color/white-background tools, not microscopy segmentation models.
- Independent plans and different compute per mode prevent a clean causal estimate of Jev selection alone.
- No model/rubric/threshold tuning or selective retry after outcomes.

Source: [Complete BBBC001v1 counting benchmark](https://bbbc.broadinstitute.org/BBBC001). BBBC001v1, Moffat et al. (Cell, 2006), Broad Bioimage Benchmark Collection; Ljosa et al. (Nature Methods, 2012).

[CC BY-NC-SA 3.0; images and ground truth by David Root and Anne Carpenter.](https://creativecommons.org/licenses/by-nc-sa/3.0/)

Token totals include only recorded usage. An interrupted/failed parse may leave an unrecorded call; compare started_calls and calls in results.json. Runtime excludes container setup.

View traces: `uv run harbor view jobs/bbbc001-20260922`

## User-requested Jev retry

The user-requested Jev retry succeeded after bounding the evidence payload. It returned support 0.56, compared with the unchanged 0.75 acceptance threshold. The original frozen benchmark remains below; the repaired retry is separate. The latest Harbor recovery finished with status abstained and no API/parsing exception.

See [recovery evidence](jev-recovery-field4/result.json) and [failure analysis](findings.md).
