"""Remote Harbor coordinator: single queue, durable closed-file checkpoints."""

import argparse
import asyncio
import fcntl
import hashlib
import json
import os
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from harbor.job import Job
from harbor.models.job.config import JobConfig

from infra.daytona.reuse.auth_guard import AuthenticationGuard
from infra.daytona.reuse.common import REPORT, SPLIT, hashes, write


def snapshot(run, stage):
    rows = []
    job = run / "jobs" / f"research-execution-{SPLIT}-full"
    for path in sorted(job.glob("*/config.json")):
        folder = path.parent
        result = json.loads((folder / "result.json").read_text()) if (folder / "result.json").exists() else {}
        answer = json.loads((folder / "agent/run/answer.json").read_text()) if (folder / "agent/run/answer.json").exists() else {}
        live_stage = None
        locator = folder / "agent/workspace-location.json"
        if locator.exists() and not result.get("finished_at"):
            private = Path(json.loads(locator.read_text())["private_root"])
            events = private / "logs/agent/run/events.jsonl"
            if events.exists():
                for line in events.read_text().splitlines():
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # A concurrent writer can leave the last line partial.
                    if event.get("kind") == "stage":
                        live_stage = event["data"]["stage"]
        rows.append({"trial": folder.name, "finished": bool(result.get("finished_at")),
            "error": (result.get("exception_info") or {}).get("exception_type"),
            "status": answer.get("status"), "review_status": answer.get("review_status"), "active_stage": live_stage})
    value = {"stage": stage, "updated_at": datetime.now(timezone.utc).isoformat(), "coordinator_pid": os.getpid(),
        "planned": 36, "finished": sum(r["finished"] for r in rows),
        "running": sum(not r["finished"] for r in rows), "trials": rows}
    write(run / "status.json", value)
    return value


def checkpoint(run):
    persistent = Path("/persist/artifacts") / run.name
    persistent.mkdir(parents=True, exist_ok=True)
    registry = run / "checkpointed.json"
    saved = json.loads(registry.read_text()) if registry.exists() else {}
    for result in (run / "jobs").glob("*/*/result.json"):
        # Reused controls are already preserved in frozen-inputs.tar.gz. Do not
        # rewrite 36 tiny control archives to the object-backed volume.
        if result.parent.parent.name.endswith("-vanilla"):
            continue
        folder = result.parent
        relative = str(folder.relative_to(run))
        if relative in saved or not json.loads(result.read_text()).get("finished_at"):
            continue
        archive = run / (folder.name + ".tar.gz")
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(folder, arcname=relative)
        target = persistent / archive.name
        shutil.copyfile(archive, target)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Persistent checkpoint hash mismatch")
        saved[relative] = {"archive": str(target), "sha256": digest}
        write(registry, saved)
        archive.unlink()
    for source in [run / "status.json", registry, run / "authentication-stop.json", *list((run / REPORT).glob("*"))]:
        if source.is_file():
            shutil.copyfile(source, persistent / source.name)


def report(run):
    from evals.research_execution import report as reporting
    reporting.ROOT = run
    reporting.REPORT = run / "reports/research-execution-20260922"
    reporting.collect(SPLIT)
    page = run / REPORT / "index.html"
    page.write_text(page.read_text().replace("Linux CPU execution:", "RTX 4090 GPU repeat with reused vanilla controls:"))


async def job(run, split):
    config = JobConfig.model_validate_json((run / f"{split}-config.json").read_text())
    if config.n_concurrent_trials != 1 or config.retry.max_retries != 0:
        raise ValueError("Exactly one concurrent trial, no whole-trial retries")
    if (config.jobs_dir / config.job_name).exists():
        raise ValueError("Job already exists; never silently rerun outcomes")
    experiment = await Job.create(config)
    guard = AuthenticationGuard(config.jobs_dir / config.job_name, run)
    experiment.on_trial_started(guard.on_start)
    experiment.on_trial_ended(guard.on_end)
    pending = asyncio.create_task(experiment.run())
    while not pending.done():
        await asyncio.wait({pending}, timeout=45)
        snapshot(run, split)
        checkpoint(run)
    await pending


async def main(run):
    run = run.resolve()
    if not os.path.ismount("/persist"):
        raise RuntimeError("Persistent volume must be mounted")
    lock = (Path("/root/vision-benchmarks") / "workspace-run.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for manifest, folder in (("source-manifest.json", "frozen"), ("task-manifest.json", "tasks")):
        if hashes(run / folder) != json.loads((run / manifest).read_text()):
            raise ValueError("Frozen code or inputs changed")
    os.environ["VISION_FROZEN_SOURCE"] = str(run / "frozen")
    os.chdir(run / "frozen")
    try:
        await job(run, "plumbing")
        proofs = list((run / "jobs/plumbing").glob("*/agent/plumbing.json"))
        grades = list((run / "jobs/plumbing").glob("*/verifier/grading.json"))
        if len(proofs) != 1 or len(grades) != 1:
            raise RuntimeError("Plumbing must prove isolated GPU execution and hidden verification")
        proof, grade = json.loads(proofs[0].read_text()), json.loads(grades[0].read_text())
        if not proof.get("isolated") or not grade["answered"] or grade["count"] != 0 or grade["expected"] <= 0:
            raise RuntimeError("Plumbing proof or dummy-answer transfer failed")
        snapshot(run, "plumbing_passed")
        checkpoint(run)
        await job(run, "test")
        report(run)
        snapshot(run, "complete")
        checkpoint(run)
    except BaseException as error:
        snapshot(run, "blocked_authentication" if (run / "authentication-stop.json").exists()
                 else "stopped_" + type(error).__name__)
        checkpoint(run)
        raise
    finally:
        lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    asyncio.run(main(parser.parse_args().run))
