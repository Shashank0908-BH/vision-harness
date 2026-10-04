# Selection-only ablation — not the full harness

This result excludes answer review and is an ablation, not the user-requested full-harness result. The full comparison is recorded separately under `reports/bbbc001-full-repaired-20260922/`.

This configuration is **Astra + OpenCV + Jev plan selection** (`--mode select`). It answered all six published BBBC001v1 images and scored **11.36% mean counting error**. Lower is better; this is not classification accuracy.

| Configuration | Mean counting error ↓ | Images answered | Mean time |
|---|---:|---:|---:|
| Vanilla Astra | 14.08% | 6/6 | 67.0 s |
| Astra + OpenCV | 12.78% | 6/6 | 82.1 s |
| **Harness: Astra + OpenCV + Jev selection** | **11.36%** | **6/6** | 85.3 s |

Observed improvement versus vanilla: **2.72 percentage points**, or **19.3% lower counting error**. The harness was closer to the human reference on 4/6 images and worse on 2/6.

This uses the already completed no-review trials. Jev answer review was never invoked in those trials; no rejected answer was relabeled or substituted. Historical review-enabled experiments remain in the full report but are excluded from this final comparison. No additional paid inference was needed.

This is the original frozen runtime's result, not a fresh evaluation of subsequent repairs. Six images and one attempt do not establish broad superiority. The answers relied on visual estimation after unusable segmentation, so this result does not establish an OpenCV perception gain.

[All six images, predictions and traces](index.html) · [Machine-readable final score](final-score.json) · [Original results](results.json)
