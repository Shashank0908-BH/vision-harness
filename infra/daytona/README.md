# Daytona experimentation sandbox

This directory is separate from the currently frozen local benchmark. It does
not change that benchmark's code, task cohort, time budgets or results.

## What exists

- `config.toml`: requested machine resources, names and idle shutdown interval.
- `manage.py`: CLI to create, inspect, populate, check and delete only this lab.
- `Dockerfile`: reusable scientific image, when snapshot permissions are enabled.
- `bootstrap.sh`: the same installation on an ordinary public-image worker.
- `configure_cuda.py`: TensorFlow's documented CUDA library-link setup within
  its own environment; needed for the tested bare Python image.
- `run_harness.py`: cloud-only entry point that replaces the old hardware inventory
  within its own process and records configurable controller/execution budgets.
- `science.in` / `science.lock`: pinned Linux x86-64 controller, Harbor, OpenCV,
  TensorFlow with CUDA and StarDist dependencies, with distribution hashes.
- `torch.in` / `torch.lock`: separate PyTorch with CUDA and Cellpose environment.
  Frameworks run in separate processes so they can release GPU memory between jobs.
- `control.in` / `control.lock`: local Daytona management dependencies.
- `smoke.py`: actual CUDA arithmetic and pretrained-model forward passes; verifies
  GPU use, CPU/RAM allocation and checkpoint identity. Zero images are infrastructure
  checks, not manufactured benchmark problems or evidence of counting accuracy.

Local management state, source hashes, build logs and downloaded artifacts live
in `runs/daytona/`, which is already Git-ignored. Secrets are read from the root
`.env`; they are not printed, included in image builds or copied by source sync.

## Resources and lifecycle

Requested: **one RTX 4090, 8 vCPU, 32 GiB RAM, 80 GiB local disk**. Live hardware
checks, rather than the request alone, determine whether provisioning passed.
The GPU's VRAM is separate from the requested host RAM.

GPU workers are ephemeral: stopping/deleting one loses its local filesystem.
The intended persistent Daytona volume is mounted at `/persist`. Model weights,
source manifests and final outputs must be copied there. The SDK defaults must
not silently shut down a long job: this configuration allows 120 minutes idle;
disable idle shutdown explicitly while supervising a longer job, then restore it.
An asynchronous process session continues when the local terminal disconnects.

**Initial permission blocker:** the supplied key allows sandbox creation but
Daytona denied volume access and custom snapshot creation. A bare GPU worker can
be provisioned and validated independently. A directory named `/persist` on that
temporary worker is only local disk; `hardware.json` records whether it is an
actual mounted volume. `run` refuses long jobs without the volume. Do not claim
durable storage until the mounted-volume check passes.

At published 2026-09-23 rates, this request is approximately **$1.92/hour** while
running: GPU $0.99 + CPU $0.4032 + RAM $0.5184 + roughly $0.0081 local disk.
Provider API calls and persistent storage are additional. Availability, quotas
and billing can change; this is an estimate, not a spending cap.

## Commands from the repository root

```bash
uv venv --python 3.12 runs/daytona/venv
uv pip install --python runs/daytona/venv/bin/python --require-hashes -r infra/daytona/control.lock

# Normal durable setup, after volume and snapshot permissions are available:
runs/daytona/venv/bin/python infra/daytona/manage.py build
runs/daytona/venv/bin/python infra/daytona/manage.py provision
runs/daytona/venv/bin/python infra/daytona/manage.py sync

# Temporary setup when those optional APIs are unavailable:
runs/daytona/venv/bin/python infra/daytona/manage.py provision --base-image --without-volume
runs/daytona/venv/bin/python infra/daytona/manage.py bootstrap
runs/daytona/venv/bin/python infra/daytona/manage.py logs --name bootstrap
runs/daytona/venv/bin/python infra/daytona/manage.py exec --command 'tail -n 25 /persist/setup/bootstrap.log'
# Wait for bootstrap exit code 0 before syncing or checking.
runs/daytona/venv/bin/python infra/daytona/manage.py sync

runs/daytona/venv/bin/python infra/daytona/manage.py status
runs/daytona/venv/bin/python infra/daytona/manage.py check --name health
runs/daytona/venv/bin/python infra/daytona/manage.py logs --name health
runs/daytona/venv/bin/python infra/daytona/manage.py exec --command 'tail -n 25 /persist/setup/health.log'
runs/daytona/venv/bin/python infra/daytona/manage.py download --remote /persist/setup/health.json --local runs/daytona/health.json

# Inspect commands and package versions without making model API calls:
runs/daytona/venv/bin/python infra/daytona/manage.py exec --command '/opt/venvs/science/bin/harbor --version'

# Long job, after durable storage is configured. Choose a unique job name.
runs/daytona/venv/bin/python infra/daytona/manage.py idle --minutes 0
runs/daytona/venv/bin/python infra/daytona/manage.py run --name experiment-001 --command 'YOUR_EXPLICIT_EXPERIMENT_COMMAND'
runs/daytona/venv/bin/python infra/daytona/manage.py logs --name experiment-001
# After collecting outputs:
runs/daytona/venv/bin/python infra/daytona/manage.py idle --minutes 120

# GPU deletion is irreversible for LOCAL files. Download them first.
# This command preserves a separately mounted persistent volume.
runs/daytona/venv/bin/python infra/daytona/manage.py delete
```

