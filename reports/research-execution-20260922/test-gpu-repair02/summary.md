# Completed GPU repair repeat

Experiment: `reuse-gpu-repair02`. Completed 24 September 2026. The 12 official
BBBC039 microscopy images were already inspected; each has three new full-harness
runs, compared with all 36 preserved vanilla attempts, including its failure.
This is a post-hoc engineering comparison. Hardware and deployment also differ.

| Metric | Full harness | Vanilla Astra |
|---|---:|---:|
| Finished attempts | 36/36 | 36/36 |
| Returned answers | 33/36 | 35/36 |
| Within 10% of reference count, all attempts | 31/36 (86.1%) | 31/36 (86.1%) |
| Mean absolute percentage error, answered only | 4.63% | 5.75% |
| Mean trial time | 1,122.4 s | 37.5 s |
| Mean instance F1, returned masks, IoU ≥ 0.5 | 0.9567 | Not applicable |

The conditional errors cover different answered subsets. They do not establish
an overall harness win: the primary success metric is tied. JEV reviewed all
33 harness answers; 31 were provisional and two provisional after a later error.
None were approved. Three missing answers failed before review: two documentation
contract failures and one trial with GPU-placement then missing-dependency errors.

[Machine-readable summary and full-harness per-trial counts](summary.json).
Full raw traces remain in the existing workspace and persistent volume; ignored
`runs/` and `jobs/` are not included in the repository.

The later operational repairs passed both actual documentation correction replays,
private Torch dependency installation/import validation, and corrected StarDist
GPU inference. Those are development checks, not replacements for failed
benchmark attempts. A full repeated cohort with those repairs is still pending.
