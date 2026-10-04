# Combined repeated comparison

> Infrastructure interruption: macOS sleep logs show the laptop repeatedly slept while requests were active. The recorded failures remain in the denominator. These numbers describe this interrupted deployment run; they are not a clean estimate of the harness's accuracy or latency relative to vanilla. [Host evidence](host-sleep-events.txt).

12 BBBC039 images × 3 repetitions × 3 conditions = **108 unique trials**. The 36 vanilla trials are shared by both comparisons.

| Condition | Counts returned | Within 10% | Conditional MAPE | Mean recorded runtime |
|---|---:|---:|---:|---:|
| Vanilla Astra | 36/36 | 32/36 (88.89%) | 5.62% | 46.92 s |
| Full harness · 48 KB | 6/36 | 4/36 (11.11%) | 7.52% | 715.96 s |
| Full harness · 96 KB | 12/36 | 11/36 (30.56%) | 4.95% | 749.51 s |

All planned trials remain in each condition's denominator. The 96 KB follow-up uses the same cohort and all controls; it is not an independent new validation set.

- 48 KB minus vanilla: -77.78 percentage points, with an image-cluster bootstrap 95% interval of [-91.67, -61.11].
- 96 KB minus vanilla: -58.33 percentage points, with an image-cluster bootstrap 95% interval of [-72.22, -44.44].

These descriptive intervals use 12 image clusters, not 36 independent images. Conditional MAPE excludes missing answers and must be read with coverage. Extra research, pixels, code and inference are bundled, so Jev's causal contribution is not isolated.

[Visual comparison and all repeated counts](comparison.html) · [Original traces](index.html) · [96 KB traces](test-transport96/index.html) · [Amendment](transport-amendment.md)
