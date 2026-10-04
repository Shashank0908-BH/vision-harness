# Daytona: one continuously running GPU workspace

The current setup follows the user's single-workspace policy: one RTX 4090
workspace, at most one named snapshot, and one persistent volume. See
[PERSISTENCE.md](PERSISTENCE.md) for lifecycle details, commands and cleanup.

## Files to review

| File | Purpose |
|---|---|
| `config.toml` | Fixed resource names, 8 vCPU / 32 GiB RAM / 80 GiB disk, one GPU, no auto-stop, and resource limits. |
| `manage.py` | Reuses the fixed workspace, builds/reuses one snapshot, syncs an allowlisted source bundle, manages sessions, and cleans only designated scratch files. |
| `doctor.py` | Read-only credential, configured resource and mounted-volume checks. Never provisions resources or prints credentials. |
| `Dockerfile` | Reusable scientific dependency environment; contains no provider keys or benchmark answers. |
| `science.in` / `science.lock` | Pinned controller, Harbor, OpenCV, TensorFlow/CUDA and StarDist packages. |
| `torch.in` / `torch.lock` | Separate PyTorch/CUDA and Cellpose environment. |
| `control.in` / `control.lock` | Local Daytona-management dependencies. |
| `configure_cuda.py` | Creates the TensorFlow CUDA wrapper and library links. |
| `smoke.py` | Checks GPU arithmetic and actual specialist forward passes. |
| `run_harness.py` | Describes real cloud hardware and accepts explicit per-task budgets. Does not create another sandbox. |
| `bootstrap.sh` | Recovery installation path for a bare image; normally dependencies come from the named snapshot. |
| `benchmark/` | Earlier frozen three-arm cloud benchmark; its worker-per-attempt launcher is now disabled by policy. |

## Start here

```bash
runs/daytona/venv/bin/python -m infra.daytona.doctor
runs/daytona/venv/bin/python infra/daytona/manage.py status
```

For initial provisioning only:

```bash
runs/daytona/venv/bin/python infra/daytona/manage.py build
runs/daytona/venv/bin/python infra/daytona/manage.py provision
runs/daytona/venv/bin/python infra/daytona/manage.py sync
```

Repeated calls reuse the same names; creating another project sandbox or named
snapshot is refused once its configured limit is reached. No automatic snapshot
is created for each run. A GPU workspace must remain running to preserve its
local disk. `/persist` survives its deletion; save important outputs there.

Local control state and reports are in ignored `runs/daytona/`. The root `.env`
is read only by the local management process; source sync never includes it.
There is no model API call merely from provisioning, source sync or health checks.

The current GPU workspace is a development environment. A reused directory is
not an isolated benchmark attempt. New benchmark work must define its reset and
verifier boundaries before claiming comparability with the earlier fresh-worker
experiment. The local repaired 36-trial harness repeat remains independent.

The [single-workspace GPU repeat](reuse/README.md) now defines those boundaries:
serial Harbor trials with fresh private mounts and processes, read-only shared
models, a separate offline verifier, frozen inputs, and persistent checkpoints.
It reuses the registered GPU workspace and creates no additional Daytona resources.
