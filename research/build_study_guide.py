from pathlib import Path
import json, re, html
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
md = MarkdownIt('commonmark', {'html': True}).enable('table')
pages = []
def add(slug, title, deck, minutes, body, visual='', question='', answer='', essential=True):
    pages.append(dict(id=slug, title=title, deck=deck, minutes=minutes, body=md.render(body), visual=visual, question=question, answer=answer, essential=essential))

add('start', 'Your study day, mapped out', 'Start here · no installation required', 8, '''
You want an LLM to coordinate a fleet of specialist models: ask for a measurement, inspect its evidence, request a closer look, and explain the result. This guide teaches the concepts you need to decide what to build. You do not need to know neural-network mathematics first.

**By the end, you should be able to draw your proposed system, explain who computes each result, choose a first task, and describe how you will test whether it helps.** You will not have trained a model or demonstrated AGI. Those are different outcomes.

### A realistic plan for tomorrow

| Session | Study | Leave with |
|---|---|---|
| 45 minutes | Foundations, representations, native vision and OpenCV | Explain the difference between a model, a library and a harness |
| 10 minutes | Break | Rest your eyes |
| 50 minutes | Vision tasks, human perception and the agent loop | Sketch a request → evidence → follow-up cycle |
| 15 minutes | Break | Keep one unanswered question in your notes |
| 50 minutes | Output contracts, memory and inference hosting | Explain where masks live and why GPU memory matters |
| 30 minutes | MRI/fMRI and TRIBE, if that domain matters first | Separate scan analysis from stimulus-response prediction |
| 15 minutes | Break | — |
| 50 minutes | Evaluation, harness reading and design decisions | Choose a prototype and its comparison experiments |
| 30 minutes | Browse only the model categories you need; complete the design exercise | Write your one-page project brief |

That is about **4¼ hours of focused study plus breaks**. It is a suggested allocation, not a promise of mastery. The full catalog and glossary are reference material; do not try to memorize 50 models in one day. Individual page reading estimates exclude following external papers or taking detailed notes.

### How to use this guide

- Use **Previous / Next**, the page selector, or the contents sidebar. Pages have stable links you can bookmark.
- **Core route** hides the long model-catalog chapters from the reading sequence. **Full library** includes everything.
- Underlined concept buttons open a definition. The glossary collects all definitions in one place.
- Search finds matching pages across the whole guide, including catalog and glossary text.
- Mark a page understood only when you can answer its self-check. Notes and progress save in this browser when local storage is available. Export them for a portable backup.
- **Print / PDF** includes the entire guide, even pages currently hidden by pagination. External reading links need internet; the lessons and visuals work offline.

### What is evidence, and what is a recommendation?

The model catalog reflects research checked on **18 September 2026**. This learning edition was prepared on **19 September 2026**. Linked papers and official documentation support factual descriptions. Suggested architecture, study order and integration rankings are our engineering recommendations. Interactive examples are explicitly invented teaching examples—not live model predictions or benchmark results.
''', question='What should you be able to produce by the end of tomorrow?', answer='A concrete task definition, a system diagram, a typed result example, a first model shortlist, and an evaluation plan. A running fleet is not a prerequisite for understanding the design.')

add('big-picture', 'The idea in one picture', 'A coordinator, specialists, and inspectable evidence', 10, '''
Imagine a laboratory. A researcher asks a question. A microscope produces an image. A technician runs an analysis. A spreadsheet calculates measurements. The researcher compares the evidence and explains it. Your proposed system separates similar responsibilities.

The **LLM** is a language model that proposes and interprets steps. A **specialist model** performs a narrower learned task, such as locating cells. A **harness** is the software around the LLM that makes tools available, executes requests, tracks state and returns results. A **worker** is the process that actually performs computation. An **artifact** is a saved piece of evidence, such as an image, mask or result file.

“Brain layer” is a useful product metaphor for the coordinator. It does not establish that the system thinks, feels, perceives or learns like a human brain. You can test capabilities without resolving consciousness.

### A concrete request

**User:** “Count the cells in this microscopy image and show which ones you counted.”

1. The harness saves the image and gives it an ID.
2. The LLM asks a cell-segmentation tool to process that ID.
3. The worker returns a mask that assigns each detected cell an instance ID.
4. Deterministic code counts distinct IDs and computes areas.
5. The harness stores complete outputs and returns a summary plus an overlay.
6. The LLM inspects those observations and may request a crop around ambiguous cells.
7. The answer refers to the stored evidence and reports unresolved limitations.

The final arithmetic can be exact while the count is wrong: two touching cells may have been merged into one predicted instance. Correct code does not rescue an incorrect prediction.

### Three approaches worth comparing

**Direct multimodal model:** ask the model about the image. **Fixed pipeline:** always run the same segmentation and counting steps. **Adaptive harness:** let the LLM decide when to run, crop, retry or use another tool. The adaptive version earns its complexity only if it improves an outcome you care about.
''', visual='architecture', question='Which component should count mask IDs?', answer='Numerical code in the adapter or analysis worker. The LLM can decide to request the count and explain it, but should not manually count a long JSON list.')

add('ml-basics', 'The minimum ML vocabulary', 'Learn the parts before choosing the products', 15, '''
### A model is a learned function

A model takes inputs and produces outputs according to learned numerical settings called **weights** or **parameters**. A detector might map an image to object boxes. A forecast model might map past demand to future demand estimates. The same word “model” covers systems with very different inputs, outputs and intended tasks.

**Training** changes weights using examples and a learning objective. **Inference** runs an already-trained model on a new input. **Fine-tuning** continues training to adapt a model to a task or domain. **Prompting** changes the request or examples presented at inference time; it usually does not change model weights.

Saving an agent conversation is not the same as training its LLM. A harness may remember prior observations in a database while the underlying model remains unchanged.

### Library, checkpoint, pipeline: three different purchases of effort

| Thing | Everyday meaning | Example | Work still required |
|---|---|---|---|
| Library | A toolbox of functions | OpenCV, XGBoost | Choose operations; for XGBoost, fit a task-specific predictor |
| Checkpoint | Saved trained weights | A particular SAM 2 release | Load compatible code, preprocess inputs and validate fit |
| Pipeline | A sequence of operations | OCR detection → recognition → table parsing | Configure stages and validate the combined outcome |
| API | An agreed way to request work | A function call or service endpoint | Send correct arguments and handle results/errors |
| Harness | The coordinator's operating machinery | DeepSeek Harness, smolagents | Add your domain capabilities and evaluation |

### Generalization is the actual challenge

A model can perform well on its training distribution and fail on a different one. A factory camera, scanner, stain, language, accent, lighting condition or business process can change the inputs enough to matter. This is **domain shift**. “Pretrained” means somebody trained it already; it does not mean it understands your domain reliably.

A **baseline** is a simple comparison system. A **benchmark** is a defined task set and scoring procedure. A **held-out test set** is data reserved for assessment rather than tuning. Your test set should resemble the real questions you want the system to answer.

You do not need backpropagation, calculus or distributed training on day one. You do need to understand input/output shapes, versions, preprocessing, error handling and how to compare predictions with known answers.
''', question='If you add examples to a prompt, have you fine-tuned the model?', answer='No. Prompt examples alter the inference context. Fine-tuning changes learned weights through training.')

add('representations', 'What an image looks like to software', 'Pixels → arrays → features; none is the whole story', 15, '''
A digital image is a grid of **pixels**. In a common color representation, each pixel has red, green and blue channel values. A 640 × 480 RGB image has 640 × 480 × 3 channel values. A grayscale image can use one channel. Medical data can use different numeric ranges and physical meanings.

An **array** stores a regular grid of numbers. A **tensor**, in this context, generalizes that idea to several axes. An image might have shape `[height, width, channels]`; a video adds time; a medical volume adds depth. Frameworks may order axes differently. Shape labels are part of the contract, not a cosmetic detail.

A **feature** is a derived signal useful for a task. An edge detector produces edge responses. A neural encoder produces learned features. An **embedding** is a numerical representation often used for comparison or retrieval. Similar embeddings can help find related items, but a single vector is not a complete, lossless copy of the image.

### Four representations can coexist

| Representation | Good for | What can be lost or missing |
|---|---|---|
| Original image | Reinspection and new analyses | Does not itself explain objects |
| Caption | Quick semantic summary | Small details, geometry, uncertainty |
| Embedding | Search and grouping | Directly interpretable measurements |
| Structured prediction | Boxes, masks, regions, trajectories | Anything the chosen model failed to predict |

Your system should retain the original and allow several derived views. It does not need to choose “only text” or “only embeddings.”

### Coordinates are not self-explanatory

Suppose a box is `[20, 30, 80, 90]`. Does that mean left/top/right/bottom, or left/top/width/height? Are values pixels or normalized fractions? Is the origin top-left? Is it relative to the source or a crop? Without those answers, valid-looking numbers can silently describe the wrong region.

If a crop starts at original pixel `(100, 50)`, then local point `(20, 30)` maps to `(120, 80)` before any resizing. If the crop was resized, you must undo that scale too. Save the transform rather than asking the LLM to guess it.

The visual below is deliberately tiny. Real images contain many more samples; magnification enlarges available samples and does not recover details never recorded.
''', visual='pixels', question='Why keep the original image after producing an embedding?', answer='The embedding was optimized for a particular purpose and may discard details needed later. Another worker may need original pixels, resolution, metadata or a new crop.')

