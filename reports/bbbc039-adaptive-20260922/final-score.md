# Adaptive StarDist and Jev condition review

New project cohort: six preselected images from the official BBBC039 test split. This is a derived nucleus-count task, not the published instance-segmentation benchmark metric. Lower count error is better; coverage is not exact-match accuracy.

| Configuration | Final counts | Full-cohort error | Answered-subset error | Abstained | Errors | Mean time |
|---|---:|---:|---:|---:|---:|---:|
| Fixed default StarDist | 6/6 | 9.72% | 9.72% | 0 | 0 | 1.0 s |
| Vanilla Astra | 6/6 | 10.03% | 10.03% | 0 | 0 | 34.3 s |
| Astra + adaptive StarDist | 6/6 | 9.72% | 9.72% | 0 | 0 | 36.6 s |
| Astra + StarDist + Jev selection | 6/6 | 9.20% | 9.20% | 0 | 0 | 40.7 s |
| Full condition-review harness | 2/6 | Incomplete | 7.72% | 3 | 1 | 195.9 s |

## Post-hoc fixed-profile diagnostic

Using the sensitive profile uniformly on all six images yields 7.94% mean error. This is a post-hoc calculation from measurements already saved in the selection arm, not a preregistered arm or a new inference run. It applies one fixed rule to every image, without choosing the best profile separately for each annotation. Compare adaptive choices with this simpler explanation before attributing a gain to orchestration.

[Exact diagnostic and source traces](fixed-sensitive-diagnostic.json) · [When and why it was added](fixed-profile-diagnostic-policy.json)

Incomplete arms have no full-cohort error. Subset errors use only answered images and cannot establish a win over complete arms. Runtime excludes container setup; standalone includes adapter execution and its first model load. Interrupted request usage may be unknown.

## Did orchestration improve fixed StarDist?

| Arm | Matched images | Different counts | Closer | Worse | Tied | Full-cohort error change (negative helps) |
|---|---:|---:|---:|---:|---:|---:|
| Vanilla Astra | 6/6 | 4 | 2 | 2 | 2 | +0.31 pp |
| Astra + adaptive StarDist | 6/6 | 0 | 0 | 0 | 6 | +0.00 pp |
| Astra + StarDist + Jev selection | 6/6 | 3 | 3 | 0 | 3 | -0.52 pp |
| Full condition-review harness | 2/6 | 0 | 0 | 0 | 2 | Incomplete |

## Counts on each image

| Image | Annotation count | Fixed StarDist | Vanilla Astra | Astra + adaptive StarDist | Astra + StarDist + Jev selection | Full condition-review harness |
|---|---:|---:|---:|---:|---:|---:|
| BBBC039 test image 1 | 62 | 52 | 52.0 | 52.0 | 53.0 | abstained |
| BBBC039 test image 2 | 82 | 76 | 73.0 | 76.0 | 76.0 | 76.0 |
| BBBC039 test image 3 | 119 | 108 | 110.0 | 108.0 | 109.0 | abstained |
| BBBC039 test image 4 | 197 | 181 | 185.0 | 181.0 | 181.0 | 181.0 |
| BBBC039 test image 5 | 119 | 102 | 102.0 | 102.0 | 102.0 | abstained |
| BBBC039 test image 6 | 156 | 151 | 148.0 | 151.0 | 152.0 | error |

## Full-chain proposals, before acceptance

- first numerical candidate: 6/6, 9.20% full-cohort error; 9.20% answered-subset error.
- last numerical candidate: 6/6, 9.48% full-cohort error; 9.48% answered-subset error.

First/last policies are fixed and include rejected proposals. No best-of-N selection; these do not replace accepted-output scores.

## Method and limits

- Only six of 50 official test images; one primary attempt per mode; exploratory not a conclusive population estimate
- Images are new to this project, but public-model training exposure is unknown and BBBC039 partly overlaps DSB2018
- Annotation-derived nucleus-count MAPE is a local task, not the official segmentation benchmark metric
- All arms use identical 8-bit display conversion of original 16-bit TIFFs; this is not lossless radiometric preservation
- All Astra arms share the adaptive system prompt; vanilla receives image plus empty evidence, no tools or Jev
- Independent planning and unequal compute prevent a causal estimate of Jev alone
- Jev gets supplied metadata and structured measurements, not image pixels or ground truth; its scores are uncalibrated
- No arbitrary code, scale changes, continuous threshold tuning, or mask editing; choices are bounded to three fixed profiles and crops
- A more appropriate estimate policy may improve coverage without improving perception; these outcomes must be distinguished

BBBC039v1, Caicedo et al. 2018, Broad Bioimage Benchmark Collection; Ljosa et al., Nature Methods 2012. [CC0](https://creativecommons.org/publicdomain/zero/1.0/). [Dataset and annotation documentation](https://bbbc.broadinstitute.org/BBBC039).

[Visual report](index.html) · [Frozen protocol](protocol.json) · [All results and trace links](results.json) · [Implementation file map](../../docs/adaptive-stardist.md)
