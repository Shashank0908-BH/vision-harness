# Development status: no held-out benchmark score yet

The new pipeline is implemented in `src/vision_harness/research_execution/` and
the Harbor task/evaluation adapter in `evals/research_execution/`. See the
[file map and CLI guide](../../docs/research-execution-v3.md).

The proposed pilot is 12 previously unused BBBC039 official-test images, with
three fresh repetitions for vanilla Astra and three for the complete harness.
Development validation is complete and the held-out task set is being frozen and launched; no primary score exists yet.
Development uses one image from the official validation split.

## Recorded development work

| Run | What it established or exposed |
|---|---|
| Isolated Codex health check | Exact configured `gpt-6-astra` successfully invoked a shell command and returned its observed result. |
| `research-execution-dev-01` | Docker's build backend would not resolve a bare local image SHA in `FROM`; changed to the local tag with explicit digest verification before launch. No scientific inference. |
| `research-execution-dev-02` | Real research, catalog extraction and Jev candidate scoring worked. Prefix-only documentation excerpts omitted key usage details. The model correctly declined executable planning, which surfaced as a plan-contract error. No valid final count. |
| `research-execution-dev-03-vanilla` | A fresh vanilla Astra call returned an answer. Initial separate-verifier setup failed; the answer was preserved. |
| `research-execution-dev-03-verifier-check` | Regrading exposed that this installed Docker backend rejects Harbor's `no-network` policy. Reference separation did not require that unsupported setting. |
| `research-execution-dev-03-verifier-check-02` | Regraded the same saved answer successfully in a fresh verifier-only container, without another inference call. This is a grader check, not a second model trial. |
| `research-execution-dev-04-full` | Required task parts were preserved, and missing usage details triggered renewed research. Later OpenAI calls failed with HTTP 401 `token_invalidated`. |
| `research-execution-dev-05-full` | Research and Jev scoring completed with complementary libraries retained; actual documentation was retrieved. OpenAI rejected the documentation-processing call with HTTP 401 `token_invalidated`. |

The verifier Dockerfile was added to development task folders while debugging
the missing-container-definition issue. These mutable development tasks are not
claimed as frozen benchmark runs. Final task preparation includes the corrected
verifier definition from the start.

## Corrections included in current source

- Every necessary task requirement is required by schema.
- Candidate scoring covers every candidate–requirement pair, and role rankings
  are separate. Relevant complementary libraries survive retention.
- Up to three usage pages per retained candidate are retrieved; the model-facing
  budget is 60,000 characters per page, with explicitly located windows for
  longer documents. Full pages and hashes are preserved. Python/plain text is
  not parsed as HTML.
- Readiness means a documented, testable procedure. Unknown runtime and possible
  biological errors become checks/limitations rather than requiring accuracy to
  be proven before inference.
- Invalid plan contracts can receive one explicit repair before scoring.
- The separate verifier has its own build definition and receives only declared
  final artifacts. The agent is stopped before reference grading begins.
- Execution errors, authentication errors and Jev review results remain distinct.

## Required next step

The user replaced the key and the exact Astra/Codex live health check passed.
Freeze the test task set and source hashes, then run all 72 planned attempts. The existing
failed traces must remain available rather than being overwritten or presented
as successful tests.

## Continued validation after key replacement

- `dev-06-full`: fresh intake, research, every candidate-role score, documentation
  extraction and complete plan generation passed. Combined plan scoring exceeded
  the 48 KB local Jev request budget. Lossless subject batching now splits the
  request; no scientific plan content is shortened.
- `dev-07-full`: explicitly labeled replay of the successful development prefix.
  Fresh Jev plan scores, Codex inference, artifact validation, Astra visual inspection
  and Jev output scores passed. Noul review returned HTTP 422 because criteria
  were a string instead of a true/false mapping. This was an adapter error, not
  a rejection of the scientific answer.
- `dev-08-full`: repeats that development-only prefix after correcting the Noul
  wire contract. All held-out runs will execute every stage afresh.

Before test freeze, the controller call ceiling was increased from 28 to 48 so
two research passes plus size-split scoring requests can reach a second execution.
The two-round and 25-minute limits remain. Development replay artifacts preserve
the earlier 28-call policy; they are not rewritten. Independent artifact checks
now expose dtype/minimum label and explicit validation flags to the visual reviewer.
A regression test also verifies that a later review failure preserves the earlier
answer and matching mask together.

`dev-08-full` completed: the first selected program produced a measured count,
Astra inspected it, Jev scored and reviewed it, and low evidence support triggered
new research. Second-round proposals failed required-task coverage even after
the allowed repair. The first reviewed answer/mask were preserved as
`provisional_after_error` and accepted by the separate verifier. Harbor exported
a validated trajectory. This establishes live stage integration and recovery,
not two successful executions or an independent benchmark accuracy result.

The research prompt now discloses the three-page retrieval budget and prioritizes
checkpoint loading, preprocessing and inference documentation within it. This
addresses the observed case where general FAQ pages displaced loader documentation.
Final pre-freeze checks: 108 tests, scoped lint, and the dependency lock check.