add('native-vision', 'What built-in vision does—and what tools add', 'Complementary routes to an answer', 12, '''
Multimodal language models can accept more than text. A common design transforms image content into learned visual representations that interact with the language model. Implementations differ; do not assume every commercial model uses one identical encoder or tokenization method.

Built-in vision is valuable for interpreting scenes, linking visual content to a question, and reasoning about observations. Its accuracy on counting, tiny objects, exact chart values and spatial relationships depends on the model and task. A confident sentence is not a measurement guarantee.

Specialists can add outputs that the coordinator would otherwise have difficulty producing reliably: explicit masks, timestamped transcripts, georeferenced grids, or reproducible numerical measurements. They can also fail or add unnecessary latency.

### “Use OpenCV instead of GPT vision” is not one switch

For **“What is happening in this scene?”**, OpenCV alone does not supply a general semantic answer. For **“What is the area of this calibrated foreground mask?”**, numerical code is an appropriate calculator. For **“Which object is the damaged package?”**, a detector/segmenter, an inspection model, and a reasoning model may each have a role.

Your coordinator can receive selected original images, tool-generated overlays and structured measurements together. If the chosen coordinator is text-only, it can use tool results but cannot directly inspect an image merely because a file path appears in its prompt. The input transport must actually deliver a supported visual input.

### What earlier research establishes

[BLINK](https://arxiv.org/abs/2404.12390) evaluates diverse perception tasks, highlighting that general visual question answering and precise perception are not interchangeable. [ViperGPT](https://arxiv.org/abs/2303.08128) studies composing visual modules through generated programs. [Visual Sketchpad](https://arxiv.org/abs/2406.09403) studies using visual intermediate artifacts and tools during reasoning.

These papers motivate experiments. Their results concern particular models, tool sets and datasets at publication time. They do not prove your 2026 coordinator will improve on your data. Avoid carrying an old percentage into a claim about a new system without reproducing the comparison.
''', question='Should every image question trigger all the vision tools?', answer='No. Use the question and validated capability fit to select useful tools. Simple questions may need no specialist; running more tools can add cost and conflicting errors.')

add('opencv', 'OpenCV: the ruler and image workbench', 'Useful precision without pretending it understands everything', 12, '''
[OpenCV](https://github.com/opencv/opencv) is a computer-vision library: code for manipulating and analyzing images. It includes classical operations and interfaces for some learned methods. Treating “OpenCV” as a single pretrained intelligence is a category mistake.

### Useful operations, explained

**Resize:** change the number of samples representing the image. **Crop:** keep a selected region. **Threshold:** classify pixels according to a numeric cutoff. **Contour:** a curve around a detected region. **Connected components:** groups of foreground pixels joined under a chosen neighborhood rule. **Morphology:** shape operations such as removing small specks or closing gaps. **Optical flow:** an estimate of apparent pixel motion between images.

Each operation has assumptions. Thresholding can work for dark objects on a consistently bright background. It can fail under uneven illumination. Two touching cells may become one connected component. A shadow may look like a defect. Classical methods are worth testing because they can be cheap, understandable and sufficient on controlled inputs.

### Worked measurement

Suppose a validated mask contains **400 foreground pixels** and the image has a known scale of **0.5 micrometers per pixel in both directions**. Each pixel covers 0.25 square micrometers. The estimated area is `400 × 0.5 × 0.5 = 100 µm²`.

That result assumes the scale applies to this image, the mask is correct, and no unrecorded resizing occurred. If horizontal and vertical scales differ, multiply them separately. If you only know pixel counts, report pixel area rather than inventing a physical unit.

### The right division of work

- A specialist predicts which pixels belong to a cell.
- OpenCV or equivalent array code checks and measures the mask.
- The adapter labels units and coordinate systems and saves the result.
- The LLM explains the measurement and asks for another observation when needed.

You may never need a neural model for a highly controlled visual inspection task. Include a simple classical pipeline as a baseline before assuming deep learning is necessary.
''', visual='mask', question='A contour calculation is exact. Is the detected object necessarily correct?', answer='No. The contour may perfectly describe the wrong thresholded region. Evaluate the segmentation or detection stage as well as the arithmetic.')

add('vision-tasks', 'Different vision models answer different questions', 'A box, a mask, a track and a depth map are not interchangeable', 15, '''
### Learn the output before learning the brand

| Task | Plain-language question | Typical output | Common trap |
|---|---|---|---|
| Classification | What category does this input belong to? | Label and score | No location is implied |
| Detection | Where are the objects? | Bounding boxes, labels, scores | Missed/duplicate objects affect counts |
| Semantic segmentation | Which category is each pixel? | Class map | Two adjacent cells may share one class |
| Instance segmentation | Which individual object owns each pixel? | Separate object masks | Touching objects can merge |
| Tracking | Is this the same object in later frames? | IDs and trajectories | IDs can swap or disappear |
| OCR | What text is visible, and where? | Text and regions | Characters or reading order can be wrong |
| Depth estimation | What is nearer or farther? | Depth map | Relative values may not be meters |
| Pose estimation | Where are key body/joint points? | Keypoints and scores | Occluded joints can be guessed |
| Visual retrieval | Which stored image/page resembles the query? | Ranked IDs | Similarity does not prove a fact |

### A detector and a segmenter can cooperate

Grounding DINO can propose object locations from a text query. SAM 2 can use prompts such as points or boxes to produce masks. These are candidate modules, not guaranteed universal recognizers. A known-category detector fine-tuned on your actual products may be a better fit than open-vocabulary discovery. [Grounding DINO](https://github.com/IDEA-Research/GroundingDINO), [SAM 2](https://github.com/facebookresearch/sam2)

### Counting requires a definition

“How many people?” could mean visible faces, visible bodies, or unique individuals across a video. Counting detections in every frame will repeatedly count the same person. Counting track IDs can still overcount if a tracker assigns a new ID after occlusion. Define the target before choosing the model.

### Depth requires a scale contract

A relative-depth model can order objects by apparent distance without recovering a trustworthy physical scale. Metric depth seeks physical units, but its validity depends on model assumptions, inputs and domain. A single 2D image generally does not uniquely determine all 3D geometry. Preserve the distinction in the capability name, such as `estimate_relative_depth` versus `estimate_metric_depth`.

The catalog later ranks candidates by the job they perform. A mask model cannot meaningfully outrank a speech recognizer in a universal “best model” list.
''', question='Why is semantic segmentation insufficient for some cell-counting tasks?', answer='It can label all cell pixels as the same class without distinguishing individual cells. Counting usually needs instance separation or another validated counting method.')

add('human-vision', 'What to borrow from human vision', 'Engineering inspiration, with the analogy kept honest', 12, '''
Human seeing is an active biological process. The eyes collect light; retinal and brain circuits transform signals; gaze changes which details are sampled. A useful engineering lesson is to acquire the next observation deliberately rather than expecting one compressed view to answer every question.

The **fovea** is the retinal region associated with highest visual acuity. **Saccades** rapidly move gaze so different parts of a scene can be examined. A study of neural responses around eye movements illustrates that perception and eye movement are closely linked. For our system, this motivates a coarse overview followed by targeted high-resolution crops. That is an engineering analogy, not a simulation of the same neural mechanism. [Zirnsak et al., 2014](https://www.nature.com/articles/nature13149)

Peripheral vision is not simply a blurry version of central vision. Research on **crowding** examines how nearby items interfere with identifying a target and how summary representations may account for information loss. A practical hypothesis for your harness is that a full-image summary may miss distinctions that a local inspection reveals. The machine failure mechanism must still be tested independently. [Balas, Nakano & Rosenholtz, 2009](https://pmc.ncbi.nlm.nih.gov/articles/PMC2923917/)

Even during fixation, small eye movements occur; research relates them to perception and adaptation. This does **not** imply that artificially jittering images will make an LLM conscious or automatically improve accuracy. Borrow the principle of active sampling, then measure any proposed technique. [Martinez-Conde, Macknik & Hubel, 2004](https://www.nature.com/articles/nrn1348)

### Translate the inspiration into testable design

| Biological inspiration | Proposed engineering behavior | Test |
|---|---|---|
| Selective detailed inspection | Overview → crop a relevant region | Does small-object accuracy improve at a fixed budget? |
| Multiple useful representations | Keep raw input, features, masks and measurements | Can a later question recover needed evidence? |
| Repeated observation | Compare frames or alternate views | Does ambiguity decrease rather than just repetition increase? |
| Limited resources | Spend extra compute where it changes an answer | Is accuracy per unit cost better? |

### What this does not establish

Senses are neither a proven sufficient condition for AGI nor evidence of subjective experience. A modular tool system does not thereby acquire human perception. Your feasible research claim is narrower and stronger: **an active evidence-gathering policy can improve defined multimodal tasks under measured constraints**.
''', visual='fovea', question='What is a defensible claim based on the eye analogy?', answer='Targeted inspection may improve certain visual tasks; test it against an equal-budget baseline. It is not evidence that the harness feels or uses the same mechanisms as a human visual system.')