If a temporary worker already exists when permissions are fixed, provisioning
does not replace it. Download its artifacts first, delete only that lab worker,
then create a fresh worker with the persistent volume. Volumes attach at creation.

Use `/opt/venvs/science/bin/python-gpu` for the controller/StarDist: this wrapper
sets the TensorFlow environment's CUDA library search paths before Python starts.
Use `env -u LD_LIBRARY_PATH /opt/venvs/torch/bin/python` for PyTorch/Cellpose to
avoid carrying TensorFlow's CUDA 12 paths into PyTorch's CUDA 13 process.
Code is in `/workspace/vision`,
StarDist weights in `/opt/checkpoints/stardist`, and warm Cellpose weights in
`/opt/checkpoints/cellpose`. Copy newly downloaded weights into persistent storage
before deleting a worker. Installed package inventories are saved by the checks.

## What this setup does not yet establish

This step provisions infrastructure; it does not start or score a new cohort.
The original `research_execution` entry point still describes the old CPU-only
2-core/6-GiB task and has a 1,500-second controller budget. The cloud entry point
`run_harness.py` measures the actual GPU, CPU and RAM, exposes both Python
environments, and accepts explicit application budgets (defaults: 2 hours per
task, 96 controller calls, 20 minutes per Codex execution, 4 rounds). It records
that configuration before any provider call. This is a new configuration, not
an extension of the existing frozen benchmark. The executor's `/.dockerenv`
requirement is checked in the hardware report. Hardware detection and command
startup are tested separately from a full end-to-end harness benchmark.

Inspect the cloud configuration without making provider calls:

```bash
runs/daytona/venv/bin/python infra/daytona/manage.py exec --command '/opt/venvs/science/bin/python-gpu /workspace/vision/infra/daytona/run_harness.py --describe'
```

To launch a future individual trial inside its own sandbox, use the GPU Python
entry point and pass `--mode`, `--query`, `--raw`, `--preview`, `--output` and the
chosen budgets to `run_harness.py`. Supply provider credentials at execution time
through Daytona's structured `process.exec(..., env=...)` API or an approved secret
binding, never as command text or as part of the source archive. Dataset choice,
agent/verifier isolation and a complete cloud Harbor run remain a separate
experiment, not something the infrastructure checks have already validated.

Harbor 0.23.0 with its Daytona extra is installed in the scientific environment.
Future benchmark attempts should each have a fresh Harbor-managed sandbox, with
the verifier/reference masks kept outside the agent environment. This reusable
lab is for preparation and debugging; do not expose earlier attempts or reference
labels to the next attempt through a shared mounted artifacts directory.

For a full declared cohort, run three fresh attempts per task per arm. With exactly
three attempts, **pass@3** is the fraction of tasks with at least one success;
it is not average accuracy and does not show the system can identify its correct
answer without a grader. Also report pass@1, all three outcomes, failures, time,
cost and the deterministic specialist control. Define success and task inclusion
before reading results. Previously inspected images remain development data.

## Official references

- [Daytona GPU sandboxes and lifecycle](https://www.daytona.io/docs/en/sandboxes/)
- [Persistent volumes](https://www.daytona.io/docs/en/volumes/)
- [Pricing](https://www.daytona.io/pricing)
- [Harbor task resources](https://www.harborframework.com/docs/tasks)
