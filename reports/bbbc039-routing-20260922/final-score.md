# Specialist routing experiment

Six new official-test images; local derived count MAPE, not published segmentation performance. Jev receives structured evidence, not pixels.

| Arm | Numeric results | Count MAPE | Exact |
|---|---:|---:|---:|
| stardist-default | 6/6 | 7.22% | 0 |
| stardist-sensitive | 6/6 | 5.43% | 0 |
| stardist-conservative | 6/6 | 8.67% | 0 |
| cellpose-sam | 6/6 | 4.23% | 0 |
| vanilla_astra | 6/6 | 5.44% | 0 |
| harness_with_review | 6/6 | 5.71% | 0 |
| astra_preferred_measurement | 6/6 | 7.22% | 0 |
| jev_selected_measurement | 6/6 | 5.71% | 0 |

Astra preference and Jev selection measurement rows are policy diagnostics from the frozen decision, not separate answer-generation arms.
The harness returns estimates with either supported or caution review status. This differs from the historical full harness abstention policy; do not pool their scores.

Review: {"supported": 0, "caution": 6, "not_completed": 0, "not_run": 0}

Routing diagnostics: {"complete_tasks": 6, "top_choice_matches_oracle_including_ties": 2, "mean_regret_percentage_points": 1.6578933414602584}
