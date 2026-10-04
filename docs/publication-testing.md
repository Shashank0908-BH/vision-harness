# Publication and testing record

Publication prepared on 4 October 2026 from source revision `2769348` in the original Vision repository. The three review branches are cumulative snapshots. All tracked source, configurations, dependency locks, experiments, research, and report artifacts from that revision are included. The tool-specific development guidance is retained as `docs/development-guide.md`. No assistant coauthor trailers are added.

## Review order

| PR branch | Original snapshot | Scope |
|---|---|---|
| `review/01-core-benchmarks` | `5381ddb` | Typed-tool harness, providers, bounded review, specialist routing, Harbor evaluation, and benchmark history through the repeated Kromp evaluation. |
| `review/02-research-audits` | `1648350` | Observed-output routing, research/execution v3, reference-integrity audit, native StarDist checks, and initial Daytona workflow. |
| `review/03-operations-validation` | `2769348` | Transport/documentation/dependency repairs, GPU reuse workflow, completed repair reports, team handoff, public license, and this verification record. |

PR 2 is based on PR 1; PR 3 is based on PR 2. Review and merge in order. The final branch contains the complete project. Snapshot commit IDs differ from the original history; frozen protocol hashes and original evidence files remain unchanged.

## Checks rerun for publication

The per-branch logs are in [publication-validation](publication-validation/). Each snapshot was tested from its own checkout using the existing Python 3.12 environment and its own source path.

| Snapshot | Core tests | Ruff lint (`src evals tests`) |
|---|---|---|
| Core and benchmarks | 65 passed | Passed |
| Research and audits | 107 passed, 1 skipped | Passed |
| Operations and validation | 130 passed, 1 skipped | Passed |

The skipped check requires a locally generated development task that is intentionally Git-ignored. In the original workspace, where that task exists, the current full suite passed **131 tests**. The clean publication checkout also passed **18 infrastructure tests** covering the authentication stop guard, trial path and mount boundaries, verifier network isolation, and fail-closed resource limits. These tests use mocks; they do not provision cloud resources.

The initial infrastructure invocation could not collect the resource-limit tests because the main environment lacks the optional Daytona SDK. Repeating with the project's pinned `daytona==0.216.0` in a temporary uv dependency overlay passed all 18 tests.

The current formatting check is **not passing**: 38 files would be reformatted and 61 are already formatted. Lint passes. No blanket formatting changes were made to the source used in historical experiments.

Reproduction commands from the project root:

```bash
uv sync --locked --extra eval --extra research
uv run pytest -q
uv run ruff check src evals tests
uv run ruff format --check src evals tests
uv run --with daytona==0.216.0 python -m pytest -q \
  infra/daytona/reuse/test_auth_guard.py \
  infra/daytona/reuse/test_environment.py \
  infra/daytona/test_resource_limits.py
```

## Historical experiments and audits

These records describe earlier runs. Publication checks did not repeat hosted-model calls, cloud/GPU inference, or the full benchmark cohorts. [The historical verification record](verification.md) contains test counts, trace and mask audits, provider health checks, report rendering checks, and their original scope. Failed attempts, abstentions, missing responses, and superseded scores remain preserved.

