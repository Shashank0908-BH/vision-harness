# Structured review loop — BBBC001 retest

## Outcome

Vanilla returned six counts with **11.64% mean counting error**. The full loop returned **no accepted counts**: three abstentions and three Astra timeouts. Its first numerical proposals had **14.09%** error; last numerical proposals had **14.56%** error. Mean runtime increased from **93.9 s** for vanilla to **326.1 s** for the loop. See [final score](final-score.md) and [all candidate counts](candidate-counts.md).

The earlier single-run baseline values of 14.08% and 10.30% remain separate experiments. We do not combine them to declare a stable winner. This run compares only vanilla and the structured loop, not a fresh evaluation of tools-only or selection-only variants.

## What changed and what stayed fixed

The loop adds method-validity, coverage, target-validity and answer-grounding questions to the existing overall support review. A single Jev call returns all five Noul values. The controller derives failed-check IDs and fixed remediation hints from those results; hints are authored rubric text, not Jev-generated explanations. Previous plans, selections, candidate answers, measured evidence and review scores go to both the next planner and selector.

Effective duplicate operations are reused, and fully repeated plans can be excluded. A round producing no new measurement/artifact observations stops before another answer/review. The experiment permits four rounds, up to 24 provider calls including format retries, and a 600-second admission deadline for new work. All five review propositions must meet 0.75. Per-call timeout remains 120 seconds, with at most one format retry. The Jev payload budget is 48,000 serialized bytes for the larger history.

OpenCV's segmentation, the original task text and images, the Astra model/effort and base prompt, and the numerical threshold were not changed. Adding four mandatory checks nevertheless makes the gate stricter. This experiment jointly changes feedback, acceptance checks, retry budget and repeat detection; it does not isolate their separate causal contributions.

## Evidence the feedback loop executed

All six full trials reached Jev method selection and at least one structured review. Eight reviews returned all four checks plus overall support. Each successful later-round Jev selection received the previous round history and failed review checks. Six repeated tool operations were reused rather than executed again.

- Field 4 stopped after its second selection: only one plan remained viable with low confidence, so the existing selection policy would not execute it alone.
- Field 5 completed three planning rounds, proposed 570 twice, then Astra abstained because added crops did not establish independently measured enumeration.
- Field 3 replanned and obtained 373 and 314 segmented regions under different thresholds. Astra then abstained because merged/dim nuclei and target identification remained unresolved.
- Field 1 reached a third round, but its answer-format recovery timed out. Earlier proposals of 390 and 400 are preserved.
- Fields 2 and 6 timed out during second-round planning-format recovery, after initial proposals of 390 and 270 respectively.

No live run ended through the no-new-observation, total-call or total-time stopping rules; those branches are exercised by local tests. Operation reuse and low-confidence selection stopping did occur live. The loop did not manufacture confidence or relax acceptance to obtain a final count.

## Why this did not establish a gain

All eight overall review scores were below threshold (0.06–0.11); every per-check score was also below 0.75. The initial segmentation mismatch persisted: the existing `color="any"` rule can select the whole fluorescence image, and visual estimates or crop descriptions do not provide independent numerical evidence to a text-state reviewer. Replanning produced a concrete segmentation change on field 3, but failed to substantiate a reliable cell count.

Three Astra calls timed out at the configured 120-second per-call timeout after an initial output-token-limited response triggered the allowed 8192-token recovery attempt. Two were planning calls and one was answering. These are execution failures, distinct from review rejection. Jev returned successfully on all 20 of its calls; this run did not exercise evidence compaction. The 58 started calls across both modes have 55 recorded responses. Costs and full usage for the three timed-out calls are unknown, not zero.

The observed candidate-count errors are worse than the same-run vanilla baseline. But half the full trajectories were interrupted, so this is not a clean estimate of how six fully completed loops would perform. Repeating inference to replace failures would create a separate recovery experiment, not overwrite this frozen comparison.

## Reproduction and scope

The exact source commit, runtime hashes, image hashes, budgets and candidate-scoring policy were frozen before inference in [protocol.json](protocol.json). No inference code or thresholds changed during the run. All original images and published human annotations were reused unchanged; labels stayed outside agent environments.

This is a six-image retest after prior inspection and debugging. Human counts disagree; their mean is the reference. It is not a new held-out evaluation, a clinical validation, a compute-matched comparison, or a stable ranking across all harness variants.

Implementation and commands: [review-loop guide](../../docs/review-loop.md). Jev's multiple typed questions over structured state follow the [TypeSafe API reference](https://docs.typesafe.ai/api).

Source images and annotations: [BBBC001v1](https://bbbc.broadinstitute.org/BBBC001), David Root and Anne Carpenter, [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/).
