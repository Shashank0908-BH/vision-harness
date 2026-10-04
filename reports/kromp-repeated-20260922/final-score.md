# Repeated external microscopy benchmark

37 official Kromp test images × 3 fresh repetitions per image.

| Arm | Counts returned | Complete-cohort MAPE | Conditional MAPE | Run MAPE SD | Within 10%, all attempts |
|---|---:|---:|---:|---:|---:|
| Vanilla Astra | 107/111 | — | 9.68% | — | 70.27% |
| Astra + preferred specialist (paired) | 98/111 | — | 20.79% | — | 51.35% |
| Astra + Jev selection (pre-review stage) | 101/111 | — | 16.90% | — | 55.86% |
| Full current harness | 101/111 | — | 16.90% | — | 55.86% |
| Strict-support diagnostic | 4/111 | — | 12.32% | — | 1.80% |
| Fixed StarDist default | 111/111 | 25.80% | 25.80% | 0.00 | 54.05% |
| Fixed StarDist sensitive | 111/111 | 32.58% | 32.58% | 0.00 | 51.35% |
| Fixed StarDist conservative | 111/111 | 17.45% | 17.45% | 0.00 | 62.16% |
| Fixed Cellpose-SAM | 111/111 | 13.41% | 13.41% | 0.00 | 70.27% |
| Astra-preferred measurement only | 111/111 | 30.95% | 30.95% | 1.05 | 51.35% |
| Jev-selected measurement only | 111/111 | 24.44% | 24.44% | 1.07 | 55.86% |

Conditional MAPE uses only returned numeric answers. A missing complete-cohort MAPE means one or more outputs were absent. All-attempt within-10% success counts missing outputs as failures.

Run SD is the sample standard deviation of three complete cohort MAPEs; it is not uncertainty over new images. Confidence intervals resample images, averaging repetitions within image; they do not establish generalization to independent patients.

Review statuses: {"caution": 107, "supported": 4}

Routing: {"rankable_trials": 111, "best_candidate_choices_including_ties": 20, "mean_regret_pp": 15.832856365929052}

## Three-run averages

These are conditional returned-answer MAPEs; coverage can differ between repetitions. SD is in percentage points.

| Arm | Run 1 | Run 2 | Run 3 | Mean ± run SD |
|---|---:|---:|---:|---:|
| Vanilla Astra | 9.88% (35/37) | 9.29% (36/37) | 9.88% (36/37) | 9.68% ± 0.34 pp |
| Astra + preferred specialist (paired) | 24.50% (33/37) | 19.20% (32/37) | 18.63% (33/37) | 20.78% ± 3.24 pp |
| Astra + Jev selection (pre-review stage) | 16.32% (34/37) | 16.97% (33/37) | 17.40% (34/37) | 16.90% ± 0.54 pp |
| Full current harness | 16.32% (34/37) | 16.97% (33/37) | 17.40% (34/37) | 16.90% ± 0.54 pp |
| Strict-support diagnostic | 10.36% (2/37) | 14.27% (2/37) | — (0/37) | — ± — pp |
| Fixed StarDist default | 25.80% (37/37) | 25.80% (37/37) | 25.80% (37/37) | 25.80% ± 0.00 pp |
| Fixed StarDist sensitive | 32.58% (37/37) | 32.58% (37/37) | 32.58% (37/37) | 32.58% ± 0.00 pp |
| Fixed StarDist conservative | 17.45% (37/37) | 17.45% (37/37) | 17.45% (37/37) | 17.45% ± 0.00 pp |
| Fixed Cellpose-SAM | 13.41% (37/37) | 13.41% (37/37) | 13.41% (37/37) | 13.41% ± 0.00 pp |
| Astra-preferred measurement only | 30.35% (37/37) | 32.17% (37/37) | 30.33% (37/37) | 30.95% ± 1.05 pp |
| Jev-selected measurement only | 24.18% (37/37) | 25.61% (37/37) | 23.52% (37/37) | 24.44% ± 1.07 pp |
