# Full harness — final real-microscopy result

The requested follow-up [scores the rejected candidate counts](candidate-counts.md): last proposals have **14.49%** mean counting error; first proposals have **13.71%**, versus **10.30%** for vanilla. These diagnostic scores do not change the recorded abstentions below.

The complete harness was run with **both Jev method selection and Jev answer review enabled**. The separate review-only ablation was skipped.

| Configuration | Final numerical counts | Mean counting error ↓ | Abstentions | Execution errors | Mean runtime |
|---|---:|---:|---:|---:|---:|
| Vanilla Astra | 6/6 | 10.30% | 0 | 0 | 76.5 s |
| Full harness | 0/6 | Undefined: no final counts | 6 | 0 | 234.4 s |

**The full harness did not improve task performance in this test.** All six trials executed, but none produced an accepted count. Completion is 0%; this is not a claim of “0% counting accuracy.” The published error metric requires numerical predictions, so no full-harness percentage error can be computed. Rejected candidate estimates are retained in traces and are not substituted for final answers.

The current OpenCV foreground rule is poorly matched to grayscale fluorescence. Astra falls back to visual estimates or attempts revised segmentation, while Jev's structured-evidence review rejects the remaining uncertainty. Jev receives JSON evidence, not image pixels, and the review rubric requires independent support for image interpretations. This result therefore includes the effects of both the tool mismatch and the acceptance policy.

These are all six original BBBC001v1 images, with unchanged published human counts; no invented tasks or labels. This was one paired retest after integration repairs on previously inspected images, not fresh held-out evidence about all multimodal tasks. The earlier “5/5, 25.3 s” result was a synthetic smoke test, and the earlier 11.36% result was selection-only mode.

[Interactive report and all trials](index.html) · [Failure analysis](findings.md) · [Machine-readable score](final-score.json) · [Frozen protocol](protocol.json)

Open Harbor traces locally:

```sh
uv run harbor view jobs/bbbc001-full-repaired-20260922
```
