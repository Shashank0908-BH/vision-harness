# One reusable GPU workspace

The user chose one GPU workspace kept running continuously on 2026-09-23.
This supersedes the earlier proposal for a CPU coordinator plus many GPU workers.

## Resource policy

| Resource | Configuration |
|---|---|
| Workspace | `vision-workspace`, one RTX 4090 |
| Host resources | 8 vCPU, 32 GiB RAM, 80 GiB local disk |
| Named snapshot | `vision-workspace-runtime`, maximum one project snapshot |
| Persistent volume | `vision-lab-artifacts-20260923`, mounted at `/persist`, subpath `lab` |
| Auto-stop | Disabled (`0`) for continuous use |
| Wall-clock TTL | Not set |
| GPU lifecycle | Ephemeral: stopping/deleting the worker destroys local disk |
| Future creation | Manager reuses the fixed name and refuses a second project sandbox |
| Per-attempt cloud launcher | Disabled by `allow_benchmark_worker_creation = false` |

A continuously running GPU sandbox preserves its working environment while it
stays alive. Daytona does not guarantee GPU stop/start persistence. The snapshot
lets us recreate the installed environment; the independent volume keeps the
files explicitly saved there. Neither is a live memory/process backup.

Management actions verify exact resource IDs and names recorded in local
`runs/daytona/sandbox.json`, `snapshot.json` and `volume.json`; sandbox labels are
checked as well. Similar names or labels alone are insufficient. Unregistered or
mismatching existing resources are left alone. The manager does not perform
account-wide cleanup. Keep these local registration files when moving the project.

Approximate published cost for this running configuration is $1.92/hour, or
$46/day. Model APIs and persistent storage are additional. This is an estimate,
not a spending cap. We have not created a CPU coordinator or another GPU worker.

## Everyday commands

Run from the repository root. This optional alias is local to your shell:

```bash
alias vday='runs/daytona/venv/bin/python infra/daytona/manage.py'

vday status
runs/daytona/venv/bin/python -m infra.daytona.doctor
vday exec --command 'nvidia-smi'
vday exec --command 'ls -lah /persist'
```

`provision` reuses the existing named workspace; it does not create a worker for
each command. `build` reuses the existing active named snapshot. Neither command
silently rotates names or grows a pool.

```bash
# Initial setup / deliberate recovery after worker deletion:
vday build
vday provision
vday sync
vday check --name workspace-health
vday logs --name workspace-health
```

Snapshots inherit their original resource configuration. Changing CPU/RAM in
TOML does not resize an existing snapshot or workspace. A dependency change is
normally installed in the live workspace first. Replacing the single snapshot
should be a deliberate maintenance operation; the manager will not create a
second named project snapshot to bypass the limit.

## Where files go

| Path inside the workspace | Use |
|---|---|
| `/workspace/vision` | Installed working copy of the source |
| `/opt/venvs/science` | TensorFlow, StarDist, OpenCV, Harbor and controller packages |
| `/opt/venvs/torch` | Separate PyTorch / Cellpose environment |
| `/opt/checkpoints` | Local model cache for inference |
| `/persist/setup` | Source archive, manifest, setup and health reports |
| `/persist/checkpoints` | Durable copies of model weights |
| `/persist/artifacts` | Saved runs, results and traces |
| `/persist/scratch` | Explicitly disposable files |

Use `/opt/venvs/science/bin/python-gpu` for TensorFlow/StarDist. It supplies the
correct CUDA library paths. For PyTorch use
`env -u LD_LIBRARY_PATH /opt/venvs/torch/bin/python` to keep the environments separate.
Copy new weights and outputs to `/persist` as they are produced; unsaved local
files are lost if the GPU worker is stopped. A mounted-volume check is required:
a directory called `/persist` alone is not evidence of durability.

## Cleaning without replacing the box

```bash
vday clean          # lists scratch entries; deletes nothing
vday clean --apply  # removes only /persist/scratch contents
```

Cleanup preserves source, environments, model weights, saved artifacts, the
snapshot and the volume. It does not stop the GPU. The ordinary `stop` command
refuses GPU sandboxes because GPU stop deletes their local filesystem. `delete`
is an explicit destructive operation on this workspace only; it keeps the
separately mounted volume and named snapshot.

For a long command use an asynchronous session. Have the program write its
completed output files into the persistent artifacts directory:

```bash
vday run --name experiment-001 --command 'YOUR_COMMAND'
vday logs --name experiment-001
```

Use a unique session name, not a new sandbox name. Provider keys are injected at
execution time through structured SDK environment arguments; source sync and
snapshot builds exclude `.env`. Do not bake credentials into a snapshot.

The mounted volume is object-backed FUSE storage. In the live check, a log held
open by its writer could not be read concurrently, while closed files read back
correctly. Setup commands therefore write live logs to `/tmp/vision-bootstrap.log`
or `/tmp/vision-health.log` and copy completed logs into `/persist/setup`.
For live setup progress, use `vday exec --command 'tail -n 20 /tmp/vision-health.log'`.

## Access checks and the earlier experiment

The updated key passed the required permission checks: `write:sandboxes`,
`write:snapshots`, `read:volumes` and `write:volumes`. The checker uses the current
key endpoint and emits permission names only, never the returned key value.
It saves `runs/daytona/persistence-check.json`.

The old 450-attempt cloud experiment is incomplete and its coordinator is no
longer running. Key rotation invalidated its cached key, and its worker-per-attempt
architecture conflicts with the new single-workspace policy. Its completed
results remain unchanged. The remaining GPU worker's artifacts were downloaded,
checksum-verified and preserved in `runs/daytona/key-rotation-recovery/` before
that worker was deleted. The recovery record is
`runs/daytona/key-rotation-recovery.json`.

Do not resume the frozen old launcher directly: it would allocate fresh workers.
The current launcher rejects that architecture under the workspace policy.
A future benchmark on this reused workspace needs a separately declared protocol
and isolation/reset controls; retaining files between attempts cannot be silently
substituted for the old fresh-worker experiment. Verifier labels and previous
answers must not be visible to an evaluated agent.

The separate repaired 12-image full-harness repeat runs in local Docker, with
its own frozen inputs and source. It does not allocate Daytona resources.

## References

- [Daytona persistence and GPU lifecycle](https://www.daytona.io/docs/en/persistence/)
- [Snapshots](https://www.daytona.io/docs/en/snapshots/)
- [Volumes](https://www.daytona.io/docs/en/volumes/)
- [API-key permissions](https://www.daytona.io/docs/api-keys)
- [Pricing](https://www.daytona.io/pricing)
