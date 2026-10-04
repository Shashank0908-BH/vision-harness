# StarDist in the complete harness

The specialist configuration replaces color-component and watershed segmentation with a pinned pretrained StarDist model. OpenCV remains an implementation utility for reading/cropping images and drawing overlays. The previous configurations retain their previous tool lists.

| File | Responsibility |
|---|---|
| `src/vision_harness/tools/stardist.py` | Validates fluorescence inputs and profiles, verifies the checkpoint, lazily loads the model, and returns mask-derived counts and traceable artifacts. |
| `src/vision_harness/tools/dispatch.py` | Routes tools while keeping TensorFlow imports out of OpenCV-only execution. |
| `src/vision_harness/contracts.py` | Adds the `stardist` operation and nullable `segmentation_profile`. |
| `configs/capabilities-stardist.toml` | Exposes StarDist and crop inspection with their requirements and limitations. |
| `prompts/astra-stardist.md` | Describes measured-count derivation, correlated threshold comparisons and crop coverage. Contains no benchmark labels or previous scores. |
| `configs/poc-stardist.toml` | Full structured review loop, with the same four-round/24-call/600-second limits and 0.75 review threshold as the earlier loop configuration. |
| `requirements-stardist.in`, `requirements-stardist.txt` | Direct requirements and hashed Linux ARM64 Python 3.12 dependency resolution for the specialist container. The original runtime lock remains unchanged. |
| `evals/build_tasks.py` | Optional `specialist=True` bundles only the three checkpoint files and installs the specialist dependencies; reference labels remain verifier-only. |
| `configs/bbbc001-stardist.toml` | Fresh six-image vanilla/tools/full comparison in Harbor, one attempt per mode, concurrency two. |
| `tests/test_stardist.py` | Argument rejection, operation identity, non-contiguous instance counting, profile thresholds, crop provenance and invalid-input checks. |

## Flow

Astra proposes methods → Jev scores eligible plans → selected StarDist/crop operations execute → Astra derives an answer from the evidence → Jev reviews overall support and four evidence checks. Rejected candidates and failed checks return to planning and selection until acceptance or an existing loop stopping condition.

The three profiles share one checkpoint: default uses its pretrained probability threshold; sensitive uses 0.35; conservative uses 0.60. All use overlap threshold 0.3 and normalization percentiles 1/99.8. Alternative profiles measure sensitivity, not independent model agreement. They were fixed before the harness run, not optimized against reference counts.

Evidence includes count, target, foreground fraction, border count, size/score summaries, exact parameters, checkpoint hash, coordinate origin, label-map hash and raw artifact paths. Full instance geometry stays in trace files; it is not expanded into every LLM request. Astra receives actual original/overlay/crop images. Jev receives structured evidence, not image pixels; an artifact path does not let Jev inspect that image. Its review can still abstain.

## Setup and execution

The already installed standalone StarDist environment can prepare the local checkpoint:

```sh
.venv-stardist/bin/python - <<'PY'
from pathlib import Path
from shutil import copy2
from csbdeep.models.pretrained import get_model_folder
from stardist.models import StarDist2D
source = get_model_folder(StarDist2D, '2D_versatile_fluo')
target = Path('models/stardist')
target.mkdir(parents=True, exist_ok=True)
for name in ('config.json', 'thresholds.json', 'weights_best.h5'):
    copy2(source / name, target / name)
PY
```

The adapter verifies these exact files against pinned hashes. They are excluded from Git and copied into each specialist task image; no runtime checkpoint download is needed. Linux ARM64 builds compile the StarDist extension, so the specialist Dockerfile installs compiler/OpenMP dependencies.

Build a new empty task directory using `evals.build_tasks.build(dataset, tasks, split='test', specialist=True)`, set that directory in a separate evaluation config, and run `.venv/bin/vision eval --config CONFIG`. Reusing existing output directories is forbidden. The current experiment uses `configs/bbbc001-stardist.toml`.

## Interpretation

Report accepted final answers separately from all first/last numerical candidates and failures. A full-dataset error requires all six valid final counts. The standalone default StarDist count remains a separate baseline; improvements in review coverage or methodology scores are not improvements in counting accuracy. These six images are development data already inspected, not a new held-out test.

## Completed experiment

The [18-trial report](../reports/bbbc001-stardist-20260922/index.html) records Astra + StarDist at 6/6 counts and 6.67% mean error, identical to standalone StarDist. Full mode produced the same first/last numerical proposals, then abstained on all six. Overall Jev support was 0.80–0.87, but method validity (0.19–0.32) and target validity (0.33–0.46) failed the unchanged 0.75 per-check threshold. All six replanning loops delivered failed checks to both Astra and Jev; no full-mode execution failed.

Primary vanilla had five counts and one 120-second API timeout. A separately preserved 300-second retry returned the missing count, producing a recovered/composite vanilla error of 18.20%. StarDist is closer on all six images in that comparison. The [final score](../reports/bbbc001-stardist-20260922/final-score.md) keeps primary coverage, recovery and candidate diagnostics separate.

The current policy cannot distinguish a useful estimated count from an independently validated biological count at acceptance time. This run supports the specialist's measured-count benefit on this cohort; it does not show that the full chain beats the specialist or that Jev's review scores are calibrated.
