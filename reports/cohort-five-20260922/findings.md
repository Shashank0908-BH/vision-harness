# Findings for tomorrow's review

On these five examples, vanilla Astra is the most efficient tested setup: it answered all five correctly and averaged 6.4 seconds. The full harness also answered all five correctly but averaged 25.3 seconds. This is evidence of overhead on this cohort, not evidence that tools can never help.

## What was tested

The five preselected test-split examples cover separated-circle counting, color-filtered counting, relative position, pixel distance, and touching circles. Each ran once in each of five modes. Model IDs, prompts, thresholds and grading were fixed throughout the final comparison. This small synthetic set turned out to be easy for vanilla Astra; it cannot establish performance on complex real-world images or medicine.

## The useful failure

The review-only mode initially answered the touching-circle question correctly: **10**. Jev returned a support probability of **0.71**, below the configured **0.75** review threshold. The runtime requested another plan, but that request failed to produce parseable structured JSON. The final trial therefore counts as an error, leaving review-only at **4/5**.

This illustrates a concrete failure path: a reviewer can reject a correct answer and introduce a new opportunity for failure. The observation does not isolate whether a different review threshold, better evidence presentation, or stronger retry handling would help; those would require a separately configured experiment.

One failed planner response did not have its token usage recorded because parsing raised before response logging. The report retains its started-call event and marks token totals as potentially incomplete. The exact unrecorded usage is unknown; do not treat the displayed tokens as the full invoice.

## A harness bug fixed before the final comparison

The initial five-trial baseline batch rejected legitimate citations to `original`, the supplied image. This was an application validation bug, not a vision failure. We preserved that batch, fixed image citations for every mode, and restarted the entire comparison. No tasks, expected answers, model settings, prompts or thresholds were changed to improve the scores. Both runs and the correction are documented in `protocol.json`.

## What to examine next

1. Inspect the failed review trace and the correct answer that preceded it.
2. Decide when a reviewer should request additional work instead of accepting an answer already supported by evidence.
3. For a future experiment, preselect harder, more varied images before looking at model outcomes. Do not tighten this cohort's grading after seeing its answers.
4. Compare against a fixed OpenCV pipeline as well as vanilla Astra, to establish whether LLM planning adds value to tasks that already have deterministic solutions.

Open `index.html` for images, all 25 answers, Jev scores, decisions and trace links. `results.json` contains the machine-readable comparison. The full Harbor viewer command is:

```bash
uv run harbor view jobs/cohort-five-20260922-v2
```
