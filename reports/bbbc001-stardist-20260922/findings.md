# StarDist inside the complete harness

StarDist improves measured counts on this cohort. Astra + StarDist matches the standalone counts; full-chain Jev review rejects all six. No accepted-output improvement from the full chain is established.

Mean absolute percentage count error against the mean of two published human counts; lower is better. Six real BBBC001 images, not invented problems. Coverage counts returned estimates, not exact answers.

| Primary experiment | Final counts | Full-cohort error | Abstentions | Execution errors | Mean time |
|---|---:|---:|---:|---:|---:|
| Vanilla Astra | 5/6 | Incomplete | 0 | 1 | 90.7 s |
| Astra + StarDist | 6/6 | 6.67% | 0 | 0 | 33.2 s |
| Full harness: Astra + StarDist + Jev selection/review loop | 0/6 | Incomplete | 6 | 0 | 114.0 s |

Vanilla's primary answered-subset error is 17.64% on five images; it is not a full-cohort score. Its sixth request timed out at 120 seconds. This is an Astra execution error, not a Jev rejection.

## Separately recorded timeout recovery

Recovered/composite vanilla: five primary answers plus one separately retried timeout: **6/6 counts, 18.20% error**. The retry uses a 300-second per-call timeout; other inference settings and all input/source files are unchanged. The primary timeout remains in its original trial. See [policy](recovery-policy.json), [retry config](recovery-evaluation.toml) and [exact results](final-score.json).

Astra + StarDist has 63.4% lower error than this recovered/composite baseline, and is closer on 6 of six images. This comparison includes a recovery attempt and must not be presented as six successful first attempts.

## Every count

| Image | Humans | Reference | Primary vanilla | Vanilla incl. recovery | StarDist / Astra + StarDist | Full-chain first / last numerical candidate | Full final |
|---|---|---:|---:|---:|---:|---:|---|
| BBBC001 field 1 | [350, 362] | 356.0 | 490.0 | 490.0 | 375 | 375 / 375 | abstained |
| BBBC001 field 2 | [336, 342] | 339.0 | 391.0 | 391.0 | 354 | 354 / 354 | abstained |
| BBBC001 field 3 | [396, 447] | 421.5 | Timeout | 510.0 (retry) | 456 | 456 / 456 | abstained |
| BBBC001 field 4 | [320, 341] | 330.5 | 362.0 | 362.0 | 349 | 349 / 349 | abstained |
| BBBC001 field 5 | [398, 533] | 465.5 | 544.0 | 544.0 | 529 | 529 / 529 | abstained |
| BBBC001 field 6 | [241, 257] | 249.0 | 271.0 | 271.0 | 256 | 256 / 256 | abstained |

## Why full mode still abstains

All six first and last numerical candidates have 6.67% mean error, identical to standalone StarDist and the tools-only arm. These are diagnostic proposals, not accepted outputs. Replanning produced no revised numerical estimate.

Jev's overall answer-support scores were 0.80–0.87. Method-validity checks scored 0.19–0.32 and target-validity checks 0.33–0.46. Every requirement must reach 0.75; therefore all six candidates failed review. Overall support is not the acceptance rule and none of these scores is calibrated count accuracy.

All six trials passed failed checks back into Astra planning and Jev selection. Five trials then returned an Astra abstention after additional auditing; one stopped because Jev selected no eligible new plan. No full-mode request timed out. Five cropped StarDist maps were added across four trials; additional views did not establish independent biological validation. The available specialist and crops cannot guarantee one instance per true cell.

This points to a mismatch between an estimated-count task and a policy requiring independent validation before returning any estimate. It does not establish that Jev as a model is inherently harmful. A future policy experiment should distinguish 'measured estimate with unresolved caveats' from 'verified count', and calibrate acceptance on held-out data. Do not tune this run's threshold after looking at its answers.

## What improved and what did not

The perception layer now returns real nucleus instance masks and derives counts from distinct positive IDs. This is a substantive improvement over the previous OpenCV run's unusable whole-image components and visual fallback. The previous OpenCV scores are historical, not fresh paired controls: 16.16% tools-only and 14.27% selection-only, versus this run's 6.67% StarDist tools-only result.

The harness did not improve on standalone StarDist's 6.67% error. It added orchestration, evidence provenance and inspectable traces. Its full review policy reduced final-answer coverage to zero. The next useful evaluation is on new annotated images with a predeclared policy and specialist selection; repeated measurements on these six development images cannot establish generalization.

## Review files and limits

- [Interactive report](index.html): primary outcomes, recovery summary, images and traces.
- [Candidate counts](candidate-counts.md): proposals before review, without substituting them for final answers.
- [Verification](verification.json): trajectory, source, input, checkpoint, geometry, feedback and credential checks.
- [Preflight](preflight-verification.json): 42 tests plus exact native/container mask agreement for all six defaults.
- [Integration file map](../../docs/stardist-harness.md): what each adapter/configuration file does.
- [Frozen protocol](protocol.json): all settings, hashes, attribution and limitations.

Six previously inspected images, one primary attempt per mode, uncertain pretraining overlap, disagreeing human annotations, and no instance-level ground truth limit conclusions. All three modes share the frozen Astra system instructions, including StarDist guidance. Vanilla receives only the original image and an empty evidence list; it has no specialist or Jev calls. This is an API ablation under the common harness prompt, not a measurement of the default ChatGPT product. Threshold variants are correlated predictions from one model. Runtime excludes container setup; token usage for the timed-out request is unknown. Local masks and Harbor jobs are retained on this machine; raw job traces are Git-ignored.

Reproduce report-only calculations from the repository root:

```bash
.venv/bin/python -m evals.benchmark_report reports/bbbc001-stardist-20260922 jobs/bbbc001-stardist-20260922
.venv/bin/python -m evals.candidate_report reports/bbbc001-stardist-20260922
.venv/bin/python reports/bbbc001-stardist-20260922/summarize.py
.venv/bin/python reports/bbbc001-stardist-20260922/audit.py
```