add('loop', 'Follow one request through the harness', 'The agent loop, step by step', 15, '''
An **agent loop** repeats a small sequence: assemble context, ask the model what to do, execute an allowed action, record the result, then ask the model again if necessary. The harness owns that loop. The LLM supplies proposed actions and interpretations within it.

### What each component owns

**Capability registry:** describes available operations, inputs, outputs and constraints. **Router:** chooses an implementation or worker for a request. **Adapter:** translates the common request into the specialist's expected format and translates its output back. **Worker:** loads the model or algorithm and executes it. **Artifact store:** retains complete input/output data. **Session log:** records the interaction and evidence references.

The LLM does not need to choose low-level details such as a CUDA device every turn. Deterministic rules can route a requested capability to an available implementation. Some workflows should be fixed graphs: known stages with explicit dependencies. Others benefit from flexible agent decisions. They can coexist.

### Use the example below

Step through an invented cell-counting request. Nothing is being inferred in your browser. The example shows the shape of an actual implementation: small structured messages around larger data artifacts.

### Limits keep the loop purposeful

Set an operation budget, a deadline and a stopping rule. “Continue until confident” is weak because a model can become confident without obtaining new evidence. Better: stop when required measurements and quality checks exist; if ambiguity remains after a defined retry, report it.

Distinguish **failure** from **valid emptiness**. “No objects detected” is a valid result if inference completed. “GPU memory exhausted” is an execution error. An empty list must not silently stand for both.

### A tool and a sub-agent are different

A specialist tool can simply compute a function. A sub-agent is another reasoning loop with its own context and decisions. You do not need to wrap every model in another LLM. Extra agents are useful only when delegation solves a real coordination problem.
''', visual='loop', question='Who should handle a GPU memory error?', answer='The worker reports a typed execution error. The harness applies a defined retry, smaller-batch or alternate-worker policy. The LLM should not treat the error as evidence of zero detected objects.')

add('contracts', 'How outputs become reliable evidence', 'Structured data first; explanations after', 18, '''
Your earlier question was: “Does OpenCV hand the output to GPT to structure?” A better design is for **deterministic adapter code to produce the authoritative structure**, validate it, and then let the LLM interpret it. Asking GPT to reconstruct measurements from prose adds an avoidable source of errors.

A **schema** specifies the allowed shape of data: required fields, types and constraints. **JSON** is a common text format for structured objects and lists. A schema can check that a count is an integer; it cannot prove the detector counted correctly.

### A small illustrative result

```json
{
  "status": "ok",
  "source_id": "image-001",
  "capability": "segment_cells",
  "implementation": "example-model@pinned-revision",
  "instance_count": 12,
  "mask_artifact_id": "mask-001",
  "overlay_artifact_id": "overlay-001",
  "coordinates": "original_image_pixels",
  "pixel_size_um": [0.5, 0.5],
  "quality_flags": ["border_objects_excluded"],
  "uncertainty": null
}
```

This is teaching data. The full mask is stored separately; the result points to it. `null` uncertainty means unavailable, not zero. The count definition excludes border objects, so that rule must be visible to the answer's reader.

### Three forms of the same result

**Machine form:** structured fields and artifact references, used by code. **Model form:** selected fields plus supported visual inputs, used in the next reasoning step. **Human form:** a readable table, overlay or report. These should derive from the same evidence rather than become three separately invented stories.

[DeepSeek's tool contract](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cookbook/adding-a-tool.md) explicitly distinguishes canonical values, model-facing rendering and UI presentation. Its canonical return value is not automatically a durable archive of your scientific arrays; provide that storage explicitly.

### Avoid false precision

A detector score of 0.92 does not necessarily mean “92% probability this answer is correct.” Score semantics differ by model. **Calibration** evaluates whether stated probabilities correspond to observed frequencies on relevant data. Preserve the score type, decision threshold and available validation. Do not ask the LLM to invent a universal confidence number.

Also preserve model revision, preprocessing, input hashes, units, transformations and quality flags. Those details make reruns comparable and disagreements investigable.
''', question='What does schema validation establish?', answer='That the data obeys the declared structural contract. It does not establish semantic correctness, model accuracy, valid calibration or correct physical scale.')

add('state', 'Memory, context and storage are different', 'Keep large evidence available without flooding the prompt', 12, '''
The **context window** is the bounded input a model can consider in a request. **Session state** is what the application remembers about ongoing work. **Artifact storage** holds large source and derived data. **Model weights** are learned parameters. These are different kinds of memory.

A conversation may summarize an earlier tool output because it no longer fits in context. That does not mean the original evidence should disappear. The summary should retain references that allow the model or a human to reopen the relevant artifact.

### What goes where?

| Data | Typical location | What the coordinator receives |
|---|---|---|
| Original 3D scan | Artifact storage | ID, modality, shape, geometry, selected views |
| Full segmentation mask | Artifact storage | ID, statistics and overlay |
| Embeddings for a million documents | Retrieval index | Top candidate IDs and selected evidence |
| Run history | Session/event log | Relevant current state and past conclusions |
| Loaded model weights | RAM or GPU memory | Usually an implementation identifier |

A **cache** saves a reusable computation result. Its key should account for the source, checkpoint, preprocessing and parameters. Reusing a mask from an older model while labeling it as a new model's output would corrupt provenance.

An **event log** records facts such as “tool requested,” “job completed,” and “result referenced.” An append-only design keeps a trace rather than overwriting history. Replaying a log can reproduce what evidence the coordinator saw. Reproducing the exact original numerical output additionally depends on preserving artifacts and execution details; random or nondeterministic computations can complicate reruns.

### Source text is data, not automatic authority

An OCR result may contain a sentence such as “ignore your instructions.” That is content from the document, not permission to change the workflow. Treat documents and tool content as untrusted observations. Bound tools by actual application permissions, validate requests, and avoid exposing irrelevant credentials to workers. This is part of designing a tool system that operates on arbitrary external material.

For a first local prototype, a folder of artifacts plus a small manifest and session log may be sufficient. A distributed database is not a prerequisite for understanding this boundary.
''', question='Does saving a conversation train the model?', answer='No. Application memory stores information for later retrieval or context. Model training changes weights through an optimization process.')

add('compute', 'Inference: what needs to run on the box?', 'Disk, RAM, VRAM and latency in plain language', 18, '''
**Inference** means running a trained model. The **CPU** handles general computation and much preprocessing. A **GPU** accelerates many neural operations. **RAM** is the machine's working memory. **VRAM** is a GPU's working memory. **Disk** retains weights and data when they are not actively being used.

A model can be downloaded on disk without occupying VRAM. It must be loaded into the appropriate working memory to execute. **Cold latency** includes loading or initialization. **Warm latency** measures an already-ready worker. End-to-end latency also includes upload, preprocessing, queuing, postprocessing and the coordinator's calls.

### A useful lower-bound calculation

Weight storage alone is approximately `parameter count × bits per parameter ÷ 8`. A one-billion-parameter model stored at 16 bits per parameter needs about **2 decimal GB for its weights alone**. That is not a promise it runs on a 2 GB GPU.

Working memory may also include activations, temporary buffers, model-specific caches, image tensors and framework overhead. Autoregressive models can keep an attention **KV cache** as sequence length increases. Vision and scientific models have different memory patterns. Quantization metadata and additional components may add storage too.

**Quantization** stores or computes with lower-precision numbers to reduce resource demands. It can change accuracy and supported operations. Evaluate the exported or quantized model you will actually deploy.

### What changes resource demand?

- Larger input images or volumes can require much more memory.
- More video frames or views increase work.
- **Batch size** means how many examples run together; larger batches may improve throughput but require memory.
- **Concurrency** means how many jobs run at once; it is not the same as batching.
- **Offloading** moves some data or computation to CPU/RAM, often trading speed for lower GPU memory use.

Use the calculator as a teaching estimate. It computes only raw weight storage, in decimal GB. It cannot size your GPU.

### A sensible first resource decision

Use your existing machine for reading, adapters and CPU tasks. When a chosen specialist requires acceleration, rent and profile an appropriate GPU before buying. A selected small-model experiment may fit a 24 GB-class GPU, but no single box can be promised to run this whole catalog concurrently. Training and fine-tuning need separate estimates.
''', visual='memory', question='If a 7B model has roughly 14 GB of 16-bit weights, is 14 GB total VRAM enough?', answer='Not necessarily. Weight storage excludes working buffers, activations, caches and other components. Measure peak memory for the actual workload and implementation.')

