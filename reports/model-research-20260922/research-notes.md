## Recommendation

**Add StarDist and Cellpose-SAM as the first complementary baselines; add InstanSeg next; reserve μSAM for an annotation/correction workflow.** This is an integration priority—not a prediction of performance on your images.

For a **commercial deployment**, StarDist has the clearest licensing evidence in the sources reviewed. Cellpose-SAM requires particular care: its official weight repository advertises BSD-3-Clause, but upstream now flags noncommercial training-data licenses. InstanSeg and μSAM also need checkpoint-level license verification rather than relying on their software licenses. ([github.com](https://github.com/stardist/stardist-models))

**Version check, September 22, 2026:** Cellpose’s current documentation distinguishes **`cpsam_v2`**, released June 2026, from the original **`cpsam`**, released April 2025. Do not silently substitute one for the other in a reproducibility manifest. ([github.com](https://github.com/MouseLand/cellpose/blob/main/docs/models.rst?utm_source=openai))

I shortlisted **four model families** below. I used author/project repositories, official weight registries, and primary papers; unverified details are explicitly marked. Nothing was installed or evaluated in your harness.

## 1. StarDist — first addition for a nuclei-only baseline

### Checkpoint and input

- **Recommended checkpoint:** `StarDist2D.from_pretrained("2D_versatile_fluo")`.
- **Exact registered artifact:** `stardist/stardist-models`, release `v0.1`, file **`python_2D_versatile_fluo.zip`**. The official loader also records an artifact checksum.
- **Input:** a **single-channel 2D fluorescence image containing a nuclear marker**. The official example normalizes the image before `predict_instances`.
- The separately registered **`2D_paper_dsb2018`** is the paper-associated model, not an interchangeable name for the versatile checkpoint. Both were trained on subsets of DSB2018. ([github.com](https://github.com/stardist/stardist?utm_source=openai))

### Capability and crowded-image limitations

StarDist predicts object probabilities and radial distances defining **star-convex polygons**, followed by nonmaximum suppression. It produces instance labels and polygon geometry, making it a direct fit for nuclei segmentation and subsequent counting. Its important limitation is the shape representation: deeply concave, branched, or otherwise non-star-convex objects are not represented faithfully. The maintainers recommend checking how well annotated objects can be reconstructed by that representation. ([github.com](https://github.com/stardist/stardist?utm_source=openai))

**My assessment:** a strong first baseline when the target is approximately blob-shaped nuclei. Explicitly inspect suppressed detections in crowded groups and errors on lobulated nuclei; do not assume that a plausible polygon means a correct instance.

### License, hardware, evidence

- **License:** both the software and the dedicated pretrained-weight repository identify **BSD-3-Clause**—permissive commercial use subject to its conditions. This is stronger evidence than a software-only license badge. ([github.com](https://github.com/stardist/stardist?utm_source=openai))
- **Documented execution:** TensorFlow; NVIDIA GPU support through compatible CUDA/cuDNN, plus documented Apple Silicon/TensorFlow acceleration. **I did not verify a checkpoint-specific minimum VRAM requirement or inference throughput figure.** ([github.com](https://github.com/stardist/stardist))
- **Published evidence:** the author repository identifies the original **MICCAI 2018, “Cell Detection with Star-convex Polygons”** paper and its paper-associated checkpoint. Keep that method evidence separate from evidence for the exact `2D_versatile_fluo` artifact; I did not verify a numerical benchmark specifically attributable to that artifact. ([github.com](https://github.com/stardist/stardist?utm_source=openai))

**Harness priority: 1.** A straightforward nuclei-specific reference with relatively clear weight licensing.

## 2. Cellpose-SAM — first complementary model, explicitly versioned

### Checkpoints and input

- **Current candidate:** official Hugging Face repository **`mouseland/cellpose-sam`**, checkpoint file **`cpsam_v2`**.
- **Paper-era reproducibility candidate:** same repository, file **`cpsam`**.
- Ownership is supported by the **MouseLand implementation directly using that repository as its weight-download location**, not merely by its Hugging Face organization name. ([github.com](https://github.com/MouseLand/cellpose/blob/main/cellpose/models.py?utm_source=openai))

Both use a **SAM ViT-L backbone**. The official documentation specifies fixed **256 × 256 inference tiles** and training object diameters spanning **7.5–120 pixels**, with mean 30 pixels. These are training-scale facts, not a guarantee that every object within that range will segment correctly. Larger objects may require rescaling and adjusted dynamics iterations. ([github.com](https://github.com/MouseLand/cellpose/blob/main/docs/models.rst?utm_source=openai))

Upstream describes the model as supporting cell and nuclear segmentation, channel-order variation, and substantial image degradation. **For this task, my initial adapter would expose only the nuclear image channel**, then evaluate additional channels separately so that whole-cell versus nucleus targeting does not become an uncontrolled variable. ([github.com](https://github.com/MouseLand/cellpose?utm_source=openai))

### License, hardware, evidence

- **Software:** BSD-3-Clause.
- **Weights:** official Hugging Face metadata also says BSD-3-Clause, but its model-card body is empty.
- **Important qualification:** the current upstream README states that all Cellpose models were trained on **CC-BY-NC data**. These statements do not establish that the data license automatically transfers to learned weights—but neither should a commercial deployment ignore the discrepancy. **My recommendation is a commercial-release hold pending clarification from the rights holder**, not a categorical assertion that the weights are noncommercial. ([github.com](https://github.com/MouseLand/cellpose/blob/main/LICENSE?utm_source=openai))
- **Documented execution:** the implementation supports **CPU, CUDA, and Apple MPS** devices. I did not verify a minimum inference VRAM requirement; checkpoint file size is not an adequate substitute. ([github.com](https://github.com/MouseLand/cellpose/blob/main/cellpose/models.py?utm_source=openai))
- **Evidence:** upstream cites the 2025 Cellpose-SAM preprint. It describes `cpsam_v2` as fixing training behavior in low-contrast regions and reducing spurious masks; **that release statement is not a quantified benchmark for v2**. I could not verify the original preprint’s numerical tables from the permitted sources reviewed. ([github.com](https://github.com/MouseLand/cellpose?utm_source=openai))

**Harness priority: 2.** Useful architectural complement to StarDist. Pin `cpsam_v2` explicitly; retain original `cpsam` only if paper-era comparison is important.

## 3. InstanSeg — next alternative, especially for a portable inference module

### Checkpoint and input

A verified versioned starting point is:

- **Model:** `fluorescence_nuclei_and_cells`
- **Official model release:** **`v0.1.0`**
- **Capability:** channel-invariant segmentation of nuclei and cells in multiplexed fluorescence images.

This is a reproducible release reference, **not a claim that v0.1.0 is newest**. The official release history also lists **`single_channel_nuclei`**, specifically intended for a single fluorescence nuclear channel; I did not establish its exact release/artifact version and therefore would not yet put it into a locked manifest. ([github.com](https://github.com/instanseg/instanseg/releases?utm_source=openai))

InstanSeg’s inference workflow requires **pixel size**, read from image metadata or supplied explicitly when unavailable. That makes calibration a meaningful adapter requirement rather than optional bookkeeping. The project supports compiling the model **and postprocessing into TorchScript**, allowing deployment through LibTorch. ([github.com](https://github.com/instanseg/instanseg?utm_source=openai))

### License, hardware, evidence

- **Software:** Apache-2.0.
- **Weights:** the official release notes explicitly direct users to each model archive’s README for its license and training datasets. **I did not verify the archive-specific grant for the selected checkpoint**, so I would not yet label it commercially cleared. ([github.com](https://github.com/instanseg/instanseg?utm_source=openai))
- **Documented execution:** PyTorch/TorchScript/LibTorch deployment is documented. **A specific inference GPU, minimum VRAM, or comparable throughput result was not verified.** The repository’s CUDA/MPS epoch timings concern training and should not be reported as inference measurements. ([github.com](https://github.com/instanseg/instanseg?utm_source=openai))
- **Evidence:** the authors distinguish their **embedding-based InstanSeg paper** from the **channel-invariant fluorescence paper**. The latter is the relevant method evidence for this checkpoint; brightfield results alone would not establish fluorescence-nucleus performance. ([github.com](https://github.com/instanseg/instanseg?utm_source=openai))

**My assessment:** worthwhile as a third, structurally different approach. Before integration, resolve the single-channel model’s artifact and license; otherwise use the explicitly versioned fluorescence model and retain **only its nuclear output** for this task.

**Harness priority: 3, conditional on artifact/license verification.**

## 4. μSAM / micro-sam — most useful when correction and annotation matter

### Checkpoint and operating mode

- **Candidate identifier:** **`vit_b_lm`**, the light-microscopy model used in the authors’ own segmentation/correction study.
- **Reproducibility gap:** I verified the identifier, but not an immutable weight revision/hash or the exact matching automatic-instance-segmentation decoder artifact. Those should be resolved before deployment. ([github.com](https://github.com/computational-cell-analytics/user-study-v3?utm_source=openai))

μSAM supports interactive segmentation and automatic segmentation. For a counting harness, distinguish:

1. **AMG:** automatic masks generated from a grid of prompts.
2. **AIS:** a learned additional decoder predicting foreground and object-center/boundary distances, followed by instance postprocessing.

A checkpoint capable of interactive prompting is therefore **not, by itself, proof that the intended AIS pipeline is fully specified**. ([nature.com](https://www.nature.com/articles/s41592-024-02580-4.pdf?utm_source=openai))

### License, hardware, evidence

- **License:** I did not verify a checkpoint-specific commercial-use grant for this proposed artifact. Treat that as unresolved rather than inheriting permission from the surrounding software.
- **Hardware:** I did not verify a specific inference device/minimum VRAM for `vit_b_lm` plus its AIS decoder.
- **Published evidence:** the **2025 Nature Methods paper** reports that fine-tuning improves microscopy segmentation. On **LIVECell**, specialist-model AIS was on par with the compared Cellpose model, while interactive correction improved further. Its LM generalist training includes **Nucleus DSB**, so that dataset cannot simply be presented as unseen evidence for the generalist. Those results also do **not** establish that `vit_b_lm` is the best automatic model for crowded fluorescence nuclei. ([nature.com](https://www.nature.com/articles/s41592-024-02580-4.pdf?utm_source=openai))

**Harness priority: 4.** Move it higher if your modular harness includes human correction, prompt caching, or training-set creation; otherwise the first three are more direct automatic-segmentation candidates.

## What the published comparisons actually establish

A useful primary **2026 FUCCI study** compared custom-trained StarDist, InstanSeg, and fine-tuned Cellpose-SAM. InstanSeg achieved approximately similar accuracy to StarDist; Cellpose-SAM was slightly worse in that experiment. The authors reported Cellpose-SAM inference approximately **5× slower than StarDist and 10× slower than InstanSeg**. **These are study-specific, trained-model results—not timings or accuracy for the stock checkpoints above, and not forecasts for your dataset.** ([nature.com](https://www.nature.com/articles/s44303-026-00159-6?utm_source=openai))

I would not construct a numerical leaderboard from these sources: they mix different checkpoints, training regimes, modalities, and interactive versus automatic evaluation.

## Proposed harness additions

This is the integration/evaluation plan I recommend:

| Order | Adapter | Initial gate |
|---|---|---|
| 1 | StarDist `2D_versatile_fluo` | Pin registered archive/checksum; explicit normalization and nuclear channel |
| 2 | Cellpose-SAM `cpsam_v2` | Pin weight revision/hash; explicit preprocessing; commercial clarification |
| 3 | InstanSeg | Resolve single-channel checkpoint or pin fluorescence release; verify weight license and pixel size |
| 4 | μSAM `vit_b_lm` + AIS | Pin both model and decoder; verify licensing; separate automatic from prompted evaluation |

For each adapter, I would require:

- **Output contract:** original-resolution integer instance labels, background `0`, optional scores, and recorded preprocessing/rescaling.
- **Counting contract:** count unique nonzero instance IDs **after** tile reconciliation and the agreed edge-object policy—not `labels.max()` or a foreground-pixel count.
- **Provenance:** software commit/version, weight hash, license snapshot, thresholds, pixel size, channel selection, and tile settings.
- **Evaluation:** held-out annotated fields stratified by crowding and signal quality; instance precision/recall and matched-mask quality, **split/merge errors**, count MAE/bias, tile-boundary errors, latency, and peak memory.
- **No silent tuning on test data:** calibrate thresholds and scale on validation images, then lock them.

**Bottom line:** start with **StarDist + explicitly pinned Cellpose-SAM v2**, then investigate **InstanSeg’s single-channel nuclear checkpoint** as the next addition. Keep **μSAM** for the branch where interactive correction offers additional value. None of these recommendations constitutes validation on your dataset.
