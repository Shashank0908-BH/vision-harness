# Single-workspace GPU repeat

This runner uses only the registered `vision-workspace` sandbox, ID
`7dcd09f3-b2b9-4c9f-9a3b-96772eb042ee`. It never calls sandbox, snapshot or volume
creation. The legacy per-attempt Daytona launcher remains disabled.

The experiment repeats all 12 images from `test-repair01`, three full-harness
attempts per image. The original 36 vanilla controls are copied without filtering,
including their failed attempt. This is a post-hoc engineering repair comparison
on an inspected cohort, not a new held-out result. GPU hardware, package versions,
available model environments and isolation differ from the CPU run. Scientific
method selection remains the harness's job.

Limits remain 1,500 seconds, 48 controller calls, two execution rounds, and 420
seconds per Codex execution. Only one trial runs at a time. No outcome retries.
Missing answers score zero for the primary within-10%-error metric. Incomplete
JEV reviews are shown separately from completed chains and approved answers.

## Files

| File | Responsibility |
| --- | --- |
| `common.py` | Fixed experiment names, paths and hash utilities. |
| `prepare.py` | Verify the CPU repair source freeze; copy the same input images, references, prompts and vanilla controls; freeze GPU code and protocol. |
| `environment.py` | Harbor adapter using Bubblewrap inside the existing workspace. Fresh trial files and PID/mount/IPC namespaces; read-only code, packages and weights; no parent results or credentials mounted. |
| `agent.py` | Harbor agent invoking the repaired controller and exporting its existing ATIF trace. A separate plumbing agent makes no provider calls. |
| `entry.py` | Supply measured GPU inventory and per-trial installation instructions; retain the repaired controller's default budgets. |
| `smoke.py` | Check hidden paths, read-only weights, TensorFlow/PyTorch CUDA execution, and dummy output transfer. It never predicts a benchmark answer. |
| `runner.py` | Remote serial Harbor coordinator, one-workspace lock, freeze checks, mandatory plumbing gate, progress, persistent checkpoints and final report. |
| `client.py` | Deploy, start, inspect and download using the existing workspace's exact ownership checks. Provider keys travel through the SDK environment argument, never command text or files. |
| `test_environment.py` | Transfer-boundary, mount-isolation and offline-verifier checks. |
| `auth_guard.py` | Stop after a recorded authentication failure and block subsequent provider calls, without dropping poor scientific outcomes. |
| `test_auth_guard.py` | Verify that invalid credentials stop the serial queue while timeouts and low-confidence answers remain scored attempts. |
| `health.py` | Small Astra and JEV requests from the actual GPU workspace before the coordinator launches; saves credential-free health evidence. |

## Historical experiment commands (from repository root)

The cohort is complete. These commands describe its original deployment; they
are not fresh-clone onboarding. `prepare.py` requires locally restored frozen
inputs/controls and the original CPU-repair source fingerprint. Current source
contains later operational fixes and intentionally fails that fingerprint check.
For team setup and future experiment boundaries, see
[the handoff](../../../docs/team-handoff.md). Do not overwrite this completed run.

```sh
# Once only; refuses to overwrite the frozen experiment.
.venv/bin/python -m infra.daytona.reuse.prepare
runs/daytona/venv/bin/python -m infra.daytona.reuse.client deploy
runs/daytona/venv/bin/python -m infra.daytona.reuse.client start

# Read progress or download traces/results.
runs/daytona/venv/bin/python -m infra.daytona.reuse.client status
runs/daytona/venv/bin/python -m infra.daytona.reuse.client pull
```

The coordinator runs remotely and survives a laptop disconnect. A second start
is rejected. After a coordinator failure, inspect the saved job before deciding
how to continue; this runner deliberately does not silently repeat attempts.

The current restart is `reuse-gpu-repair02`; `reuse-gpu-repair01` remains preserved
with four authentication-failed attempts. The restart repeats all 36 attempts.
The scientific controller and its budgets are unchanged; the new coordinator
stops the queue if authentication fails. Provider health calls are outside the
benchmark and their outputs cannot enter an agent's filesystem.

Live files reside under `/root/vision-benchmarks/reuse-gpu-repair02`, on the GPU
workspace's local disk. Closed trial archives, hashes, status and reports are
copied to `/persist/artifacts/reuse-gpu-repair02`. Live SQLite/log writers never
write directly to the object-backed volume. The frozen inputs archive on that
volume includes hidden references for recovery; it is not mounted into agents.

Each agent gets only its current inputs and private writable directories. The
trusted separate verifier gets its reference after the agent command finishes
and has no network or provider keys. This is process/filesystem isolation on
shared hardware, not a fresh VM for every task. Internet research still carries
the usual public-benchmark exposure limitation.

The GPU remains running after the cohort, as requested. Workspace cleanup only
targets its designated scratch area; results and checkpoints are retained.

The adapter follows the upstream [Harbor custom-environment interface](https://github.com/harbor-framework/harbor/blob/main/src/harbor/environments/base.py)
and [Bubblewrap mount and process isolation](https://github.com/containers/bubblewrap).