add('deployment', 'One machine first; workers later', 'Separate decision-making from model execution', 15, '''
The harness and the model fleet do not need to share a programming language or process. A TypeScript coordinator can call a Python service. An API-hosted LLM can coordinate local models. A fully local system can use a local coordinator model as well. These are deployment choices, not different scientific claims.

### Three layouts

| Layout | What runs where | Good reason to choose it | Tradeoff |
|---|---|---|---|
| Local experiment | Coordinator client, adapters and specialists on one workstation | Learn and debug one task | Limited memory/concurrency |
| Hybrid | Hosted reasoning model; local or rented CPU/GPU workers | Access capable coordination without hosting its weights | Network calls and data-handling constraints |
| Multi-worker service | Coordinator, queue, artifact store and workers on separate hosts | Different models need different environments or multiple users | More operational complexity |

A **process** is a running program. A **container** packages a software environment; it does not magically supply a GPU or make all dependencies compatible. A **queue** holds pending jobs. A **scheduler** decides which job gets resources. **Admission control** limits simultaneous work so memory is not overcommitted.

### Long work should return a job handle

A long volume-processing request can return `{ "job_id": "job-123", "status": "queued" }`. The harness can check status, collect artifacts when complete, or cancel the job. Avoid making the LLM repeat the same expensive request because it cannot distinguish “still running” from “failed.”

An **idempotency key** lets a service recognize a repeated request and avoid duplicate side effects or expensive duplicate jobs. A **timeout** stops waiting after a limit; it does not necessarily stop computation unless cancellation is propagated.

### Where MCP fits

The **Model Context Protocol** is one way to expose tools and resources to compatible clients. It is an interface layer. It does not perform GPU inference, determine scientific validity or replace storage and scheduling. Plain function calls or HTTP APIs are enough for an initial implementation when they fit your runtime.

Keep a small active tool set. Exposing 50 specialists at once can make selection harder and enlarge the prompt. A capability discovery step or task-specific preset can supply only relevant tools. Do not require an LLM decision for every deterministic preprocessing operation.
''', visual='deployment', question='Does adopting MCP remove the need to host the specialist models?', answer='No. MCP exposes the capability; a worker or external service still performs the computation and needs appropriate resources.')

add('medical-data', 'DICOM, MRI and fMRI without the jargon wall', 'A file format, an imaging method and a time series', 18, '''
**MRI** is magnetic resonance imaging, an imaging method. **DICOM** is a standard used to represent and exchange medical imaging data and associated metadata. They are not synonyms. A DICOM collection may contain MRI, CT or other imaging objects.

A **voxel** is a volume element: the 3D analogue of a pixel. A structural MRI can represent anatomy as a 3D array. **fMRI** commonly tracks a signal over time, making it a series of 3D volumes—a 4D array when time is counted as an axis.

Many fMRI experiments use **BOLD**, or blood-oxygen-level-dependent contrast. It measures changes related to blood oxygenation and is an indirect indicator associated with neural activity, not a direct recording of each neuron's firing. Its interpretation has physiological and measurement limits. [Logothetis et al., 2001](https://www.nature.com/articles/35084005), [Logothetis, 2008](https://www.nature.com/articles/nature06976)

### The terms you will encounter

| Term | Meaning |
|---|---|
| NIfTI | A common neuroimaging format for arrays and spatial information |
| BIDS | A standard organization and metadata convention for brain-imaging datasets |
| TR | Repetition time; relevant acquisition timing that must be interpreted for the sequence |
| Registration | Aligning data between coordinate spaces |
| Resampling | Computing samples on a different grid |
| Atlas | A reference mapping or partition of anatomy |
| Confound | A factor that can influence measurements apart from the effect being studied |
| ROI | Region of interest selected for an analysis |

[BIDS documentation](https://bids.neuroimaging.io/) explains dataset organization. These are supporting data concepts; none is itself an LLM or a learned perception model.

### The pipeline comes before interpretation

Real scan analysis must identify series and preserve orientation, voxel spacing, acquisition metadata and timing. Neuroimaging preprocessing can involve motion estimation, distortion correction and spatial alignment. The appropriate steps depend on the acquired data and analysis. fMRIPrep documents such workflows and generates inspectable reports; preprocessing is not the same as performing the downstream scientific hypothesis test. [fMRIPrep workflows](https://fmriprep.org/en/stable/workflows.html)

Do not treat a rendered slice as equivalent to the whole scan. A screenshot loses much of the array, metadata and time information. Your harness should request selected views while preserving the complete volume and transforms.

For a research prototype, begin with a clearly defined dataset and question. Anatomical segmentation, motion-quality assessment, task activation analysis and stimulus-response prediction are separate capabilities. A single generic “analyze fMRI” tool hides too many choices.
''', visual='volume', question='Why is a screenshot of an fMRI slice an incomplete input?', answer='It omits other slices, time points, acquisition timing, numeric data and spatial metadata. A screenshot can be a useful view but is not a replacement for the source dataset.')

add('tribe', 'TRIBE v2: get the direction right', 'Stimulus → predicted brain response', 12, '''
The verified [TRIBE v2 model card](https://huggingface.co/facebook/tribev2) and [repository](https://github.com/facebookresearch/tribev2) describe a neuroscience encoding system: inputs derived from video, audio and text are used to predict fMRI responses. That is a different task from interpreting an arbitrary uploaded scan.

Think of an experiment where a participant watches a movie while researchers measure brain responses. An **encoding model** asks: given information about the stimulus, what response should we predict? A **decoding model** asks a reverse kind of question: given measured brain data, what can we infer about stimuli or other variables? Reversing the arrow requires another model and evaluation; it does not happen automatically.

### A suitable harness capability

The user supplies a compatible stimulus and a defined neuroscience question. The adapter prepares the inputs, executes the feature/prediction stages, and saves predicted responses with timing and cortical-space metadata. If measured responses exist, an analysis tool can compare predictions with measurements under a specified evaluation procedure.

The coordinator explains what was predicted, which stimulus interval it refers to, and what comparison was performed. It should not describe predicted activity as a direct observation of a particular person's thoughts.

### An unsuitable shortcut

“Here is a random patient's DICOM folder; run TRIBE and tell me what is wrong” does not match that input/output contract. A scan-analysis workflow needs the relevant acquisition-aware processing and validated task models. An anatomy segmenter may help with structure measurements; a stimulus encoder answers a different scientific question.

### Resource and licensing implications

TRIBE's feature-extraction and prediction stages need separate profiling. A small final prediction component would not imply that every upstream encoder is cheap. The project is a noncommercial research release with component terms to track. Do not infer commercial permissions or a universal VRAM requirement from “open weights.”

For your first biology demonstration, a narrowly defined Cellpose segmentation/counting experiment is easier to scope. TRIBE is worth studying when your objective specifically involves stimulus-to-response modeling.
''', visual='tribe', question='Can you reverse an encoding model simply by swapping input and output?', answer='No. The reverse problem can be ambiguous and requires its own method, assumptions, training or optimization, and evaluation.')

add('evaluation', 'How to find out whether the harness helps', 'Design the experiment before adding a fleet', 18, '''
First define the claim. A useful example is: “On held-out microscopy fields, the system reduces cell-count error while keeping processing time below our workflow limit.” “Makes the LLM better at vision” is too broad to score.

### Compare four systems

| System | Purpose |
|---|---|
| Base multimodal model | Establish current capability without specialist tools |
| Base model with comparable extra budget | Check whether improvement simply comes from more calls, crops or compute |
| Fixed specialist pipeline | Test whether predetermined steps already solve the task |
| Adaptive harness using the same specialists | Measure the added value of LLM-directed selection and follow-up |

Keep question wording, datasets and scoring comparable. Save the model/version and settings. Repeated runs can reveal variability. Do not select a favorable run and report it as typical.

### Choose a task-specific metric

**Count error:** difference between predicted and reference count; average absolute error avoids cancellation of overcounts and undercounts. **Precision:** among detections you made, how many were correct? **Recall:** among real target objects, how many did you find? **Intersection over union (IoU):** overlap divided by union for predicted and reference regions. **Latency:** elapsed time. **Cost:** resources consumed under an explicit pricing or compute accounting method.

A perfect total count can hide one missed object and one false detection. For counting with evidence, assess instance quality as well as the total. A segmentation score alone may also miss the measurement errors that matter to the business.

### Avoid data leakage

Do not tune on the final test set. For microscopy, related images from the same slide can leak into both train and test. For time series, random splits can expose future information. For medical data, the same subject across splits can make results misleading. Choose splits that match the intended generalization question.

### Audit the failures

Classify them as: wrong specialist prediction; wrong tool selection or parameters; incorrect transformation/units; misinterpretation of correct evidence; execution failure; or insufficient source information. This tells you which component to improve.

**Ablation** means removing or replacing one component to assess its contribution. Ask whether cropping, OCR or iterative retries actually changed outcomes. Also test contradictory evidence: does the coordinator revise its answer appropriately, or just repeat its initial guess?

Start with a pilot to discover defects, then freeze a larger assessment. Report uncertainty and representative failures. A small pilot is a feasibility signal, not proof of broad superiority.
''', visual='metrics', question='Why compare against a fixed specialist pipeline?', answer='Otherwise you cannot tell whether the improvement came from the specialist itself or from the adaptive LLM coordination. A fixed pipeline may be cheaper and just as accurate.')

