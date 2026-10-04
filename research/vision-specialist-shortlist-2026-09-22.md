# Replacing the perception layer: researched shortlist

Research date: 22 September 2026. This is a research recommendation, not a new benchmark result. No specialist was installed or evaluated during this research pass.

## Decision

Evaluate Cellpose-SAM `cpsam_v2` and StarDist `2D_versatile_fluo` first, with InstanSeg as a third candidate. Keep OpenCV for image operations and measurements. Establish whether the specialists produce useful masks and counts before reconnecting Astra and Jev.

These are integration priorities based on task fit and deployment, not an accuracy ranking against Astra. I did not find a direct published comparison establishing that these checkpoints beat our configured `gpt-6-astra` on BBBC001.

## Why the current experiment did not test the central idea well

OpenCV is a library. Our adapter exposes a particular hand-written segmentation pipeline, not a trained cell-recognition model. In `src/vision_harness/tools/opencv.py`, `color_mask` explicitly assumes a white background when `color="any"`. With `saturation_min=0`, every pixel passes the saturation condition. `value_min` is unused in this branch. The resulting whole-image masks explain the observed failure; this does not establish that every classical vision method fails on microscopy.

The [latest local comparison](../reports/bbbc001-no-review-20260922/final-score.md) returned counts in all 18 trials, but all 12 tool-mode final answers used visual estimates after unusable segmentation. Its lower average error with selection is not proof of improved measured perception.

