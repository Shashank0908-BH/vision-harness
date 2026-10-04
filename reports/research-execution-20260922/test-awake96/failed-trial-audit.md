# Audit of the 19 failed harness trials

None of the 19 reached final Jev answer review. Earlier Jev candidate/plan scoring did run in some trials.

Six trials preserved segmentation masks even though Astra/Codex execution-stage visual acceptance requested replanning. The latest available mask in every one of these six meets the benchmark count tolerance (within 10%). This does not establish perfect segmentation or validate every review concern. The other 13 trials have no saved standard output mask to grade.

Disjoint breakdown: six trials with saved masks withheld before Jev review; seven API failures before a saved mask; five research/catalog validation failures; one model-loading/API-interface execution failure with no saved mask. One of the six mask-producing trials subsequently hit an API timeout, so the terminal-error-only breakdown differs.

| Trial | Last saved round | Count | Reference | Error | Instance F1 |
|---|---|---:|---:|---:|---:|
| image-03__uknsS7Y | round-02 | 47 | 49 | 4.08% | 0.917 |
| image-04__SiARKG5 | round-01 | 130 | 139 | 6.47% | 0.959 |
| image-07__9tqKMAg | round-01 | 128 | 130 | 1.54% | 0.969 |
| image-07__S3eLRY9 | round-02 | 135 | 130 | 3.85% | 0.943 |
| image-08__KsnQbKR | round-02 | 164 | 167 | 1.80% | 0.943 |
| image-10__Hzq2ta5 | round-02 | 120 | 127 | 5.51% | 0.947 |

The latest mask was selected by round order before grading, not by best reference accuracy. All ten available intermediate masks are retained in the [audit data](failed-trial-mask-audit.json); one earlier mask exceeded 10% error before a later round improved it.

This is a post-hoc artifact audit with no new model calls. The official result stays 17/36 successful completed harness trials. No failed trial was replaced and no benchmark answer was altered.

The execution-stage acceptance gate can suppress a usable provisional count before the planned Jev review stage. A future implementation should separate successful artifact production from qualitative concerns, preserve structurally valid provisional outputs, and pass those concerns to the review stage. That change needs a separately recorded retest.
