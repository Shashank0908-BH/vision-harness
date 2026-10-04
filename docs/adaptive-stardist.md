# Testing StarDist as a tool Astra chooses

The previous experiment prescribed a default-first strategy and required independently resolved biological validity before accepting an estimated count. The new configuration removes that preference and evaluates the conditions under which a specialist output supports the user's requested estimate. It does not change model weights, profile thresholds or the 0.75 Jev acceptance threshold.

## File map

| File | Responsibility |
|---|---|
| `prompts/astra-adaptive.md` | Astra chooses and justifies a tool/profile/crop; no default profile preference. Requires measured derivation, declared uncertainty and honest domain assumptions. |
| `configs/capabilities-adaptive.toml` | The existing StarDist and crop tool interface without a preferred profile. |
| `prompts/jev_plan_conditions.json` | Jev scores whether concrete steps fit known conditions or can test an unresolved condition. |
| `prompts/jev_review_estimate.json` | Overall review at the precision actually requested: an estimate, not guaranteed ground truth. |
| `prompts/jev_conditions_checks.json` | Separate input suitability, parameter justification, coverage and count-grounding checks with actionable feedback. |
| `configs/poc-adaptive.toml` | Four-round bounded loop and unchanged 0.75 review threshold; 300-second API timeout shared by all arms. |
| `configs/bbbc039-adaptive.toml` | Independent vanilla/tools/select/full runs on the same six preselected images. |
| `evals/import_bbbc039.py` | Original-image import, fixed 16-bit display mapping, official mask-decoding semantics and verifier-only count labels. |
| `experiments/microscopy/harness_control.py` | Fixed default StarDist baseline using the exact adapter in the same specialist container, with no LLM or labels. |
| `evals/adaptive_report.py` | Report final answers, raw proposals, selected profiles, conditions, failures and paired differences from the fixed baseline. |

The StarDist adapter, runtime, model weights and three available threshold profiles are unchanged. This experiment tests a different orchestration policy, not a newly trained segmenter. The action space remains bounded: whole-image segmentation at default/sensitive/conservative thresholds, regional segmentation and crop inspection. There is no unrestricted code execution, arbitrary threshold search, image rescaling or automatic correction of detected objects.

## Roles and acceptance

Astra observes the image, proposes applicable methods and derives an answer from executed measurements. Jev scores the proposed conditions before selection, then checks actual inputs, parameters, coverage and derivation after execution. Failed checks return to both Astra planning and Jev selection. Python enforces tool schemas, valid inputs, coordinate bounds and loop budgets.

Jev receives structured evidence and explicitly supplied task metadata, not image pixels. It can assess consistency and suitability under those conditions; it cannot independently establish biological truth or inspect an overlay through a filename. Its scores are not calibrated probabilities of accuracy. The rubric requires rejection for unknown critical modality or missing spatial coverage; this is a model judgment that can itself be wrong, not a hard guarantee. Routine model uncertainty can be disclosed alongside a justified estimate instead of requiring every instance to be manually validated.

## Frozen comparison

Six filenames from the official BBBC039 test split are selected by a fixed hash ordering before downloading images or annotations. These images are new to this project's experiments. Public-model training exposure is unknown; BBBC039 has some overlap with BBBC038/DSB2018, so the split alone cannot establish that pretrained StarDist has never seen them.

All arms receive the same original field converted from 16-bit TIFF using fixed per-image 1/99.8 percentile clipping and rounding to 8-bit, with no spatial resizing. The segmentation adapter then applies its unchanged internal normalization. This is a declared display transformation, not lossless TIFF conversion. The task asks for estimated nuclei, including visible border nuclei, matching the annotation target. This is a derived counting task; the count-MAPE metric is not the official BBBC039 instance-segmentation benchmark score.

Compare fixed standalone StarDist, Astra + tools, Astra + tools + Jev selection, and the complete Jev review loop; fresh vanilla is contextual. Report accepted-output coverage and error first, then first/last numerical proposals separately. Record selected profiles, disagreement with the fixed baseline, per-image wins/losses, abstentions and execution failures. Do not select the best profile using ground truth or retry poor answers. Identical default counts remain a valid outcome.

Independent planning and unequal model-call budgets mean these arms compare whole policies rather than isolate a causal Jev effect. One small cohort is exploratory. A more permissive definition of a supported estimate must be evaluated for both improved coverage and incorrect approvals, not celebrated merely because more answers pass.

Sources: [BBBC039 dataset, split and CC0 license](https://bbbc.broadinstitute.org/BBBC039); [official annotation decoding example](https://gist.github.com/jccaicedo/15e811722fca51e3ae90e8b43057f075).

## Completed run

The [24-trial report](../reports/bbbc039-adaptive-20260922/index.html) is complete. Fixed default and Astra-only tools both score 9.72%; Jev selection chooses three sensitive counts and improves to 9.20%. Full review accepts 2/6, abstains on three and encounters one Astra structured-output limit failure. First/last numerical proposals score 9.20%/9.48%; they do not replace final-output scoring.

A separately labeled post-hoc calculation applies the same sensitive profile to every image using existing selection-arm measurements and scores 7.94%. Consequently, this run does not establish an advantage over a simpler fixed policy. The [findings](../reports/bbbc039-adaptive-20260922/findings.md) explain the changes, failures and limitations.

To regenerate the report without model calls:

```sh
.venv/bin/python -m evals.adaptive_report reports/bbbc039-adaptive-20260922 jobs/bbbc039-adaptive-20260922
.venv/bin/python reports/bbbc039-adaptive-20260922/audit.py
.venv/bin/harbor view jobs/bbbc039-adaptive-20260922
```

For another inference experiment, copy the evaluation config and select fresh empty task/job/report directories. Do not rerun into the frozen job directory. Build specialist tasks using `evals.build_tasks.build(dataset, tasks, split='test', specialist=True)`; the pinned checkpoint setup is documented in [StarDist setup](stardist-harness.md).