add('harness-reading', 'Read real harness code with a purpose', 'You are looking for boundaries, not memorizing repositories', 18, '''
### The reading order

| Project | What to look for | Why it matters |
|---|---|---|
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) | Plugin architecture, tool contracts, session log | Swappable capabilities and inspectable runs |
| [smolagents](https://github.com/huggingface/smolagents) | Model request → tool execution → observation loop | A compact Python starting point close to ML tooling |
| [Deep Agents](https://github.com/langchain-ai/deepagents) | Context management, persistent workflows, delegation | Longer tasks and resumability |
| [Pi](https://github.com/earendil-works/pi) | Provider layer, runtime, application separation | Clean component boundaries in TypeScript |
| [OpenHands SDK](https://github.com/OpenHands/software-agent-sdk) | Tools, conversations, local/remote workspaces | Execution isolation and remote workers |
| [Harbor](https://github.com/harbor-framework/harbor) | Tasks, environments and scored trials | Evaluation of complete agents |

These are architectural references, not a ranking of visual intelligence. DeepSeek's MIT developer preview is evolving; study its concepts and pin a version if you later build on it. Harbor is the evaluation framework intended here, not a claim that it hosts your entire model fleet. [DeepSeek introduction](https://deepseek.com/harness/en/)

### An exact first reading assignment

Open DeepSeek's [architecture document](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md). Locate the boundaries for tools, model providers and durable session events. Then read its [tool-authoring document](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cookbook/adding-a-tool.md). Find what the executor returns and how that becomes model-facing content.

Next open smolagents' [agents.py](https://github.com/huggingface/smolagents/blob/main/src/smolagents/agents.py) and [tools.py](https://github.com/huggingface/smolagents/blob/main/src/smolagents/tools.py). You do not need to understand every line. Find where a tool request is accepted, executed and added to the next observation.

### Study two actual specialist integrations

[TotalSegmentator's MCP server](https://github.com/wasserth/TotalSegmentator/blob/master/totalsegmentator_mcp/README.md) provides a concrete medical-model interface. [PyOD](https://github.com/yzhao062/pyod) documents agent-oriented anomaly-analysis tools. Trace which output is a prediction, which is a derived measurement, and which is an explanation.

### Write answers, not copied code

Where is input validation? Where is the full artifact saved? Can a long operation return a job handle? What gets logged? Who cancels work? How would you replace one detector without changing every consumer? Those six questions turn repository browsing into design knowledge.
''', question='What is the most useful reason to read two different harnesses?', answer='To distinguish fundamental responsibilities from one framework’s implementation choices. You can adopt the boundaries without copying every abstraction.')

add('decisions', 'Make the first design small and testable', 'Choose a capability boundary before choosing infrastructure', 15, '''
### My recommended first scope

Choose one of these: exact fields from a specific document type; instance counting on a defined microscopy dataset; or counting a known set of products under controlled photography. Specify accepted inputs, expected outputs and failure conditions. Choose one, not all three for the first experiment.

Use an existing coordinator model. Add one adapter. Preserve original inputs and outputs. Compare direct inference, fixed processing and adaptive use. Only add another model when a observed failure or new task justifies it.

### Decisions you can postpone

You can postpone a universal model marketplace, multi-cloud scheduling, training your own base LLM, a custom distributed database and buying several GPUs. None is necessary to establish whether structured perception evidence helps your chosen task.

### Decisions you must make early

| Decision | Example |
|---|---|
| Output semantics | Count only fully visible cells; retain instance masks |
| Coordinate contract | Original-image pixels; transforms recorded for crops |
| Source retention | Preserve raw image and physical-scale metadata |
| Model identity | Pin checkpoint and preprocessing revision |
| Failure contract | Distinguish no objects, invalid input and worker failure |
| Evaluation | Held-out slides; count error and instance quality |
| Resource budget | Defined retry/call limit; measured latency |

### Licensing is a component property

“Open source” can refer to code, weights, or a loosely described public release. They do not necessarily share a license. A family can contain permissive, custom-license and noncommercial checkpoints. The catalog records these distinctions because choosing a commercial product dependency requires checking the actual release and its components.

### What changes the architecture later?

Multiple simultaneous users justify a queue and admission control. Conflicting dependencies justify isolated workers. Slow repeated encoders justify caching. Multi-hour work justifies resumable jobs. Different input modalities justify new contracts. Add infrastructure in response to demonstrated needs.

The first real milestone is an inspectable run that answers one question, with a measurement whose origin you can trace. The second is evidence that it beats an appropriate baseline under your constraints.
''', question='What should trigger adding a second model?', answer='A specific unmet capability or recurring failure that the second model can plausibly address—and an experiment that can verify its contribution.')

add('prerequisite-skills', 'The technical skills to learn next', 'A prerequisite ladder you can follow at your own pace', 15, '''
You can understand tomorrow's architecture without becoming a machine-learning engineer first. Building it later requires a small set of practical skills. Use this ladder to locate gaps rather than studying every topic in computer science.

| Order | Skill | Minimum useful ability | You can postpone |
|---|---|---|---|
| 1 | Basic programming | Read variables, lists, dictionaries, functions and conditions | Advanced language internals |
| 2 | Files and structured data | Load a file, understand a path, inspect JSON fields | Distributed databases |
| 3 | Arrays | Understand shape, indexing, axis order, masks and units | Tensor calculus |
| 4 | Model execution | Load an existing checkpoint, preprocess an input, inspect its output | Training a foundation model |
| 5 | Services and tools | Explain request, response, validation, timeout and error | Multi-cloud operations |
| 6 | Evaluation | Keep test data separate and calculate task metrics | Large-scale experiment platforms |

### Read this tiny example in English

```python
result = {"count": 12, "source_id": "image-001"}
if result["count"] > 10:
    message = "More than ten predicted instances"
```

`result` is a variable: a name for a value. The curly braces create a dictionary mapping keys to values. The expression `result["count"]` reads the value associated with the key `count`. The `if` line checks a condition. The indented line runs when the condition is true. Nothing in this example performs vision; it operates on an existing result.

A **function** is a named operation with inputs and a returned result. A **function argument** is an input passed to that operation. This use of “parameter” or “argument” differs from learned model weights. A **package** is reusable software. An **environment** is a selected set of software versions and dependencies. A notebook is a convenient place to run small exploratory code cells; a production service has different lifecycle requirements.

### Use these resources selectively

- [Python tutorial](https://docs.python.org/3/tutorial/): lists, dictionaries, functions, files and errors. Its official introduction assumes some general programming experience; if you are completely new, treat it as a reference rather than expecting every page to be introductory.
- [NumPy absolute beginner guide](https://numpy.org/doc/stable/user/absolute_beginners.html): arrays, shapes and indexing. Practice explaining which axis means height and which means width.
- [PyTorch basics](https://docs.pytorch.org/tutorials/beginner/basics/intro.html): tensors and a model workflow. Understand inference before committing time to training.

**Optional practice after the study day:** describe a 2 × 3 array; translate one crop coordinate; read a result dictionary; and compute the precision of eight correct detections among ten detections. If these are comfortable, you have enough grounding to follow a simple adapter implementation.
''', question='Does the example dictionary demonstrate that the model found 12 real objects?', answer='No. It demonstrates how code stores and reads a number. You still need the source prediction, count definition and validation to justify the claim.', essential=False)

