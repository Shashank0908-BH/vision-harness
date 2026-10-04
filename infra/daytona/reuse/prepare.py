"""Freeze the same 12-image repair cohort for the single-workspace GPU repeat."""

import json
import shutil
import tarfile
from datetime import datetime, timezone

from evals.research_execution.prepare import ROOT, source_snapshot
from infra.daytona.reuse.common import LOCAL, NAME, REMOTE, REPORT, SPLIT, hashes, write


def prepare():
    if LOCAL.exists():
        raise ValueError(f"Already frozen: {LOCAL}; do not overwrite an experiment")
    original = ROOT / "reports/research-execution-20260922/test-repair01"
    selection = json.loads((original / "selection.json").read_text())
    if source_snapshot() != selection["source_snapshot"]:
        raise ValueError("Controller changed since the CPU repair freeze")
    paths = [ROOT / p for p in source_snapshot()]
    paths += list((ROOT / "infra/daytona/reuse").glob("*.py"))
    paths += [ROOT / "infra/daytona/run_harness.py"]
    for source in set(paths):
        target = LOCAL / "frozen" / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    write(LOCAL / "source-manifest.json", hashes(LOCAL / "frozen"))
    for split, previous in (("test", "test-repair01"), ("plumbing", "dev-repair02")):
        for task in sorted((ROOT / "evals/tasks/generated/research-execution" / previous).glob("image-*")):
            target = LOCAL / "tasks" / split / task.name
            for name in ("environment/input.tif", "environment/input.png", "instruction.md"):
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(task / name, path)
            shutil.copytree(task / "tests", target / "tests")
            spec = (task / "task.toml").read_text().replace('user = "researcher"', 'user = "root"')
            spec = spec.replace("cpus = 2", "cpus = 8").replace("memory_mb = 6144", "memory_mb = 32768")
            spec = spec.replace("storage_mb = 12000", "storage_mb = 81920\ngpus = 1")
            spec += '\n[verifier.environment]\ncpus = 8\nmemory_mb = 32768\nstorage_mb = 81920\ngpus = 0\nnetwork_mode = "no-network"\n'
            (target / "task.toml").write_text(spec)
    write(LOCAL / "task-manifest.json", hashes(LOCAL / "tasks"))
    selection.update(frozen_at=datetime.now(timezone.utc).isoformat(),
        split="GPU repeat of previously inspected official test cohort; post-hoc repair study",
        execution_platform="One reused RTX 4090 workspace; serial private PID/mount namespaces; separate offline verifier",
        new_full_attempts=36, new_vanilla_attempts=0,
        package_policy="Pinned GPU scientific environments; read-only shared weights; fresh per-trial optional installs",
        limits_note="Same CPU-repair policy limits, 1500 s / 48 controller calls / 2 rounds / 420 s Codex per round",
        supersedes_interrupted_run="reuse-gpu-repair01; all four authentication failures preserved; all 36 full attempts freshly repeated",
        authentication_policy="Stop the cohort after a provider authentication failure; preserve the failed attempt and report remaining trials as unrun",
        comparisons_note="Existing vanilla controls reused, including their failure. GPU, library versions, resource allocation, isolation and available models differ from CPU; this is a deployment comparison, not an isolated GPU-effect claim.",
        limitations=[x for x in selection["limitations"] if "CPU-only" not in x] + ["same inspected cohort; no fresh vanilla calls", "shared GPU kernel/hardware, with isolated files and processes"])
    selection["policy"]["version"] = "research-execution-reuse-gpu-repair01"
    write(LOCAL / REPORT / "selection.json", selection)
    shutil.copyfile(original / "cohort.json", LOCAL / REPORT / "cohort.json")
    # Controls are immutable copies for reporting, never visible in agent mounts.
    baseline = ROOT / "jobs/research-execution-test-awake96-vanilla"
    destination = LOCAL / "jobs" / f"research-execution-{SPLIT}-vanilla"
    for trial in baseline.glob("*/config.json"):
        for name in ("config.json", "result.json", "verifier/grading.json", "agent/run/answer.json", "agent/run/events.jsonl"):
            source = trial.parent / name
            if source.exists():
                target = destination / trial.parent.name / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    for split in ("plumbing", "test"):
        config = {"job_name": "plumbing" if split == "plumbing" else f"research-execution-{SPLIT}-full",
            "jobs_dir": str(REMOTE / "jobs"), "n_attempts": 1 if split == "plumbing" else 3,
            "n_concurrent_trials": 1, "quiet": True, "retry": {"max_retries": 0},
            "environment": {"import_path": "infra.daytona.reuse.environment:WorkspaceEnvironment", "delete": True},
            "agents": [{"import_path": "infra.daytona.reuse.agent:" + ("PlumbingAgent" if split == "plumbing" else "WorkspaceAgent"),
                        "model_name": "gpt-6-astra"}], "datasets": [{"path": str(REMOTE / "tasks" / split)}]}
        write(LOCAL / f"{split}-config.json", config)
    write(LOCAL / "protocol.json", {"name": NAME, "split": SPLIT, "remote": str(REMOTE),
        "workspace_id": "7dcd09f3-b2b9-4c9f-9a3b-96772eb042ee", "planned_attempts": 36,
        "selection": str(REPORT / "selection.json"), "plumbing_provider_calls": 0})
    provenance = LOCAL / "provenance"
    provenance.mkdir()
    shutil.copyfile(ROOT / "runs/daytona/workspace-validation.json", provenance / "workspace-validation.json")
    for name in ("science.lock", "torch.lock"):
        shutil.copyfile(ROOT / "infra/daytona" / name, provenance / name)
    archive = LOCAL.with_suffix(".tar.gz")
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(LOCAL, arcname=NAME)
    print(json.dumps({"archive": str(archive), "bytes": archive.stat().st_size, "full_attempts": 36}))


if __name__ == "__main__":
    prepare()
