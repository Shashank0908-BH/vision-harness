# Completed infrastructure repeat

Infrastructure caution: host sleep events=8, trials with wall/controller gaps over 60 seconds=6. Do not interpret this as a clean comparison until these interruptions are reviewed.

Full harness: 17/36 attempts within 10% of the reference (47.22%), with 17/36 counts returned. Vanilla Astra: 31/36 (86.11%), with 35/36 counts returned.

The full harness did not improve all-attempt success in this pilot.

Full minus vanilla: -38.89 percentage points; descriptive image-cluster bootstrap 95% interval [-61.11, -19.38].

Cohort: the same 12 BBBC039 official-test images, three fresh runs per arm. No previous answers or research prefixes were reused. The 96 KB task environments remain byte-identical to the frozen configuration (660 files checked). The interrupted earlier experiments remain separate and are not pooled.

[Interactive traces and all counts](index.html) · [Full score table](final-score.md) · [Operational failures](operational-diagnostics.json) · [Host audit](host-sleep-events.txt) · [Frozen protocol](selection.json)