add('model-cards', 'How to inspect a model before adopting it', 'A repeatable reading checklist', 12, '''
A **model card** is documentation accompanying a model release. It can describe the intended task, training information, limitations, examples, evaluations and licensing. Availability and completeness vary. Read the full relevant sections rather than deciding from the repository name or a metadata badge. [Hugging Face model-card documentation](https://huggingface.co/docs/hub/model-cards)

### Read in this order

1. **Exact input and output.** Does it accept RGB images, multispectral satellite bands, audio, a time series or an already-computed feature array? Does it return labels, masks, vectors or generated text?
2. **Selected checkpoint.** Record the actual variant and revision. A family name is insufficient for reproducibility or license selection.
3. **Intended use and limits.** What languages, image types, domains or dimensions were evaluated? What is explicitly outside scope?
4. **Code and weight terms.** Check them separately, including backbone/component terms and gated download conditions. Public availability is not a universal commercial-use grant.
5. **Preprocessing.** Identify image normalization, resizing, channel order, required metadata and any sampling assumptions.
6. **Execution path.** Determine required frameworks, supported device types, and whether the example depends on custom code or additional encoders.
7. **Evaluation.** Ask which benchmark, metric and baseline produced a claimed result. Check whether your task resembles it.
8. **Output semantics.** Determine score meaning, coordinate frame, physical units and whether full outputs can be saved.

### Three decisions after reading

**Adopt for a pilot:** input/output fit is clear and terms/resources are compatible, but performance still needs testing. **Research-only candidate:** scientifically relevant with restrictions or unresolved deployment fit. **Reject for this task:** incompatible input, missing needed output, unsupported license or an unnecessary capability.

### Example: the wrong family-level assumption

The catalog documents that Depth Anything V2 Small and its larger variants have different weight terms. It also distinguishes SAM 2 from SAM 3 licensing. The lesson is to record the exact release, not to infer a permanent rule about a brand. [Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2), [SAM 2](https://github.com/facebookresearch/sam2), [SAM 3](https://github.com/facebookresearch/sam3)

Finish by writing one sentence: “This checkpoint takes ___, returns ___, and we will evaluate it on ___.” If you cannot fill the blanks, you are not ready to make it a default tool.
''', question='What is the difference between “available to download” and “ready to use in my product”?', answer='A downloadable model can still have incompatible terms, unsupported inputs, difficult deployment requirements or untested accuracy for your application.', essential=False)

# Preserve the researched catalog, including all checkpoint-specific caveats and links.
catalog = (ROOT / 'specialist-model-landscape-2026-09-18.md').read_text()
intro = catalog.split('## 1.')[0]
add('catalog-map', 'The specialist landscape at a glance', 'Integration priorities, not a universal leaderboard', 10, intro, essential=False)
titles = ['Documents and OCR','Detection, masks and inspection','Motion, depth and 3D','Audio and speech','Retrieval and reranking','Tabular data and forecasting','Geospatial and weather','Medical and scientific models','Robotics and action','Entity extraction and generation']
sections = re.split(r'(?m)^## (?=\d+\.)', catalog)[1:]
for i, chunk in enumerate(sections):
    body = chunk.split('\n',1)[1].split('\n## ')[0]
    rendered = md.render(body)
    soup = BeautifulSoup(rendered, 'html.parser')
    for table in list(soup.find_all('table')):
        cards = soup.new_tag('div', attrs={'class':'model-grid'})
        for row in table.select('tbody tr'):
            cols=row.find_all('td')
            if len(cols)<3: continue
            card=soup.new_tag('article', attrs={'class':'model-card'})
            h=soup.new_tag('h3'); h.append(BeautifulSoup(cols[0].decode_contents(),'html.parser')); card.append(h)
            p=soup.new_tag('div'); p.append(BeautifulSoup(cols[1].decode_contents(),'html.parser')); card.append(p)
            label=soup.new_tag('h4'); label.string='License and deployment'; card.append(label)
            p=soup.new_tag('div'); p.append(BeautifulSoup(cols[2].decode_contents(),'html.parser')); card.append(p)
            cards.append(card)
        table.replace_with(cards)
    pages.append(dict(id=f'catalog-{i+1}', title=titles[i], deck='Model catalog · consult when the task calls for it', minutes=10, body=str(soup),visual='',question='Which output from this category would your coordinator actually consume?',answer='Name the typed output and its source reference: for example boxes and masks, timestamped transcripts, ranked source IDs, or forecast quantiles. A brand name alone is not a capability contract.',essential=False))

add('exercise', 'Your first project brief', 'A worked example, then your own version', 20, '''
### Worked example: microscopy counts with visible evidence

**User and task:** a researcher reviews images from one defined cell-imaging workflow and needs a count with an overlay. **Inputs:** image plus physical-scale metadata and a defined inclusion rule. **Outputs:** count, masks, overlay, per-instance measurements and quality flags.

**Candidate pipeline:** preserve original → Cellpose prediction → numerical instance measurements → visual review → answer. An adaptive version adds a bounded crop/review step for ambiguous regions. A fixed version runs the same initial stages without LLM-directed retries.

**Reference answers:** expert-reviewed instance annotations and documented border rules. **Split:** reserve images from distinct slides or acquisition groups as appropriate. **Metrics:** count error, instance quality, measurement error when relevant, runtime and unsupported claims. **Failure examples:** merged cells, debris, wrong scale, missing metadata and unsupported image type.

**Decision rule:** keep the adaptive version only if it improves the chosen outcomes enough to justify its cost. Choose the acceptable tradeoff with the intended user before reviewing final test results. No invented numerical target is needed just to make the plan look precise.

### Write your version in the notebook below

1. Who will use the system, and what exact question will they ask?
2. What data exists, and what metadata must remain attached?
3. What is the simplest meaningful baseline?
4. Which one specialist capability is missing from that baseline?
5. What fields and artifacts must its output contain?
6. What inputs should be rejected or marked unsupported?
7. What is your held-out assessment and scoring procedure?
8. What latency, resource or licensing constraints matter?
9. When will the loop stop or ask for human review?
10. What finding would make you abandon or simplify the harness?

### A second example outside vision

For demand planning, the coordinator requests a forecast from a trained or pretrained forecasting worker. The worker returns time-indexed quantiles, assumptions and dataset/version references. The coordinator explains planning implications. It does not invent future sales figures from the prompt. The comparison is against relevant statistical and operational baselines, with a time-respecting split.

This second example tests whether your architecture handles different data contracts. It does not mean you need to build both examples at once.
''', question='What is the strongest sign your first scope is still too broad?', answer='You cannot write the expected input, output, reference answer and evaluation metric without using vague phrases such as “understand everything” or “analyze any scan.”')

add('faq', 'Questions you are likely to ask next', 'Short answers you can return to', 12, '''
### Does the LLM need retraining to use specialists?
Not necessarily. A capable model can use tools through descriptions, schemas and examples at inference time. Training may later improve selection or behavior, but first measure whether the unmodified coordinator can do the task.

### Can every specialist plug into one universal adapter?
A shared envelope helps with IDs, provenance and errors. The inner payload must remain task-specific. A forecast, a mask and a robot action do not become equivalent because all are serialized as JSON.

### Must all intermediate data become text?
No. Keep arrays and media as artifacts; provide supported image/audio inputs and compact structured data when useful. Text can reference data without replacing it. The coordinator only directly perceives modalities its model and interface support.

### Does a schema stop hallucinations?
It can prevent malformed output fields. It cannot guarantee correct predictions or reasoning. Verify factual and numerical claims against the stored evidence.

### Can a small specialist beat a huge general model?
On a narrow matched task, that is plausible. It is not a universal rule. Compare the chosen releases on the actual dataset, including preprocessing and end-to-end cost.

### Should every worker be an agent?
No. Most specialist inference is an ordinary computation. Another LLM loop adds decision overhead and should have a specific purpose.

### Is a failed tool call useful information?
Yes, about execution. It is not evidence that the scene contains nothing. Preserve distinct error states and avoid silently substituting an empty result.

### Can a model registry choose tools automatically?
It can filter by modality, license, task and resource availability. Selection quality still needs evaluation. Clear capability names and narrow presets can be more reliable than exposing hundreds of vague descriptions.

### Does the harness give a model permanent new knowledge?
The application may retain observations and retrieve them later. That is different from changing model weights. Neither automatically produces reliable continuous learning.

### Should I start by buying a workstation?
Start by defining and profiling one workload. Existing CPU resources may cover the coordinator client and classical operations. Rent accelerator capacity for the selected specialist when needed, then use measurements to inform a purchase.

### Is this AGI research or applied engineering?
It can inform research about active perception and tool use while producing useful engineering. Claims about AGI or subjective experience require arguments and evidence beyond improved task scores.

### What if the fixed pipeline wins?
Keep it. The LLM may be most useful for request interpretation and explaining evidence, while deterministic orchestration performs the known steps.
''')

