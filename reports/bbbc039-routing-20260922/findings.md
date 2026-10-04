# Routing v1: working infrastructure, mixed empirical result

The new modular harness completed all six additional BBBC039 tasks. The best fixed
specialist, Cellpose-SAM, produced 4.23% mean absolute percentage count error.
Fresh vanilla Astra produced 5.44%. The final routed harness produced 5.71%.
This test supports further use of specialist models, but does not establish that
this router improves on vanilla or the best fixed specialist.

## What was built and exercised

A versioned catalog exposed four complete procedures: three StarDist thresholds
on the same `2D_versatile_fluo` weights, and one Cellpose-SAM `cpsam_v2` procedure.
Astra interpreted the task, described every eligible procedure and selected a
preference. Jev scored all four before execution. The highest Score won, with a
predeclared ID-based tie rule. All scores and the decision were saved before any
specialist output existed. The two model families ran in separate environments.

The selected procedure produced a full-frame instance map; Python derived the
count and geometry. Astra saw the original and selected overlay, and returned the
same count. Jev reviewed the structured evidence. Only then were the remaining
procedures executed for comparison. Benchmark annotations were decoded after all
six routed and vanilla inference sequences completed.

The separate live research run used web search, extracted four sourced proposals,
and scored every proposal with Jev. It proposed StarDist, Cellpose-SAM, InstanSeg
and microSAM. The latter two are advisory proposals, not installed adapters.
Research Score ranks integration relevance, not expected counting accuracy.
Source URLs are verified against the actual search trace; all individual source
claims and license interpretations still require review. See
[the saved research output](../model-research-20260922/result.json).

## Exact counts

| Image ID | Reference | Vanilla | StarDist default | Sensitive | Conservative | Cellpose-SAM | Selected/final |
|---|---:|---:|---:|---:|---:|---:|---|
| b3af822f7e1a | 137 | 130 | 128 | 130 | 124 | 131 | default: 128 |
| fc4388dbac57 | 115 | 107 | 107 | 109 | 106 | 110 | default: 107 |
| f4b8ef595d67 | 50 | 44 | 45 | 45 | 45 | 48 | Cellpose: 48 |
| 17a175b5e17d | 156 | 150 | 144 | 146 | 141 | 147 | default: 144 |
| 54ee1bf8ac02 | 93 | 90 | 86 | 89 | 86 | 88 | default: 86 |
| c938cd18d93d | 66 | 65 | 63 | 65 | 61 | 67 | Cellpose: 67 |

All six final results are **caution estimates**, not Jev-approved answers. Review
support ranged from 0.64 to 0.71, below 0.75. There were no API failures,
abstentions, or execution failures. The policy now preserves measurable estimates
with their uncertainty flags; the historical full harness required approval before
returning a number. This change explains the improved completion rate. It does not
show that the old approval/replanning loop has been fixed.

Astra preferred default StarDist on all six images. Jev chose it on four, switching
to Cellpose on two. Those switches reduced mean error from 7.22% for Astra's
preferred measurements to 5.71%. But a uniform Cellpose policy was better at 4.23%.
Jev matched a best procedure on 2/6 images, including ties. Average error regret
against a label-informed per-image oracle was 1.66 percentage points. The oracle
would score approximately 4.05%; it is a diagnostic upper bound, not an available
runtime policy. The best fixed procedure is identified after evaluation and must
itself be tested on another frozen cohort before becoming a general default.

The harness beat vanilla on one image, tied on two and was worse on three.
Cellpose beat vanilla on three, tied on one and was worse on two. These six examples
are too few to establish a stable overall ranking, but they clearly show why model
availability and routing quality must be evaluated separately.

## Timing and verification

Mean input-to-final-answer time was 55.6 seconds for routing, excluding the later
comparison runs, versus 35.7 seconds total for vanilla. This small timing difference
in measurement boundaries should be kept in mind. Specialist process time included
startup, inference and artifact creation: approximately 6.62 seconds for Cellpose
and 2.24–3.04 seconds for the StarDist procedures. Native inference alone averaged
3.09 seconds for Cellpose and 0.37–0.42 seconds for StarDist. A persistent model
server is a plausible later optimization, not part of this result.

- All 24 instance maps and 2,311 instance geometry records were recomputed.
- All 12 Harbor ATIF traces validated; all 36 benchmark provider calls completed.
- All decisions preceded tool execution; comparison outputs followed the final answer.
- Source/catalog hashes matched the frozen protocol throughout inference.
- Independent Pillow/scikit-image decoding matched all six annotation reference counts.
- 57 automated tests passed, including timeout-versus-rejection, missing candidates,
  unsupported modalities, credential isolation, corrupt weights and count grounding.
- The offline HTML report passed pagination/image/link checks at 1440, 768, 390 and
  320 px widths, with no JavaScript errors or document overflow.

Execution used native specialist processes on the current Mac and hosted Astra/Jev
APIs. Harbor supplied trace export/validation; this was not a Harbor Docker job.
Jev saw structured evidence, not image pixels. The current registry only supports
2D replicated-grayscale fluorescence nucleus counting. It is not a general medical
image or fMRI interpreter.

## What the next experiment should change

Keep the modular model adapters and structured evidence. Evaluate routing on a
larger, separate development cohort with per-image quality features and measured
model performance as inputs. Then freeze that selection policy and compare it on
an untouched cohort against vanilla and each fixed specialist. Jev can remain an
experimental ranker/condition checker; its scores should earn their role through
measured routing gains rather than being treated as correctness probabilities.

Add InstanSeg or microSAM only after a checkpoint, license, adapter and resource
requirements are verified. New model names alone are not a solution to the current
selection error. Include segmentation precision/recall and mask quality alongside
counts so that coincidentally correct totals do not hide incorrect instance maps.
