# What the adaptive-tool experiment established

Astra now chooses how to use StarDist without a prescribed default-first workflow. Jev scores proposed conditions and, in full mode, checks actual input suitability, parameter justification, coverage and count derivation. The mechanism works, but this experiment does not establish an accuracy advantage over a simple fixed sensitive profile.

## Primary comparison

Six images were selected from the official BBBC039 test partition by a fixed filename hash before image/annotation downloads. They are new to this project's experiments. All live arms used identical images and the same Astra system prompt; vanilla had no tools or Jev. No inference policy changed during the run.

| Configuration | Final counts | Full-cohort mean error | Mean seconds |
|---|---:|---:|---:|
| Vanilla Astra | 6/6 | 10.03% | 34.3 |
| Fixed default StarDist | 6/6 | 9.72% | See raw control timing |
| Astra + adaptive StarDist | 6/6 | 9.72% | 36.6 |
| Astra + StarDist + Jev selection | 6/6 | 9.20% | 40.7 |
| Full condition-review harness | 2/6 | Incomplete | 195.9 |

Selection chose the sensitive result on images 1, 3 and 6: 52→53, 108→109 and 151→152, against annotation counts 62, 119 and 156. All three changes helped; the remaining outputs matched default. Aggregate error fell by 0.52 percentage points. Astra without Jev selected all six defaults. Independent planning means this is a whole-policy difference, not an isolated causal estimate of Jev.

## A simpler policy explains more of the gain

After observing those choices, we checked the fixed sensitive profile on every image using measurements already present in all six selection traces. That uniform rule scores **7.94%**: closer than adaptive selection on three images, tied on three. It improves on fixed default on all six.

This is explicitly a **post-hoc diagnostic**, not a preregistered arm, new inference run, per-image oracle or evidence that sensitive always wins. No thresholds were optimized against annotations. It shows why improvement over default does not establish a need for LLM orchestration: one simpler fixed setting did better on this cohort. See [diagnostic policy](fixed-profile-diagnostic-policy.json) and [trace-backed calculation](fixed-sensitive-diagnostic.json).

## What full review did

Full mode accepted images 2 and 4 at counts 76 and 181, both identical to fixed default. It abstained on images 1, 3 and 5. Image 6 ended in an **Astra structured-output limit error**, after the existing bounded format retry was exhausted. This was not an API timeout or a Jev API failure. No extra retries followed the outcomes.

First numerical proposals scored **9.20%** across all six images; last numerical proposals scored **9.48%**. Replanning changed image 5 from 102 to 100, farther from its annotation count of 119. Other numerical proposals stayed unchanged. These diagnostics do not replace final accepted answers. Full's 7.72% answered-subset error covers only two images and is not a complete score or a win.

Domain/target checks generally supported using the fluorescence-nucleus model. Failures concentrated on parameter justification and numerical grounding. More crops and repeated assessments did not resolve those judgments. The two accepted proposals passed all five unchanged 0.75 requirements. The policy can now accept an estimated count, but still rejects useful estimates and makes the loop expensive. More approvals alone would not establish better perception.

Jev receives structured measurements and stated microscopy metadata, not raw image pixels. Its scores are model judgments, not calibrated truth probabilities. These are all in-domain fluorescence images; this cohort does not test reliable rejection of out-of-domain uses or false modality metadata. That requires a separate applicability evaluation.

## Verification and limits

All 24 Harbor trajectories validate, all 24 verifier outputs independently reproduce, and all 99 provider calls have saved responses. All 35 Jev calls succeeded: 22 plan assessments and 13 reviews. The audit checked 59 instance maps, including six controls, and all 5,133 instance geometries. All 24 live default whole-image masks match their controls pixel for pixel. Annotation partitions match the official decoder; a separate TIFF reader reproduces display conversion. Frozen source, checkpoint, input and dependency hashes match; actual API keys were absent from logs/reports. The integration has 44 passing local tests.

This derived nucleus-count task is not BBBC039's official instance-segmentation metric. Fixed percentile conversion maps the original 16-bit TIFFs to identical 8-bit inputs in every arm. Pretrained-model exposure is unknown; BBBC039 partly overlaps DSB2018. These scores cannot be compared directly with the earlier 6.67% on different BBBC001 images.

Next, preregister all fixed profiles as controls on a larger new cohort, and evaluate Jev against explicit valid/invalid conditions of use. Judge review accuracy and runtime alongside count error. This recommendation does not change or rerun the frozen experiment.

[Visual report](index.html) · [Exact counts](final-score.md) · [All results](results.json) · [Audit](verification.json) · [Frozen protocol](protocol.json) · [File map](../../docs/adaptive-stardist.md)