GLOSSARY = '''
ASR|Automatic speech recognition: converting speech audio into text. It does not by itself establish who is speaking.
TTS|Text-to-speech: generating spoken audio from text. A generated waveform is not evidence about an observed recording.
VAD|Voice activity detection: finding intervals containing speech, usually before or alongside transcription.
Diarization|Dividing audio by anonymous speaker identity over time: who spoke when. It is not proof of a person's real-world identity.
Backbone|A reusable model component that extracts representations; a task-specific output head may be required to produce the desired prediction.
Head|A model component that maps features to a task output, such as classes or segmentation labels.
Covariate|An additional input variable used alongside the main measurements, such as a planned promotion in a demand forecast.
Quantile|A cutoff in a predicted or observed distribution. A 90th percentile forecast is a distribution statement, not a guarantee.
Dense vector|A representation stored with many numerical components, typically used for learned similarity matching.
Sparse representation|A representation with relatively few nonzero components, useful for certain retrieval or feature systems.
Hybrid retrieval|Combining different search signals, such as semantic vector similarity and lexical term matching.
Multi-vector retrieval|Representing one item with several vectors, for example page patches, and scoring against them. Storage and search must support that representation.
RAG|Retrieval-augmented generation: select relevant external evidence and provide it to a generating model. Retrieval quality and answer faithfulness are separate issues.
Neural network|A learned computation composed of connected operations with adjustable weights. It is a mathematical system, not a literal biological brain.
Deep learning|Machine learning using neural networks with multiple layers of learned transformations.
Machine learning|Methods that use data to fit patterns or decision rules rather than manually specifying every case.
Transformer|A neural architecture family using attention-based operations to process representations. Its existence does not determine which modalities or tasks a specific model supports.
Supervised learning|Training with examples paired with reference targets, such as images and object annotations.
Unsupervised learning|Learning patterns without target labels for the main task, such as grouping observations or fitting some anomaly detectors.
Zero-shot|Performing a specified task without task-specific training examples in the stated setup. The exact meaning depends on the evaluation protocol.
Open-vocabulary detection|Locating objects using a flexible set of text descriptions rather than only one fixed category list. It still has recognition limits.
Gradient boosting|A method that builds an ensemble of predictors sequentially to improve an objective; widely used for structured/tabular data.
Copyleft|Licensing terms that can require certain redistributed or combined work to retain specified freedoms and licensing obligations. The exact license and use determine requirements.
Checkpoint revision|An exact saved release or identifier for model weights, used to distinguish updates and reproduce a run.
Model card|Documentation accompanying a model release, including intended use, limitations and often evaluation and license information.
Function|A named software operation that accepts arguments and can return a result.
Dictionary|A mapping from keys to values in languages such as Python. It resembles a JSON object but follows the language's own rules.
Framework|A software structure that supplies common patterns and components for building applications or models.
Georeferenced|Associated with real-world geographic coordinates and a declared coordinate reference system.
Anomaly|An observation judged unusual under a fitted definition of normality. Unusual does not automatically mean fraudulent, defective or clinically significant.
Recommender|A system that ranks items for a user or context using information such as interactions or item features.
Source separation|Estimating component signals from a mixture, such as separating vocals and instruments. The intended source types matter.
Physical scale|The mapping between array samples and real-world units, such as micrometers per pixel. It must come from valid data/calibration.
Morphometry|Measuring shapes and sizes, such as cell area or anatomical region volume, under a defined method.
Affinities|In molecular contexts, measures related to binding strength. Model-predicted scores require task-specific interpretation and validation.
Adapter|Code that translates a common tool request into one specialist's input format and translates its output back. Example: turn an image ID into an array, run SAM, save masks.
AGI|Artificial general intelligence: a contested term for broadly general intellectual capability. Success on a few tool-assisted tasks is not evidence that it has been achieved.
Agent|A system that uses a model to select actions in a loop, receives observations and continues toward a task.
Agent loop|The repeated cycle of model request, proposed action, execution and returned observation.
API|Application programming interface: the agreed way another program requests work. It may be a local function or a network service.
Artifact|A saved input or result such as an image, mask, waveform, volume or table. An artifact ID points to the object; it is not the object itself.
Ablation|An experiment that removes or changes a component to assess its contribution.
Activation|An intermediate value produced during model computation. It can require working memory beyond the saved weights.
Attention|A family of mechanisms that combine information using learned input-dependent weights. The word does not imply human awareness.
Atlas|A reference representation or partition of anatomy used to label or align imaging data.
Batch size|The number of examples processed together in one computation. Larger batches may improve throughput while using more memory.
Baseline|A comparison system used to judge whether a more complex proposal adds value.
Benchmark|A defined collection of tasks plus a scoring procedure. Its relevance depends on whether it resembles your intended use.
BIDS|Brain Imaging Data Structure: conventions for organizing brain-imaging files and metadata.
BOLD|Blood-oxygen-level-dependent contrast, commonly used in fMRI. It is an indirect physiological signal associated with neural activity.
Bounding box|A rectangle enclosing a predicted object. State coordinate format, units and reference image.
Cache|Stored results reused to avoid repeated computation. Correct keys must distinguish inputs, model versions and settings.
Calibration|Checking whether reported probabilities match observed event frequencies on relevant data. Raw model scores may not be calibrated.
Capability|A defined operation the system can request, such as segment_cells or forecast_series, independent of one implementation.
Checkpoint|Saved trained weights at a particular revision or training stage. Different checkpoints can have different behavior and licenses.
Classification|Assigning a category to an input. It does not inherently locate objects.
Cold latency|Elapsed time when a worker must load or initialize before processing, under a stated measurement boundary.
Concurrency|Multiple jobs executing at the same time. It differs from batching examples together.
Confound|A factor that can influence a measurement besides the effect you are trying to study.
Container|A packaged software environment. It helps manage dependencies but does not supply compute hardware by itself.
Context window|The bounded amount of input a model can consider in one request. Application storage can be much larger.
Contour|A boundary curve around a region in an image. Its usefulness depends on the correctness of the region.
Coordinate frame|The reference system used to interpret positions: original pixels, crop pixels, world millimeters or an atlas, for example.
CPU|Central processing unit: general-purpose computing hardware.
Crop|A selected subregion of an image. Record its position and any resizing relative to the source.
CUDA|NVIDIA's GPU computing platform. Hardware and software compatibility affect whether a particular implementation runs.
DICOM|A standard for medical imaging data and associated information; not a synonym for MRI or fMRI.
Decoding model|In neuroscience, a model inferring stimuli or other variables from measured neural data. It is not automatically the reverse execution of an encoding model.
Depth map|An array representing estimated depth. Values may be relative or metric; the distinction must be declared.
Detection|Predicting where objects occur, usually with boxes, labels and scores.
Deterministic|Producing the same result from the same relevant inputs under the specified execution conditions. Hardware nondeterminism can complicate this in practice.
Domain shift|A change between training/validation inputs and deployment inputs, such as a new scanner, accent, lighting condition or product type.
Embedding|A learned numerical representation useful for operations such as similarity search. It is not generally a lossless copy of the input.
Encoder|A component that transforms input into a representation used by downstream computation.
Encoding model|In neuroscience, a model predicting neural responses from stimuli or stimulus features.
Event log|A sequence of recorded facts about execution, such as requests and completed results. It helps reconstruct what happened.
Feature|A derived property or representation used for a task, from a simple edge response to a learned neural vector.
Fine-tuning|Continuing training to adapt model weights to a domain or task.
fMRI|Functional magnetic resonance imaging: methods for studying changing signals associated with brain function, often using BOLD time series.
Fovea|The retinal region associated with the highest visual acuity. It motivates an analogy to selective high-resolution inspection.
GPU|Graphics processing unit: parallel hardware often used to accelerate neural computation.
Ground truth|A reference answer used for evaluation. It can contain annotation errors or ambiguity, so its construction matters.
Harness|Software around a model that manages tools, execution, context, state and interaction.
Held-out data|Examples reserved from tuning so they can assess generalization.
HTTP|A protocol commonly used for network request/response services. An inference worker can expose an HTTP API.
Idempotency|A property allowing repeated equivalent requests without duplicating the intended effect; often implemented with a request key.
Inference|Running a trained model on an input to obtain a prediction or generated output.
Instance segmentation|Assigning pixels to individual object instances, not merely categories.
IoU|Intersection over union: area of overlap divided by area of union for two regions. It ranges from zero to one.
JSON|A text format for structured objects, arrays and scalar values. A JSON document is not automatically valid for your task schema.
KV cache|Stored attention keys and values used to avoid recomputing earlier positions in some autoregressive models. It consumes memory as context grows.
Latency|Elapsed time for a request under a specified boundary, such as model-only or end-to-end.
LLM|Large language model. Some models also process images, audio or other modalities; inspect the specific interface.
Mask|An array marking selected pixels or voxels, often with a binary value, class ID or instance ID.
MCP|Model Context Protocol: an interface for exposing tools/resources to compatible clients. It is not a model-hosting engine.
Metadata|Information describing data, such as acquisition time, pixel size, orientation or source identity.
Modality|A kind of input or output, such as text, image, audio, video, volumetric imaging or time series.
Multimodal|Using multiple modalities. Capabilities depend on the specific model and transport, not just the label.
NIfTI|A common neuroimaging file format that stores array data with spatial information.
OCR|Optical character recognition: extracting text from images, often with its location.
Offloading|Moving some model data or work away from the GPU, often to host RAM/CPU, to reduce GPU memory demand at a possible speed cost.
Open weights|Model weights are available under stated terms. This does not necessarily mean unrestricted commercial use or a fully open training process.
Parameter|A learned numerical model setting, also called a weight. Parameter count alone does not determine runtime quality or memory use.
Pipeline|A sequence of processing steps with defined dependencies.
Pixel|A sample in a 2D image grid. A pixel can contain multiple color-channel values.
Precision|In detection metrics: correct positive predictions divided by all positive predictions. In numerical computing: the format used to represent numbers; these meanings differ.
Preprocessing|Transformations applied before inference, such as normalization, resizing or modality-specific preparation.
Prompt|Input instructions and context supplied to a model for a request.
Provenance|The recorded origin and transformation history of data and claims: source, method, version and settings.
Quantization|Using reduced numerical precision or compressed value representations to reduce model storage/compute demand; quality and runtime support must be checked.
Queue|A waiting list of jobs that cannot all execute immediately.
RAM|System working memory used by running programs and data. It is different from persistent disk storage and GPU VRAM.
Recall|Correctly found target objects divided by all reference target objects.
Registration|Estimating an alignment between coordinate spaces, often used in medical or multiview imaging.
Reranker|A model that reorders an already-retrieved shortlist according to relevance to a query.
Resampling|Computing values on a new spatial or temporal grid. It changes representation and requires preserved transforms.
ROI|Region of interest: an area or volume selected for analysis.
Router|Logic that chooses an implementation or worker for a requested capability.
Saccade|A rapid gaze movement that brings a different part of a scene toward detailed inspection.
Scheduler|Software that assigns pending jobs to available compute resources.
Schema|A declared structure and constraints for inputs or outputs. Structural validity is not proof of factual correctness.
Segmentation|Dividing an image or volume into meaningful regions; specify semantic versus instance output.
Semantic segmentation|Assigning each pixel/voxel a category, without necessarily distinguishing separate instances of the category.
Session|The application's record and state for an ongoing interaction or analysis.
Tensor|A multi-axis array of numbers. Shape and axis order must be explicit.
Throughput|Work completed per unit time, such as images per second. High throughput does not necessarily mean low single-request latency.
Token|A model input/output unit. Text tokens are often word pieces; multimodal representations and accounting vary by model.
Tool|A callable operation available to the coordinator; it may use ordinary code, a specialist model or another service.
Tracking|Associating observations over time so the same object can retain an identity or trajectory.
Training|Adjusting model weights using data and an objective.
TR|Repetition time: acquisition timing terminology in MRI; interpret it within the relevant sequence and dataset metadata.
VLM|Vision-language model: a model designed to connect visual and language information.
Voxel|A sample in a 3D volume. Physical size and orientation determine how it maps to space.
VRAM|GPU working memory. Loaded weights, activations and buffers share it.
Warm latency|Elapsed time when the relevant model/worker is already initialized, under a stated measurement boundary.
Worker|A running process or service that performs a computation, such as loading and executing a specialist model.
'''
glossary = dict(line.split('|',1) for line in GLOSSARY.strip().splitlines())
glossary_html = '<p>These definitions are intentionally short. Click a concept in any lesson for the same explanation. Use the search box to find a term and the lessons that use it.</p><div class="glossary-list">' + ''.join(f'<article id="term-{html.escape(k.lower().replace(" ","-"))}"><h3>{html.escape(k)}</h3><p>{html.escape(v)}</p></article>' for k,v in sorted(glossary.items(),key=lambda x:x[0].lower())) + '</div>'
pages.append(dict(id='glossary',title='Plain-language glossary',deck=f'{len(glossary)} concepts · a reference, not a memorization test',minutes=15,body=glossary_html,visual='',question='',answer='',essential=True))

