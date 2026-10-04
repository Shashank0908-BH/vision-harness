# BBBC001v1: real microscopy benchmark

Lowest error among modes answering all six images: Vanilla Astra (10.30%).

Complete published six-image cell-counting dataset; 2 modes, one attempt each. Lower percentage error is better. No invented images or labels.

| Mode | Valid counts | Published metric | Answered-subset error | Abstained | Errors | Mean time |
|---|---:|---:|---:|---:|---:|---:|
| Vanilla Astra | 6/6 | 10.30% | 10.30% | 0 | 0 | 76.5s |
| Full harness | 0/6 | Incomplete | Incomplete | 6 | 0 | 234.4s |

An incomplete run has no official full-dataset metric. Answered-subset errors use different image subsets and must not be ranked against complete scores.

## Predictions

| Image | Human counts | Reference mean | Vanilla Astra | Full harness |
|---|---|---|---|---|
| BBBC001 field 1 | [350, 362] | 356.0 | 400.0 (12.36% error) | abstained |
| BBBC001 field 2 | [336, 342] | 339.0 | 370.0 (9.14% error) | abstained |
| BBBC001 field 3 | [396, 447] | 421.5 | 475.0 (12.69% error) | abstained |
| BBBC001 field 4 | [320, 341] | 330.5 | 340.0 (2.87% error) | abstained |
| BBBC001 field 5 | [398, 533] | 465.5 | 560.0 (20.30% error) | abstained |
| BBBC001 field 6 | [241, 257] | 249.0 | 260.0 (4.42% error) | abstained |

## Method and limits

Mean over all six images of 100 * abs(prediction - mean(two human counts)) / mean(two human counts); lower is better.

Lossless 8-bit grayscale TIFF to RGB PNG by channel replication. No resize, contrast adjustment, denoising, annotation overlays or synthetic pixels.

BBBC001 has no official train/test split. 'test' is a local Harbor routing label only.

- Only six images from one experiment, not broad multimodal evidence.
- Published human counts disagree; their mean is the reference, not an exact biological truth.
- Current OpenCV tools are color/white-background tools, not microscopy segmentation models.
- Independent plans and different compute per mode prevent a clean causal estimate of Jev selection alone.
- No changes during this run; one attempt per image/mode, with the configured bounded per-call format retry.
- This is a retest of previously inspected benchmark images after integration fixes.
- Incomplete modes receive a completion rate and answered-subset error, not a fabricated full-benchmark error.

Source: [BBBC001v1: repaired full harness versus vanilla Astra](https://bbbc.broadinstitute.org/BBBC001). BBBC001v1, Moffat et al. (Cell, 2006), Broad Bioimage Benchmark Collection; Ljosa et al. (Nature Methods, 2012).

[CC BY-NC-SA 3.0; images and ground truth by David Root and Anne Carpenter.](https://creativecommons.org/licenses/by-nc-sa/3.0/)

Token totals include only recorded usage. An interrupted/failed parse may leave an unrecorded call; compare started_calls and calls in results.json. Runtime excludes container setup.

View traces: `uv run harbor view jobs/bbbc001-full-repaired-20260922`