Our images are Hoechst-stained nuclei in HT29 cells. The [BBBC001 dataset](https://bbbc.broadinstitute.org/BBBC001) has six images and two human counts per image. Nucleus segmentation is the relevant target; staining does not reveal complete cell boundaries.

## Microscopy shortlist

| Priority | Candidate | Why it belongs | Output and practical limitation |
|---|---|---|---|
| First generalist | **Cellpose-SAM `cpsam_v2`** | Trained for cellular segmentation. Current documentation identifies this June 2026 checkpoint as an update addressing low-contrast regions. | Instance label image, from which code computes counts and measurements. Splits, merges and missed dim nuclei remain possible. |
| First focused comparison | **StarDist `2D_versatile_fluo`** | Explicitly pretrained for single-channel fluorescence nuclei. Its shape representation is a good candidate for compact nuclei. | Individual instance labels and object geometry. Unusual or non-star-convex shapes can be a limitation. |
| Third candidate | **InstanSeg** | Provides fluorescence cell/nucleus segmentation and channel-invariant processing. | Labeled instances; choose nucleus output for this task. Preserve pixel-size metadata and document scaling assumptions. |
| Later correction workflow | **micro-SAM with APG** | Microscopy-adapted SAM with automatic segmentation and interactive correction tools. APG means automatic prompt generation: code derives candidate prompts for the segmentation model. | Useful when the harness needs to inspect and correct particular regions. More moving parts than the first two baselines. |
| Additional comparison | **CellSAM** | A distinct project from Cellpose-SAM, with released inference code covering multiple microscopy modalities. | Candidate masks; should not be treated as equivalent to Cellpose-SAM because the names are similar. |

Sources: [Cellpose checkpoint documentation](https://cellpose.readthedocs.io/en/latest/models.html), [StarDist repository and pretrained models](https://github.com/stardist/stardist), [InstanSeg repository](https://github.com/instanseg/instanseg), [micro-SAM documentation](https://computational-cell-analytics.github.io/micro-sam/), [CellSAM repository](https://github.com/vanvalenlab/cellSAM).

Cellpose also now offers `cpdino` and the smaller `cpdino-vitb`, using DINOv3 backbones. They are additional candidates, not measured winners. Pin checkpoint names and hashes; installing the latest package is not enough to define an experiment. [Current model documentation](https://cellpose.readthedocs.io/en/latest/models.html).

## What comparative research actually supports

The MIDL 2026 paper *Revisiting foundation models for cell instance segmentation* evaluates multiple microscopy models and general SAM models. Cellpose-SAM and micro-SAM with APG are consistently among its strongest approaches. General SAM 3 is sensitive to text prompts and trails domain-specialized models in this evaluation. The authors also identify training-data coverage as an important influence. This supports trying specialists; it does not establish superiority over Astra or validate the newer June 2026 Cellpose checkpoints, which postdate the March paper. The study is from the micro-SAM researchers, rather than a neutral comparison with no method affiliation. [Paper and results](https://arxiv.org/html/2603.17845v1).

## Beyond microscopy

These are separate task-specific workers. None is a universal replacement for Astra's visual reasoning.

| Task | Candidate | Evidence returned to the harness |
|---|---|---|
| Text and document reading | **PaddleOCR / PP-OCRv6** | Recognized text, locations and component scores. Evaluate transcription and localization separately. [Official model documentation](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv6/PP-OCRv6.en.md). |
| Inventory and inspection | **RF-DETR** | Object boxes or instance masks and class scores. Custom categories may need training; pretrained natural-image categories do not become cell detectors automatically. [Official repository](https://github.com/roboflow/rf-detr). |
| Finding and masking named objects | **SAM 3 / 3.1** | Prompt-conditioned masks and object tracks. Its natural-image capabilities do not establish microscopy suitability. [Official repository](https://github.com/facebookresearch/sam3). |
| Depth and scene geometry | **Depth Anything 3** | Dense depth, camera parameters and confidence arrays. Preserve which checkpoint produces relative versus metric scale. [Official repository](https://github.com/ByteDance-Seed/Depth-Anything-3). |
| Motion across frames | **CoTracker3** | Point trajectories and visibility through video. Tracking points does not itself identify biological entities. [Official repository](https://github.com/facebookresearch/co-tracker). |

There is direct research support for the broader small-specialist premise: the PP-OCRv5 paper reports a 5-million-parameter system competitive with much larger VLMs on OCR, with stronger localization and reduced hallucinations. This is a publisher-reported result on its evaluated tasks, not an Astra comparison. [Paper](https://arxiv.org/abs/2603.24373).

Public availability does not imply identical licensing. SAM 3 uses a custom SAM License; CoTracker is predominantly noncommercial; DA3 licenses vary by checkpoint; RF-DETR licenses vary by variant. The linked repositories document these distinctions. Record exact code and weight terms when choosing a production worker.

## Running on this machine

Read-only hardware inspection found an Apple M5 Pro with 24 GB unified memory. That supports trying small 2D image workloads locally, but it is not a measured memory or latency guarantee.

- Cellpose documents PyTorch MPS acceleration on Apple Silicon. Start with one image per worker and measure peak memory. [Installation documentation](https://cellpose.readthedocs.io/en/latest/installation.html).
- StarDist supplies Apple Silicon wheels and TensorFlow installation guidance. Use its own environment so TensorFlow dependencies do not disturb the harness. [Repository](https://github.com/stardist/stardist).
- Treat SAM 3 as a separate deployment decision: the official setup specifies a CUDA-compatible GPU. Do not promise the documented pipeline runs on this Mac. [Prerequisites](https://github.com/facebookresearch/sam3#installation).

A persistent native worker can load one checkpoint and return artifact paths plus JSON to the CLI. Keep Harbor's task and verifier separation when connecting it; model workers receive only task inputs, never labels. Native workers, rather than assuming container GPU access, are the proposed route for an initial Apple Silicon experiment. A remote GPU service can later implement the same interface.

## What each worker should return

The adapter should compute and preserve: input hash, checkpoint hash, preprocessing, original coordinates, target type, instance labels, count of distinct non-background instance IDs, centroids, areas, border flags, numbered overlay, runtime and failure flags. Instance-label counting is reproducible arithmetic, not a guarantee every instance is a real nucleus.

Astra receives the original image, overlay, summary and access to detailed artifacts. It can request a crop or alternate segmentation. Any manual-looking correction must identify the affected instances and evidence; a new ungrounded number should not silently replace the measured count.

Retain native model scores under their own names. Jev's judgment score is separate from detector scores, segmentation quality and calibrated probability of correctness. If calibration has not been measured against held-out labels, call these scores or diagnostics, not statistical confidence in the final count.

## Next evaluation protocol

1. Run Cellpose-SAM and StarDist directly on the existing six images using frozen defaults. Save numbered overlays and count unique instance IDs in code. No Astra or Jev is needed for this stage.
2. Score the same mean absolute percentage counting error as earlier. Also inspect merged, split and missed nuclei; a correct total can conceal compensating errors.
3. Treat BBBC001 as an already-inspected development cohort. Select a larger real held-out benchmark with instance masks, checking overlap with checkpoint training data. Do not choose settings by optimizing these six labels and then call the result a fresh test.
4. Compare on one fixed cohort: vanilla Astra; specialist alone; Astra plus specialist; Astra plus specialist plus Jev selection. This isolates whether perception improves, whether Astra preserves the benefit, and whether selection adds anything.
5. Reintroduce Jev answer review as a separate condition. Report counting error, coverage, latency, cost and errors together. A reviewer that rejects everything must not appear to win because rejected cases disappear from its denominator.

The immediate recommendation is **Cellpose-SAM versus StarDist as standalone perception baselines**, followed by harness integration of the useful worker. OpenCV remains valuable for cropping, transformations, overlays and measurement.