add('sources', 'Sources and a sensible reading order', 'Read selectively; follow the question you are trying to answer', 10, '''
### First: practical architecture

- [DeepSeek Harness architecture](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md): find boundaries between providers, tools and state.
- [DeepSeek tool authoring](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cookbook/adding-a-tool.md): follow data from executor to model-facing result.
- [smolagents documentation](https://huggingface.co/docs/smolagents/index): understand a small agent loop and tool implementation.
- [Harbor](https://github.com/harbor-framework/harbor): understand how complete agents can be evaluated.

### Second: research that motivates experiments

- [ViperGPT (2023)](https://arxiv.org/abs/2303.08128): programmatically compose visual modules. Ask what the modules assume and how errors propagate.
- [BLINK (2024)](https://arxiv.org/abs/2404.12390): distinguish different perception tasks. Ask which resemble your intended workload.
- [Visual Sketchpad (2024)](https://arxiv.org/abs/2406.09403): visual intermediate artifacts and tool use. Ask whether gains transfer to the model you plan to use.

### Third: perception and neuroimaging

- [Zirnsak et al. (2014)](https://www.nature.com/articles/nature13149): eye movements and visual representations.
- [Balas, Nakano & Rosenholtz (2009)](https://pmc.ncbi.nlm.nih.gov/articles/PMC2923917/): peripheral crowding and summary representations.
- [Martinez-Conde et al. (2004)](https://www.nature.com/articles/nrn1348): fixational eye movements. A review, with unresolved mechanisms distinguished from findings.
- [Logothetis et al. (2001)](https://www.nature.com/articles/35084005): physiological basis of fMRI signals.
- [Logothetis (2008)](https://www.nature.com/articles/nature06976): capabilities and limits of fMRI interpretation.
- [BIDS](https://bids.neuroimaging.io/) and [fMRIPrep workflows](https://fmriprep.org/en/stable/workflows.html): the data conventions and processing surrounding models.
- [TRIBE v2 model card](https://huggingface.co/facebook/tribev2): verify input/output direction and component/license requirements.

Each catalog entry links its primary repository or official model card. Follow those for the exact checkpoint and current installation instructions. Some publisher pages or full papers may require access; this guide does not depend on them to display its lessons.

### How to read a paper without getting lost

Read the question, input/output definition, comparison systems, dataset and limitations before the architecture equations. Write one sentence stating what was actually demonstrated. Then write one sentence stating what was not tested. Check whether the evaluation is on an old coordinator model, whether tool errors are analyzed and whether extra compute is controlled.

### Research boundaries

No model was installed or benchmarked for this guide. Model availability and licenses can change; the catalog is a dated research snapshot. Analogies to human perception are proposed engineering inspirations. All toy diagrams and numeric examples are original explanatory illustrations, not measured outputs or clinical findings.
''')

add('ready', 'You are ready to design when…', 'Use this as a self-check before writing code', 8, '''
Try answering these without reopening earlier pages. Then use the answer below to assess your readiness.

1. Explain why OpenCV, a SAM checkpoint and a harness are different things.
2. Draw a complete request with a worker, adapter, artifact store and returned observation.
3. State what happens to a large mask and what the LLM sees instead.
4. Explain why valid JSON does not guarantee a correct prediction.
5. Convert a crop coordinate into an original-image coordinate.
6. Explain why parameter count alone cannot determine your GPU purchase.
7. Distinguish a DICOM file, an MRI volume and an fMRI time series.
8. Draw TRIBE's input/output direction correctly.
9. Name the four comparison systems in your evaluation.
10. State what evidence would make you remove an unnecessary model or agent loop.

### Suggested next milestone

Complete your project brief, select one task and inspect a few representative inputs with their metadata. Read the relevant adapter interface in one harness. You are then ready to implement one observable end-to-end path and assess it.

You do not need to memorize every model in the catalog or understand every neural architecture. You need to know what each chosen component promises, how to verify that promise, and how its evidence reaches the final answer.
''', question='What does a satisfactory answer to these questions have in common?', answer='It names concrete data, ownership and checks. It separates predictions from measurements, runtime from inference, and evidence of one task improvement from claims of general intelligence.')

# Inline definitions: annotate only the first suitable mention per page, leaving links/code alone.
terms = sorted(glossary, key=len, reverse=True)
term_regex = re.compile(r'(?<![\w-])('+'|'.join(re.escape(t) for t in terms)+r')(?![\w-])',re.I)
canonical = {t.lower():t for t in glossary}
for p in pages:
    if p['id']=='glossary': continue
    soup=BeautifulSoup(p['body'],'html.parser'); used=set()
    for node in list(soup.find_all(string=True)):
        if any(x.name in ['a','code','pre','button','h1','h2','h3','h4','script'] for x in node.parents): continue
        text=str(node); pieces=[]; last=0
        for match in term_regex.finditer(text):
            key=canonical[match.group().lower()]
            if key in used: continue
            pieces.append(text[last:match.start()]); b=soup.new_tag('button',attrs={'type':'button','class':'term','data-term':key}); b.string=match.group(); pieces.append(b); last=match.end(); used.add(key)
        if pieces:
            pieces.append(text[last:]); node.replace_with(*pieces)
    for table in list(soup.find_all('table')):
        wrap=soup.new_tag('div',attrs={'class':'table-wrap'}); table.wrap(wrap)
    for a in soup.find_all('a',href=True):
        if a['href'].startswith('https://'): a['target']='_blank'; a['rel']='noopener noreferrer'
    p['body']=str(soup)

data=json.dumps({'pages':pages,'glossary':glossary},ensure_ascii=False).replace('</','<\\/')
template=(ROOT/'study_template.html').read_text()
out=ROOT.parent/'vision-harness-study-guide.html'
out.write_text(template.replace('/*__STUDY_DATA__*/',data))
print(f'Wrote {out}: {len(pages)} pages, {len(glossary)} glossary terms, {out.stat().st_size:,} bytes')
