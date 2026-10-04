# Tools and Jev selection — fresh BBBC001 retest

## Result

The requested two configurations were run alongside a fresh vanilla baseline, using all six original BBBC001v1 microscopy images and their published human counts. All **18 trials returned a numerical final answer**, with zero abstentions or execution errors.

Mean counting error: **17.34% vanilla**, **16.16% Astra + OpenCV**, **14.27% Astra + OpenCV + Jev selection**. Lower is better. Selection leads this one experiment by **3.07 percentage points** over vanilla and **1.89 points** over tools alone. See [final scorecard](final-score.md) and [per-image predictions](README.md).

Mean runtime was 100.3 s, 95.1 s and 107.6 s respectively. Vanilla required one successful output-format recovery after token exhaustion; neither tool mode needed a format retry. All 37 started provider calls have recorded responses and usage. Runtime is observed end-to-end harness time excluding container setup; it is not a stable latency ranking.

## What ran

- Vanilla: Astra answers the original image directly.
- Tools: Astra proposes plans and chooses its preferred eligible plan, OpenCV executes, then Astra answers.
- Selection: Astra proposes plans, Jev scores them, Python chooses eligible plans under the existing policy, OpenCV executes, then Astra answers.

There were **no Jev answer-review calls**, no `answer_review` events, and no structured-loop controller. Tools mode made no Jev calls at all. Selection made one plan-assessment call per image. Every mode used `configs/poc.toml`, the same model/effort, 4096 initial output tokens, 120-second per-call timeout and the existing bounded format-retry policy. No perception implementation, rubric or threshold changed during this run.

## The average does not mean improvement on every image

Both tool modes are closer to the reference on fields 4 and 6, and worse on fields 1, 2, 3 and 5. The aggregate advantage is driven primarily by field 4: vanilla 460, tools 370, selection 365, against a reference mean of 330.5. Selection versus tools is better on fields 2, 4 and 5, worse on field 6, and tied on fields 1 and 3.

This is why the lowest average should be reported as an observed result of this cohort, not proof of a consistently superior configuration. Previous vanilla experiments produced different counts and errors. The original three-mode scores of 14.08%, 12.78% and 11.36% remain a separate earlier experiment, not interchangeable baselines or replacements for these results.

## What the tool evidence actually shows

Every component or watershed output in these 12 tool-mode trials reported **one component** covering either the whole image or about **99.2%** of it. The current `color="any"` foreground rule is poorly matched to bright nuclei on a dark grayscale background, and `saturation_min=0` can select every pixel. Its `value_min` parameter is ignored in that branch.

All 12 final tool-mode answers describe visual estimation/counting. They do not report independently measured cell totals from the masks. Additional tool state, images and inference can change the model's estimate, but these traces do not establish an OpenCV perception gain or isolate a causal benefit from Jev's scores. The remaining concrete perception issue is the foreground-segmentation contract and its applicability to this input type.

## Integrity and limits

The runtime, effective settings and six image hashes were frozen before live inference in [protocol.json](protocol.json). Every attempt is retained. There were no replacement trials, threshold changes or synthetic benchmark problems. Ground-truth annotations stayed in the verifier/report, outside the agent image.

This is a one-attempt retest of previously inspected images from one small experiment. Human annotations disagree, so the official reference is their mean. The comparison uses different amounts of inference and independent plans. It cannot establish general multimodal performance, calibration, or a stable overall ranking.

Source: [BBBC001v1](https://bbbc.broadinstitute.org/BBBC001), images and ground truth by David Root and Anne Carpenter, [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/).
