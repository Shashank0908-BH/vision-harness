# Specialist models for an LLM harness: a practical business-use-case landscape

Research date: 18 September 2026. Prepared from official repositories, model cards, and project documentation. No models were installed or benchmarked for this report.

This is a representative, actionable landscape of **50 model/family entries across 10 categories**, not an enumeration of every publicly released model. It includes pretrained models, model families, and several clearly identified training/analysis libraries. OpenCV and MediaPipe are additional supporting tools, not included in that count. “Publicly available” includes permissive releases, copyleft releases, custom-license weights, and noncommercial research releases; these are not interchangeable meanings of “open source.”

## How to read the rankings

Rankings are my engineering judgment about integration priority within the stated business use case, combining task fit, useful output structure, deployment burden, and licensing clarity. They are not benchmark rankings, claims of universal accuracy, or measured ROI. A model ranked first for segmentation is not thereby better at object identification or diagnosis. Where tasks differ, the table gives a task-specific first choice rather than implying a direct competition.

Evidence is primarily **release evidence**: the publisher provides code/checkpoints, documented interfaces, and frequently a paper or evaluation. That establishes an implementable candidate, not independent proof it improves a current LLM. Repository benchmark claims are not adopted as comparative facts here. The precise checkpoint, domain, preprocessing, and deployment configuration must be evaluated.

License statements record what the linked publisher says as of this research date. “Code Apache; weights unverified” deliberately does not infer a weight license from the repository license. Custom terms and model-card inconsistencies are flagged. A permissive software license does not validate the intended scientific or operational use.

## Where the first business value is most plausible

| Priority for a general-purpose harness | Business use case | Why add a specialist? | First candidates to evaluate |
|---|---|---|---|
| 1 | Document operations: invoices, forms, manuals, reports | Recover text, layout and tables with traceable page locations | PaddleOCR; Granite Docling; retrieval/reranking |
| 2 | Enterprise search and evidence-backed answers | Improve which evidence reaches the coordinator | BGE-M3 or Qwen3 embeddings; a reranker; ColQwen for visual pages |
| 3 | Inspection, inventory, asset measurement | Produce object instances and geometry, then calculate reproducibly | RF-DETR; Grounding DINO; SAM 2; OpenCV |
| 4 | Contact centers, meetings, accessibility | Transcribe, separate speakers and synthesize speech | Whisper or Parakeet; pyannote; Kokoro |
| 5 | Demand planning and business analytics | Produce forecasts and calibrated task-specific predictions | XGBoost; Chronos/NeuralForecast; fitted anomaly models |
| 6 | Domain products: geospatial, imaging, life sciences | Specialized representations expose capabilities general vision lacks | Prithvi; Cellpose; TotalSegmentator; Boltz |
| 7 | Video geometry and physical action | Persistent motion, 3D structure, action policies | SAM 2/CoTracker; VGGT; Octo/OpenVLA |
| Separate capability | Content production and structured text extraction | Create requested assets or extract defined entities | FLUX.1-schnell; GLiNER |

This ordering assumes a small team building reusable infrastructure. A microscopy startup should put its microscopy task first. The catalog is not a recommendation to load every model into the initial harness.

## 1. Documents, OCR, tables and charts

