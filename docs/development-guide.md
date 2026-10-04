# Development guide

Development commands, architecture, and evaluation rules for this repository.

## What this is

A CLI-first research harness for vision questions (currently 2D fluorescence-nucleus counting). **Astra** (`gpt-6-astra`, OpenAI Responses API) plans, interprets and answers; **Jev** (`jev-1.13.0`, TypeSafe HTTP API) scores candidate methods/plans and reviews whether evidence supports an answer; Python validates, executes tools and records everything. Harbor (pinned 0.23.0, needs Docker) runs isolated benchmark tasks with a separate verifier.

## Commands

Run everything from the repo root (configs and prompts are loaded as project-relative files). Python 3.12 via `uv`.

```bash
uv sync --extra eval                      # install (add --extra research for bs4/tifffile)
uv run pytest -q                          # all tests (mocked providers, no paid calls)
uv run pytest tests/test_runtime.py::test_name -q   # single test
uv run ruff check src evals tests
uv run ruff format --check src evals tests

uv run vision doctor                      # config/credential check; --check-api makes small billed calls
uv run vision run --offline --mode full --image examples/shapes.png \
  --prompt 'How many red circles are in this image? Return a number.'   # no API calls
uv run vision tool run components --request examples/components.json      # one tool, no models
uv run vision inspect|replay|export runs/RUN_ID
uv run vision specialist --help           # StarDist/Cellpose-SAM routing + observed-output `compare`
```

Research-execution (v3) and routing evals are run as modules, e.g. `.venv/bin/python -m evals.research_execution.{toolchain,prepare,run,status,report}` and `.venv/bin/python -m evals.routing {prepare,infer,score}`. See `docs/research-execution-v3.md` and `docs/model-routing.md` for arguments.

Credentials live in `.env` (`OPENAI_API_KEY`, `JEV_API_KEY`; `TYPESAFE_API_KEY` is an alias, `JEV_API_KEY` wins). The project `.env` deliberately overrides inherited environment variables.

## Architecture

Three generations of runtime coexist; older ones are kept reproducible, not replaced.

1. **v1 typed-tool runtime** (`src/vision_harness/*.py`, `tools/`, `providers/`). Read in this order: `contracts.py` (Pydantic records + provider protocols) → `runtime.py` (probes → Astra candidate plans → Python eligibility → Jev score → `selection.py` → tool execution → Astra answer → optional Jev review/retry) → `selection.py` → `tools/opencv.py` → `providers/astra.py`, `providers/jev.py`. Plans are typed tool steps from `tools/registry.py` (backed by `configs/capabilities*.toml`), never arbitrary code. `--mode` ablates the pipeline: `vanilla | tools | select | review | full`. `review_loop.py` is an opt-in multi-round loop (`configs/poc-loop.toml`).
2. **Specialist routing** (`routing/`, `evidence_routing/`): versioned StarDist/Cellpose-SAM procedures run as isolated workers in separate venvs (`.venv-stardist`, `.venv-cellpose`, CPU/MPS); `.venv` holds only the light controller. `evidence_routing` backs `vision specialist compare` (run several procedures, measure disagreement, Jev scores every valid output).
3. **Research-execution v3** (`research_execution/`, `evals/research_execution/`): the current target. Discovery → documentation → competing Python programs → Jev plan scoring → Codex CLI executes inside a Docker container → evidence checks on the instance map → Noul review, two-round bounded. Config `configs/research-execution.toml`, prompt `prompts/astra-research-execution.md`.

Cross-cutting behavior to preserve:
- Hard constraints are enforced in Python; a high Jev score cannot override them. Jev Score (expected rubric level) and Noul (yes-probability) are different scales. Changing a rubric in `prompts/jev_*.json` may require recalibrating thresholds in config.
- Jev sees structured text only, never pixels. `providers/evidence_budget.py` shrinks requests to a byte budget (`limits.jev_max_request_bytes`); full geometry stays in the run's `evidence/`.
- Astra saves raw responses before parsing; `models.format_retries` allows one bounded retry. SDK auto-retries are disabled so every retry is visible. Provider failures produce a saved error answer, never a silent offline fallback. Offline stand-ins (`demo.py`) must be explicitly requested and never count as model performance.
- `tracing.py` redacts keys. Each run writes `runs/<id>/` (manifest, `events.jsonl`, `calls/`, `plans-N.json`, `answer.json`, `artifacts/`). Harbor output goes to `jobs/`. Both are git-ignored.
- Harbor is imported lazily, only for evaluation/export commands.

## Evaluation rules

- Ground truth goes only to the verifier (`tests/expected.json` in task bundles). `evals/build_tasks.py` copies an explicit allowlist into the agent image. Don't leak labels, source filenames or prior reports into agent inputs.
- Frozen cohorts are never rerun or overwritten. Generators and runners refuse to overwrite existing output on purpose. A new experiment gets a new config copy and a new `jobs/` directory, labeled as a separate follow-up; don't retry unfavorable outcomes.
- Development uses validation/dev splits. Held-out test images must not be used for debugging, and dev replays are forbidden in test runs.
- Reports in `reports/` are evidence records. When a result is corrected, preserve the original and mark it superseded.
- After changing dependencies, regenerate the hashed `requirements-runtime.txt` used by task Docker images.

## Docs

Start with `docs/file-map.md` (file-by-file responsibilities), then `docs/walkthrough.md`. Also see `docs/research-execution-v3.md` (v3 modules and commands), `docs/model-routing.md`, `docs/evidence-routing.md` and `evals/README.md` (protocol and leakage controls). `research/` and `vision-harness-study-guide.html` predate the implementation and aren't evidence that it works.