| Evidence | Recorded scope and interpretation |
|---|---|
| [Synthetic five-task cohort](../reports/cohort-five-20260922/) | 25 live trials; integration evidence, not a capability claim. |
| [Original BBBC001 comparison](../reports/bbbc001-20260922/) | Published six-image microscopy task, original trials and selection-only ablation. |
| [Full-harness retest](../reports/bbbc001-full-repaired-20260922/) | Vanilla 6/6 answers, 10.30% error; full harness 0/6 answers, six abstentions. |
| [Structured review loop](../reports/bbbc001-loop-20260922/) | 12 paired trials; full loop accepted no counts, with three abstentions and three Astra timeouts. Proposal errors remain separate from final answers. |
| [Tools and selection retest](../reports/bbbc001-no-review-20260922/) | 18/18 counts; mean errors 17.34% vanilla, 16.16% tools, 14.27% selection. Previously inspected six-image cohort. |
| [Standalone specialists](../reports/bbbc001-specialists-20260922/) | 12/12 mask-derived counts; StarDist 6.67%, Cellpose-SAM 14.09%; geometry and input/checkpoint hashes audited. |
| [StarDist full-chain integration](../reports/bbbc001-stardist-20260922/) | 18 primary trials plus one separate timeout recovery; tools returned 6/6 at 6.67%, full review abstained on all six. 19 valid traces and 41 audited maps. |
| [Adaptive BBBC039](../reports/bbbc039-adaptive-20260922/) | 24 primary trials and six controls; full review accepted 2/6. Fixed-profile diagnostics are explicitly post hoc. |
| [Specialist routing](../reports/bbbc039-routing-20260922/) | Six additional images; Cellpose 4.23%, vanilla 5.44%, routed harness 5.71%; every routed answer provisional. |
| [Model research](../reports/model-research-20260922/) | Source-backed candidate/model research artifacts; separate from measured inference accuracy. |
| [Repeated Kromp evaluation](../reports/kromp-repeated-20260922/) | 37 images × three repetitions, 111 paired trials, 444 specialist executions and 333 validated Harbor traces. Original scores are superseded by the annotation audit. |
| [StarDist/reference audit](../reports/stardist-audit-20260922/) | One reference reused 55 IDs across 102 nuclei. Corrected conditional errors: vanilla 8.57%, full v1 14.14%, fixed Cellpose 11.40%. All-attempt within-10%: 70.3%, 58.6%, 73.0%. 555 fresh native inferences; 333 original-setting maps matched pixel for pixel. Scale diagnostics are post hoc. |
| [Observed-output smoke test](../reports/observed-routing-smoke-20260922/) | Four specialists, five hosted calls, valid trace and zero candidate failures; integration evidence only. |
| [Research/execution original](../reports/research-execution-20260922/final-score.md) | 12 images × three repeats per arm. Full returned 6/36 vs vanilla 36/36; laptop sleep interrupted infrastructure. |
| [96 KB transport variant](../reports/research-execution-20260922/test-transport96/final-score.md) | Full returned 12/36; original vanilla controls reused. Sleep interruptions retained. |
| [Awake 96 KB follow-up](../reports/research-execution-20260922/test-awake96/final-score.md) | Full returned 17/36 vs vanilla 35/36; all-attempt within-10% 17/36 vs 31/36. |
| [First repair repeat](../reports/research-execution-20260922/test-repair01/final-score.md) | Full returned 7/36, all reviewed; all 36 prior vanilla controls retained. Post-hoc comparison. |
| [GPU repair repeat](../reports/research-execution-20260922/test-gpu-repair02/summary.md) | Full returned 33/36 vs vanilla 35/36; both achieved 31/36 within 10%. Conditional errors 4.63% vs 5.75%; all 33 harness answers provisional. Hardware/deployment differ. |
| [Operational repair validation](operational-repair-20260924.md) | Two actual documentation correction replays passed, along with private Torch installation/import checks and repaired StarDist GPU inference. No new full-cohort accuracy result. |

The GPU result does not establish a harness win or JEV approval. A new frozen repeated benchmark after the operational fixes remains pending.

## Artifact availability

All 14 tracked report directories are included. Large local `runs/`, `jobs/`, generated task bundles, virtual environments, downloaded models, and credentials remain Git-ignored. Some historical report links target those local raw artifacts or the existing GPU workspace; those links cannot resolve from GitHub alone. Included protocols, summaries, result JSON, audits, and tracked visual assets preserve the recorded evidence but are not a complete mirror of those external runtime stores.

## License

Original harness code and documentation use [MIT](../LICENSE). Third-party datasets, images, annotations, dependencies, and weights retain their own terms; see [third-party notices](../THIRD_PARTY_NOTICES.md).
