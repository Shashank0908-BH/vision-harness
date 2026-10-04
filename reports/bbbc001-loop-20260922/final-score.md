# Structured-loop experiment: final score

The new loop is implemented and was run on all six published BBBC001v1 images. Both Jev stages were enabled; prior failed checks reached Astra planning and Jev selection.

| Output | Numerical counts | Mean counting error ↓ |
|---|---:|---:|
| Vanilla final answers | 6/6 | **11.64%** |
| Loop's first numerical proposals | 6/6 | **14.09%** |
| Loop's last numerical proposals | 6/6 | **14.56%** |
| Loop's accepted final answers | 0/6 | Undefined: no accepted counts |

Full-harness outcomes: **three abstentions and three Astra API timeouts**. Mean runtime was **326.1 s** per image, versus **93.9 s** for vanilla. All errors and partial traces remain included. Three timed-out calls have no response or usage receipt; token totals are incomplete for those calls.

The candidate rows are retrospective diagnostics, not accepted output. Each image contributes its first or last numerical proposal uniformly; we did not choose whichever round scored best. The last proposals were worse than vanilla on all six images. Four images had only one numerical proposal, and two had two; this is not six completed four-round trajectories. No inference was repeated to replace failures.

The experiment shows that the feedback loop executes and changes subsequent choices, but it does **not** demonstrate an accuracy gain. Three interrupted trials also limit conclusions about completed-loop performance. This is one attempt on six previously inspected images, not a stable ranking of all earlier harness configurations.

[Interactive report and traces](index.html) · [Per-round counts](candidate-counts.md) · [Failure analysis](findings.md) · [Loop design and CLI](../../docs/review-loop.md)