| Rank / family | Best business fit and harness output | Code / weights and integration considerations |
|---|---|---|
| 1 — **PaddleOCR: PP-OCRv6, PP-StructureV3, PaddleOCR-VL-1.6** | Scene text, invoice/document ingestion, tables and page structure. Return recognized text with polygons, reading order, table structure, source page and rendered crops. Use the coordinate-rich conventional pipeline when geometry matters. | Repository Apache-2.0; checked PP-OCRv6 detector and VL-1.6 cards also Apache-2.0. Conventional OCR has CPU/accelerator deployment options; the VL path is a different workload. Verify each selected component. [Repository](https://github.com/PaddlePaddle/PaddleOCR), [detector card](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_det), [VL card](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6). |
| 2 — **Granite Docling 258M** | Compact structured document conversion integrated with Docling. Return document elements, structured tables, equations and links to page regions. Attractive when local footprint matters. | Model card Apache-2.0. The card documents page-level and bounding-box-guided conversion. Profile page resolution and decoding length rather than inferring speed from parameter count alone. [Official model card](https://huggingface.co/ibm-granite/granite-docling-258M). |
| 3 — **olmOCR 2** | Bulk PDF ingestion, reading-order recovery, equations, tables and difficult scans. Return extracted content plus source-page references and conversion flags. | Code and selected weights Apache-2.0; model card additionally describes research/educational intended use and responsible-use guidelines. GPU-oriented pipeline. The repository documents hardware requirements; these are configuration-specific, not universal memory guarantees. [Code](https://github.com/allenai/olmocr), [weights](https://huggingface.co/allenai/olmOCR-2-7B-1025). |
| 4 — **DeepSeek-OCR-2** | Alternative document transcription/parser to compare against the above on the same forms and scans. Preserve parsed regions and original page alongside generated content. | Selected weights Apache-2.0. Review the official implementation and pin custom code; do not assume generic model-hosting UI snippets demonstrate a tested deployment. [Official model card](https://huggingface.co/deepseek-ai/DeepSeek-OCR-2). |

Selection rule: compare exact field accuracy, table-cell accuracy, reading order, missing content and invented content. A readable Markdown page can still contain the wrong invoice total. Preserve the original page and exact source regions.

## 2. Object detection, segmentation, counting and industrial inspection

The ranks below apply to distinct jobs. Counting follows validated instance detection/segmentation; it is not automatically reliable because the final count is computed in Python.

| Task priority / family | Best business fit and harness output | Code / weights and integration considerations |
|---|---|---|
| First for custom fixed categories — **RF-DETR** | Product/asset detection, retail inventory, industrial inspection. Fine-tune to actual categories; return boxes, masks, class IDs and scores. | Open `rfdetr` code and Apache-designated checkpoints Apache-2.0. RF-DETR-XL/2XL **detection** and Plus components use PML 1.0; do not extend the Apache label to them. [Official repository and license table](https://github.com/roboflow/rf-detr). |
| First for finding objects from text — **Grounding DINO** | Open-vocabulary discovery and annotation assistance. Return boxes, matched phrases, scores and original-image coordinates. | Original repository and checked `grounding-dino-base` checkpoint Apache-2.0. This does not establish the license or availability of every later branded release. [Code](https://github.com/IDEA-Research/GroundingDINO), [checkpoint](https://huggingface.co/IDEA-Research/grounding-dino-base). |
| First for promptable masks — **SAM 2 / 2.1** | Interactive annotation, object extent, video mask propagation. Return masks, object IDs, frame times and prompts used. | Publisher explicitly licenses model checkpoints, training and demo code under Apache-2.0; some bundled components have separate notices. Prompting does not itself establish a semantic class or validate boundaries. [Official repository](https://github.com/facebookresearch/sam2). |
| Next candidate for concept segmentation — **SAM 3** | Segment matching concepts in images/video with text or visual prompts. Useful alternative to a multi-model grounding-plus-masking pipeline. | Code and weights under the custom SAM License, not Apache. Includes use restrictions; evaluate exact terms before product selection. [Code](https://github.com/facebookresearch/sam3), [license](https://github.com/facebookresearch/sam3/blob/main/LICENSE). |
| Alternative with broad deployment ecosystem — **Ultralytics YOLO family** | Detection, instance segmentation, pose and tracking; good candidate where deployment/export ecosystem dominates. Return instance records and track histories. | AGPL-3.0 or a separate enterprise license. Copyleft is not the same as noncommercial, and proprietary integration should not be treated as automatically unrestricted. Pin the chosen release and checkpoint. [Official repository/licensing](https://github.com/ultralytics/ultralytics). |
| First for “different from normal” defects — **PatchCore / PaDiM / related methods in Anomalib** | Manufacturing inspection with normal/reference images. Return anomaly map, image score, threshold, reference/training-set ID and localization. | Anomalib is an Apache-2.0 **library**, not one universally pretrained defect detector. Backbone checkpoints and datasets have their own terms. A site/product-specific fit and threshold calibration are required. [Official repository](https://github.com/open-edge-platform/anomalib). |

Supporting component: **OpenCV** is an Apache-2.0 computer-vision library rather than a replacement general vision model. Use it for calibrated geometric measurement, transformations, contours and deterministic postprocessing. Return numerical values, units, transforms and intermediate images. [Official repository](https://github.com/opencv/opencv).

## 3. Motion, depth, 3D geometry and visual representations

| Task priority / family | Best business fit and harness output | Code / weights and integration considerations |
|---|---|---|
| First low-complexity depth experiment — **Depth Anything V2 Small** | Relative scene depth, foreground/background separation and inspection views. Return depth array plus explicit scale semantics. | Small weights Apache-2.0; Base/Large/Giant weights CC-BY-NC-4.0. Relative depth must not be labeled meters. Metric variants have specific training domains and calibration assumptions. [Official repository](https://github.com/DepthAnything/Depth-Anything-V2). |
| First multiview reconstruction candidate — **VGGT** | Site capture, digital asset reconstruction, multiview geometry. Return camera intrinsics/extrinsics, depth/point maps and tracks. | Code uses custom terms; original checkpoint remains noncommercial. Separate `VGGT-1B-Commercial` weights permit commercial uses subject to restrictions and gated access. Larger view sets increase memory needs. [Official repository](https://github.com/facebookresearch/vggt). |
| First point-tracking research candidate — **CoTracker3** | Track selected points across video for motion studies, inspection and editing. Return trajectories, timestamps and visibility estimates. | Majority CC-BY-NC; bundled portions have other licenses. Research candidate rather than a default unrestricted commercial dependency. Online/offline modes have different working sets. [Official repository](https://github.com/facebookresearch/co-tracker). |
| Dense motion baseline — **RAFT** | Pixel displacement, registration assistance and motion analysis. Return two-dimensional flow fields and consistency checks; flow is not semantic object identity. | Code BSD-3-Clause; downloadable checkpoints provided, but no separate explicit checkpoint grant was confirmed in this scan. Older original dependencies need a maintained deployment path. [Official repository](https://github.com/princeton-vl/RAFT). |
| First visual feature backbone — **DINOv2** | Visual similarity, grouping, downstream defect/classification heads. Return embeddings/patch features with model version and nearest supporting exemplars. | DINOv2 code and weights Apache-2.0. Other models now present in that repository, including XRay-DINO/Cell-DINO, have different noncommercial terms. Features alone do not supply an application-specific decision rule. [Official repository](https://github.com/facebookresearch/dinov2). |
| First image–text similarity candidate — **SigLIP 2** | Product-image search, content organization, candidate-label scoring. Return embeddings and scored candidate IDs with associated images. | Checked Google checkpoint Apache-2.0. Similarity scores are not automatically calibrated probabilities, and the model is not a precise measuring tool. [Official model card](https://huggingface.co/google/siglip2-base-patch16-224). |

For a live pose or gesture product, also inspect MediaPipe's model packages and device runtime. It is a deployment/toolkit family rather than one model; confirm the selected bundle's terms instead of relying only on its Apache-licensed code. [Official MediaPipe repository](https://github.com/google-ai-edge/mediapipe).

## 4. Audio: transcription, speakers, speech generation and separation

| Task priority / family | Business fit and harness output | Code / weights and integration considerations |
|---|---|---|
| First multilingual ASR candidate — **Qwen3-ASR** | Customer support, meetings, subtitles. Return text and detected language; use its separate forced aligner when timestamps are needed. | Code and weights Apache-2.0. Documented streaming mode does not support timestamps or batching; alignment has its own language coverage. [Code](https://github.com/QwenLM/Qwen3-ASR), [1.7B weights](https://huggingface.co/Qwen/Qwen3-ASR-1.7B). |
| First candidate for supported European languages — **Parakeet-TDT-0.6B-v3** | High-throughput transcription/captioning. Return text and character/word/segment timestamps. | Weights CC-BY-4.0; runtime terms recorded separately. Covers 25 European languages, not every language. Test accents and domain vocabulary. [Official model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3). |
| Compatibility baseline — **Whisper** | Broad multilingual transcription, speech translation and archive processing. Return text, language and timestamped segments. | Publisher explicitly licenses code and weights MIT. Multiple sizes; assess noisy/silent inputs and vocabulary. Does not identify speakers. [Official repository](https://github.com/openai/whisper). |
| First diarization candidate — **pyannote community-1** | Meeting/contact-center “who spoke when?” Return time intervals and anonymous speaker IDs, combined with aligned ASR. | Model/pipeline CC-BY-4.0; pyannote.audio code MIT. Gated download, then offline use supported. Speaker clusters are not established real-world identities. [Model card](https://huggingface.co/pyannote/speaker-diarization-community-1), [code](https://github.com/pyannote/pyannote-audio). |
| First speech-presence front end — **Silero VAD** | Voice endpointing, silence skipping, telephony. Return speech intervals/probabilities. | MIT project/model release. CPU/edge-friendly PyTorch/ONNX options; supports 8 kHz and 16 kHz. Tune thresholds to avoid clipping speech. [Official repository](https://github.com/snakers4/silero-vad). |
| First compact TTS baseline — **Kokoro-82M** | Accessibility and product narration. Return waveform, sample rate and associated text chunks. | Weights and code Apache-2.0. Language/voice and phonemization support vary; test names and numbers. [Weights](https://huggingface.co/hexgrad/Kokoro-82M), [code](https://github.com/hexgrad/kokoro). |
| First controllable multilingual TTS candidate — **Qwen3-TTS** | Localization, expressive educational content and voice interfaces. Return waveform/sample rate, retaining generation settings. | Code and weights Apache-2.0. CustomVoice, VoiceDesign and Base checkpoints serve different functions; choose explicitly. [Code](https://github.com/QwenLM/Qwen3-TTS), [CustomVoice card](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice). |
| TTS alternative — **Chatterbox Turbo / family** | Conversational English speech and expressive narration. Return audio and voice-conditioning provenance. | Turbo weights/code MIT. Turbo is English; multilingual variants are separate. Project includes watermarking. Profile actual conversational latency. [Code](https://github.com/resemble-ai/chatterbox), [Turbo weights](https://huggingface.co/ResembleAI/chatterbox-turbo). |
| Music separation baseline — **Demucs / HTDemucs** | Media asset preparation and vocals/instrument isolation. Return separate waveform stems. | Repository MIT; separate per-checkpoint terms not independently confirmed here. Official repo says no longer actively maintained and points to an author fork. Not a general overlapping-speaker solution. [Official repository](https://github.com/facebookresearch/demucs). |

ASR, diarization, voice activity detection and speech synthesis are complementary jobs. For a lean voice prototype, start with VAD → one ASR → coordinator → one TTS; add diarization only when multiple speakers matter.

## 5. Search, embeddings, multilingual retrieval and reranking

| Task priority / family | Business fit and harness output | Code / weights and integration considerations |
|---|---|---|
| First dense text-retrieval candidate — **Qwen3-Embedding** | Enterprise/document/code search and clustering. The worker stores vectors; return selected source IDs, relevance scores and evidence excerpts to the coordinator. | Checked weights Apache-2.0. Official example repository license declaration was not established in this scan. Different dimensions/models require compatible indexing; do not silently mix them. [0.6B weights](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B), [official examples](https://github.com/QwenLM/Qwen3-Embedding). |
| First second-stage text reranker — **Qwen3-Reranker** | Reorder retrieved evidence for support answers and research. Return query-document scores and IDs. | Checked weights Apache-2.0; same example-code caveat. Rerank a shortlist to control cost. Relevance is not factual correctness. [0.6B card](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B). |
| First hybrid-retrieval alternative — **BGE-M3** | Multilingual semantic plus lexical search. Return dense vectors, sparse weights and/or multi-vectors to the retrieval service. | Weights and FlagEmbedding code MIT. Its hybrid advantages depend on actually using those representations. [Weights](https://huggingface.co/BAAI/bge-m3), [code](https://github.com/FlagOpen/FlagEmbedding). |
| First mixed-media retrieval candidate — **Qwen3-VL-Embedding / Reranker** | Images, video, screenshots and mixed asset collections. Return ranked artifact IDs and selected visual evidence. | Both cited checkpoints and official code Apache-2.0. Resolution and video-frame selection control cost and information retained. [Embedding](https://huggingface.co/Qwen/Qwen3-VL-Embedding-2B), [reranker](https://huggingface.co/Qwen/Qwen3-VL-Reranker-2B), [code](https://github.com/QwenLM/Qwen3-VL-Embedding). |
| First visual-PDF retrieval comparison — **ColQwen2-v1.0 / ColPali approach** | Search reports, slides and charts whose meaning is lost in text extraction. Return page/query multi-vectors internally and ranked page images externally. | This checkpoint: Apache-2.0 backbone + MIT adapters; ColPali code MIT. Official code now recommends Sentence Transformers over deprecated colpali-engine. Other family versions have different base-model terms. [Selected checkpoint](https://huggingface.co/vidore/colqwen2-v1.0), [code](https://github.com/illuin-tech/colpali). |

Specific license ambiguity: [ColQwen2.5-v0.2](https://huggingface.co/vidore/colqwen2.5-v0.2) displays MIT metadata but its license section describes a Qwen Research License backbone and MIT adapters. Do not transfer v1.0's licensing conclusion to that checkpoint.

Retrieval is a way to select observations, not an alternative to all visual understanding. A useful system retrieves a relevant chart image, then invokes parsing or measurement when the question requires exact values.

## 6. Tabular data, forecasting, anomalies and recommendations

| Task priority / family | Business fit and harness output | Code / weights and integration considerations |
|---|---|---|
| First trained tabular baseline — **XGBoost** | Churn, operational prediction, classification and regression. Return predictions, appropriate uncertainty/calibration results and feature contributions. | Apache-2.0 **training library**, not a universally pretrained predictor. Fit on business data; CPU/GPU implementations. [Official repository](https://github.com/dmlc/xgboost). |
| Pretrained tabular comparison — **TabPFN** | Rapid classification/regression baselines on compatible tabular datasets. Return predictions and class probabilities. | Current code Apache-2.0. Latest weight families use noncommercial terms; TabPFN-2 has an Apache-derived Prior Labs License with additional attribution. Pin exact version and terms. [Official repository](https://github.com/PriorLabs/TabPFN). |
| First pretrained forecasting candidate — **Chronos-2 / Chronos-Bolt** | Inventory, staffing, load and demand forecasts. Return timestamped forecasts and quantiles; include covariates used. | Code and checked Chronos-2 weights Apache-2.0. Compare against seasonal/statistical baselines and actual planning loss; pretrained is not universally better. [Code](https://github.com/amazon-science/chronos-forecasting), [weights](https://huggingface.co/amazon/chronos-2). |
| First task-trained forecasting comparison — **NeuralForecast: N-HiTS, PatchTST, TFT** | Forecasting when domain training and exogenous variables matter. Return distributions/quantiles where supported and forecast-origin metadata. | Apache-2.0 library; these models generally require fitting. Distinct from the separately offered TimeGPT API. [Official repository](https://github.com/Nixtla/neuralforecast). |
| First broad anomaly baseline — **PyOD** | Operations/data-quality monitoring and unusual-case prioritization. Return scores, thresholds and ranked cases. | BSD-2-Clause library of trainable classical/neural methods, not one pretrained detector. Its agent/MCP integration is also an architectural reference. [Official repository](https://github.com/yzhao062/pyod). |
| First interaction-based recommender baseline — **Implicit: ALS/BPR** | E-commerce/media recommendations based on behavior. Return ranked item IDs and scores; coordinator can explain or enrich retrieved items. | MIT code; needs interaction data and fitting. CPU plus selected GPU algorithms. Evaluate temporal leakage and offline-to-online relevance. [Official repository](https://github.com/benfred/implicit). |

For these tasks, the LLM should formulate the analytical request and explain the result; prediction and arithmetic belong in reproducible numerical services. Preserve dataset version, feature schema, train/test split and forecast origin. An anomaly score is not proof of fraud or an explanation of its cause.

## 7. Geospatial imagery, weather and Earth systems

| Task priority / family | Business fit and harness output | Code / weights and integration considerations |
|---|---|---|
| First satellite backbone to adapt — **Prithvi-EO-2.0** | Agriculture, land-cover/change analysis, flood/burn mapping with appropriate heads. Return georeferenced features/masks. | Checked 600M weights Apache-2.0. A backbone requires a matching task head/adaptation; it is not arbitrary satellite Q&A. Preserve spectral bands, ground resolution and timestamps. [Weights](https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-600M), [TerraTorch](https://github.com/torchgeo/terratorch). |
| Earth-system forecasting candidate — **Aurora** | Weather, air quality and other supported gridded forecasting for energy/logistics. Return spatial grids with variables, units and forecast times. | Current code/model repository MIT. README also describes research development and asks commercial users to contact the team; distinguish that language from an explicit noncommercial license. Requires compatible input variables/grids. [Code](https://github.com/microsoft/aurora), [weights](https://huggingface.co/microsoft/aurora). |

Geospatial outputs require a coordinate reference system and nodata masks. A normal RGB screenshot usually discards spectral and georeferencing information that these workers need.

## 8. Medical imaging, microscopy, neuroscience, proteins and chemistry

| Task priority / family | Business/research fit and harness output | Code / weights and integration considerations |
|---|---|---|
| First microscopy pilot — **Cellpose / Cellpose-SAM** | Cell/nucleus segmentation, counts and morphometry. Return instance masks and numerical measurements with physical scale. | Code and checked Cellpose-SAM weights BSD-3-Clause. Validate split/merged instances and domain fit. [Code](https://github.com/MouseLand/cellpose), [weights](https://huggingface.co/mouseland/cellpose-sam). |
| First ready anatomy-segmentation candidate — **TotalSegmentator** | CT/MR region segmentation and research cohort measurements. Return masks, region statistics and spatial metadata. | Code and open tasks such as total/total_mr Apache-2.0; selected specialized tasks require separate licenses. Current repo includes capability discovery and MCP support. [Official repository](https://github.com/wasserth/TotalSegmentator). |
| First custom segmentation training framework — **nnU-Net** | A task-specific 2D/3D medical segmenter when labels exist. Return validated masks and inference configuration. | Apache-2.0 code; external checkpoint terms vary. Framework rather than a universal pretrained anatomy model; training and labeled validation needed. [Official repository](https://github.com/MIC-DKFZ/nnUNet). |
| Prompted segmentation research candidate — **MedSAM2** | Medical-volume/video annotation and prompted masks. Return mask plus original prompt and volume geometry. | Code Apache-2.0; official weight card explicitly says research/education only despite CC-BY-SA metadata. Treat commercial suitability as unresolved/restricted, not permissive. [Code](https://github.com/bowang-lab/MedSAM2), [weights](https://huggingface.co/wanglab/MedSAM2). |
| Neuroscience encoding research candidate — **TRIBE v2** | Video/audio/text stimuli → predicted fMRI responses. Return time × cortical-location arrays and stimulus/space metadata. | Project/weights CC-BY-NC-4.0, with additional component terms. This does not analyze arbitrary scans or decode thoughts. Profile feature extraction and predictor stages separately. [Code](https://github.com/facebookresearch/tribev2), [weights](https://huggingface.co/facebook/tribev2). |
| First biomolecular-complex candidate — **Boltz-2** | Molecular structure and binding-related prediction for discovery research. Return structures, numerical scores and model confidence outputs. | Publisher explicitly licenses code and weights MIT. GPU preferable; validate predictions against the actual assay/problem rather than treating them as experimental observations. [Official repository](https://github.com/jwohlwend/boltz). |
| First protein representation baseline — **ESM-2** | Protein embeddings and downstream function/property models. Return sequence features and task-specific scores. | Code and checked 650M weights MIT; original repository archived. ESM3 has different terms and is not covered by this statement. [Code](https://github.com/facebookresearch/esm), [weights](https://huggingface.co/facebook/esm2_t33_650M_UR50D). |
| First assay-trained molecular baseline — **Chemprop** | Molecular property/activity prediction when training data exists. Return property predictions and uncertainty where configured. | MIT implementation; trainable message-passing models, not a single universal pretrained drug model. Check external weights/datasets separately. [Official repository](https://github.com/chemprop/chemprop). |

These are workflow components, not evidence that an LLM can independently perform clinical interpretation. For the user's intended neuroimaging route, anatomy segmentation and stimulus-response prediction are separate capabilities with different inputs and evaluation targets.

## 9. Robotics and action policies

| Task priority / family | Business/research fit and harness output | Code / weights and integration considerations |
|---|---|---|
| First compact policy architecture to study — **Octo** | Manipulation research and adaptation to robot embodiments. Return action sequences with the expected control representation. | Code and checked Base 1.5 weights MIT. Requires compatible observations/actions and often task adaptation. [Code](https://github.com/octo-models/octo), [weights](https://huggingface.co/rail-berkeley/octo-base-1.5). |
| VLA comparison — **OpenVLA** | Language-conditioned manipulation and fine-tuning. Return policy actions through a separate control interface. | Code MIT; pretrained weights inherit Llama-2 Community License. New robot domains typically require demonstrations/fine-tuning. [Official repository](https://github.com/openvla/openvla). |

The LLM can assign goals and request observations; the policy and control stack handle fast action execution. A text-tool-call loop is not a replacement for a robot controller.

## 10. Additional capabilities: structured extraction and image creation

| Task priority / family | Business fit and harness output | Code / weights and integration considerations |
|---|---|---|
| First compact entity-extraction candidate — **GLiNER multilingual v2.1** | Contract/document entity extraction and data normalization. Return exact text spans, labels, offsets and scores for specified entity types. | Checked checkpoint Apache-2.0; code/runtime license should be recorded separately. Compare against rules and prompted LLM extraction on the actual labels and languages. [Official model card](https://huggingface.co/urchade/gliner_multi-v2.1). |
| Permissive image-generation baseline — **FLUX.1-schnell** | Marketing illustrations, visual drafts and design assets. Return generated image, prompt, seed and generation parameters. | Selected weights Apache-2.0; code/runtime terms separate. GPU/offloading workload. This is a verified baseline, not a claim it is the latest/best generator; do not extend its license to every FLUX checkpoint. [Official model card](https://huggingface.co/black-forest-labs/FLUX.1-schnell). |

Generated images/audio are new artifacts, not observations of the input or evidence that a scientific statement is true. Keep their provenance explicit. This scan does not exhaust translation, generative video/3D, graph learning, security detection, materials science or every language/domain variant; those warrant task-specific follow-up if they enter the product scope.

## What the common adapter contract should preserve

This is the proposed harness design, not a standard claimed by the individual projects above.

| Common envelope | Why it matters |
|---|---|
| Input artifact IDs and immutable hashes | Know which original image, volume, waveform or table was analyzed |
| Capability name, implementation and checkpoint revision | Reproduce the exact method and distinguish model variants |
| Code license, weight license, component terms, access status | Avoid assuming all checkpoints inherit a repository badge |
| Parameters, preprocessing and transformations | Track resizing, normalization, crops, registration and resampling |
| Typed result payload | Boxes, masks, trajectories, transcripts, grids and probabilities retain their structure |
| Coordinate system, units and timebase | Prevent pixel/mm, relative-depth/meters, sample/second and atlas-space confusion |
| Quality flags and uncertainty semantics | Preserve missing evidence and model failure; do not invent a confidence score |
| Artifact references and inspectable renderings | Large arrays remain available while the coordinator sees useful evidence |
| Runtime, peak memory and cache state | Measure cost, latency and reproducibility |

The deterministic adapter structures/validates tool output. The LLM decides what evidence to request and explains the results; it should not have to reconstruct geometry from prose or calculate volume from a screenshot. A result can be numerically precise yet wrong because the segmentation is wrong. Validation should therefore inspect both the specialist prediction and the downstream arithmetic.

Preserve original images, videos, arrays and waveforms. A caption or global vector is a useful representation, not a complete substitute. The coordinator must be able to request a crop, retrieve a frame, view an overlay, compare outputs or run a numerical operation on the original data.

## Inference and deployment planning

These are engineering planning tiers, **not verified minimum hardware requirements or guarantees that every listed model fits**. Use the selected model's actual installation guide and profile representative inputs before purchasing hardware.

| Tier | Representative jobs | Initial approach |
|---|---|---|
| CPU / edge worker | OpenCV measurements, VAD, fitted small tabular/recommender models, smaller OCR/embedding options | Begin on existing hardware; establish latency and throughput first. Some workloads can be accelerated later. |
| Shared GPU worker | Detection, segmentation, moderate ASR, embeddings, small document VLMs | Start with one rented GPU and a queue. A 24 GB-class rental is a reasonable experiment platform for selected smaller variants, not a universal fit claim. |
| Larger-memory or staged GPU jobs | Large document models, long videos, multiview geometry, large biological workloads, TRIBE feature pipelines and generation | Rent a larger configuration as measurements justify it. Stage models, cache features and load on demand; avoid buying for an unmeasured worst case. |
| Domain data pipeline | fMRI volumes, Earth-system grids, long recordings, large catalogs | Host RAM, storage throughput and preprocessing can dominate; GPU VRAM is only one constraint. |

Weights can reside on disk without staying in VRAM. One GPU can execute multiple specialists sequentially; concurrent requests need explicit admission control. Keep high-use small models warm; load rare models on demand. Different frameworks should have isolated workers/environments so CUDA/framework dependencies do not dictate the whole system.

For every candidate measure: cold/warm latency, end-to-end throughput, peak GPU memory, peak host RAM, disk/cache growth, input limits, batch effects, and accuracy after quantization/export. Include data loading and postprocessing. Training/fine-tuning resources are a separate estimate from inference resources. No dollar-cost or universal VRAM estimate is defensible without the chosen workloads and service target.

## Recommended adapter sequence

For the user's **vision-first research aim**, my proposed first sequence is:

1. **Artifact inspection and OpenCV measurement:** establish image geometry, crops, transforms and reproducible numerical outputs.
2. **One OCR pipeline:** PaddleOCR is the initial candidate; benchmark against direct multimodal inference and one alternative on your own documents.
3. **Grounding DINO plus SAM 2:** test object discovery, masking and iterative correction with distinct structured outputs. Alternatively use a single fine-tuned RF-DETR if categories are known.
4. **Cellpose for the biological pilot:** a narrow test of instance counting and physical measurements.
5. **One retrieval stack:** BGE-M3 or Qwen3 embedding/reranking; add visual page retrieval only if textual extraction loses required evidence.
6. **One beyond-vision demonstration:** Chronos or an ASR worker, to prove the registry supports different data contracts rather than only image tools.

Do not interpret this as six simultaneous installations. Implement and evaluate each capability before increasing the fleet. Add TotalSegmentator when the target task is anatomical measurement; add TRIBE only for a defined stimulus-to-brain-response experiment.

## How to establish that a model deserves to stay in the fleet

For each business task compare: the base multimodal model, an equal-budget base-model alternative, a fixed specialist pipeline, and the adaptive harness using the same specialists. Score actual task outcomes, cost and failure recovery. In addition, measure specialist performance independently and inspect whether the coordinator changes its conclusions appropriately when relevant evidence changes.

Use task-specific metrics: OCR field accuracy; detection precision/recall; instance counting error; segmentation quality; physical measurement error; ASR word error; diarization error; retrieval recall/ranking; forecast loss and interval coverage. Do not reduce these to one undocumented “vision score.” Confidence calibration and abstention matter when inputs leave the validated domain.

Reject an adapter if it adds latency without new accuracy or capability, if its outputs cannot be aligned to source evidence, or if the controller routinely misuses them. A fixed pipeline winning is a useful result: it means the LLM may belong at the interface and interpretation layer rather than in every execution decision.

The complementary architecture reading list is in [the harness reference guide](harness-reference-guide-2026-09-18.md).
