"""Run frozen Harbor jobs and refresh locally durable progress once a minute."""

import argparse
import asyncio
import hashlib
import json
import os
import tomllib
from pathlib import Path

from dotenv import dotenv_values
from harbor.job import Job
from harbor.models.job.config import JobConfig

from infra.daytona.benchmark.collect import collect


async def run_job(run, split):
    config = JobConfig.model_validate_json((run / f"{split}-config.json").read_text())
    job = await Job.create(config)
    print(json.dumps({"stage": "job_started", "split": split, "trials": len(job)}), flush=True)
    pending = asyncio.create_task(job.run())
    while not pending.done():
        done, _ = await asyncio.wait({pending}, timeout=60)
        report = collect(run, split)
        print(json.dumps({"stage": "progress", "split": split,
            "finished": {k: v["completed_attempts"] for k, v in report["arms"].items()}}), flush=True)
        if done:
            break
    await pending
    return collect(run, split)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--skip-canary", action="store_true")
    args = parser.parse_args()
    policy_path = args.env_file.resolve().parent / "infra/daytona/config.toml"
    if policy_path.exists():
        workspace_policy = tomllib.loads(policy_path.read_text())
        if not workspace_policy.get("allow_benchmark_worker_creation", True):
            raise RuntimeError(
                "The project is configured for one reusable workspace. This legacy launcher "
                "creates new agent/verifier sandboxes per attempt and is disabled. "
                "Preserve the existing cohort; use the workspace manager for continuous work."
            )
    run = args.run.resolve()
    # Freeze checking precedes provider calls; parent-thread source can continue changing.
    for manifest, base in (("source-manifest.json", run / "frozen"), ("task-manifest.json", run)):
        for relative, expected in json.loads((run / manifest).read_text()).items():
            if hashlib.sha256((base / relative).read_bytes()).hexdigest() != expected:
                raise ValueError(f"Frozen file changed: {relative}")
    values = dotenv_values(args.env_file)
    for name in ("OPENAI_API_KEY", "JEV_API_KEY", "TYPESAFE_API_KEY", "DAYTONA_API_KEY", "DAYTONA_API_URL"):
        if values.get(name):
            os.environ[name] = values[name]
    for name in ("OPENAI_API_KEY", "JEV_API_KEY", "DAYTONA_API_KEY"):
        if not os.environ.get(name):
            raise ValueError(f"Missing {name}")
    os.chdir(run / "frozen")
    if not args.skip_canary:
        report = await run_job(run, "canary")
        # Gate on transport/runtime health, never on canary accuracy or JEV approval.
        for arm in ("vanilla", "stardist"):
            if report["arms"][arm]["answered"] != 1:
                raise RuntimeError(f"Validation infrastructure canary failed: {arm}; full cohort not started")
        full = next(r for r in report["attempts"] if r["arm"] == "full")
        full_run = run / "jobs/canary" / full["trial"] / "agent/run"
        if not (full_run / "manifest.json").exists():
            raise RuntimeError("Harness process did not start; full cohort not started")
        diagnostic = json.dumps(read_json(full_run / "answer.json")).lower()
        if any(token in diagnostic for token in ("token_invalidated", "invalid_api_key", "authenticationerror", "permissiondeniederror")):
            raise RuntimeError("Provider authentication failed; full cohort not started")
    await run_job(run, "test")
    print(json.dumps({"stage": "complete", "report": str(run / "test-summary.md")}), flush=True)


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else {}


if __name__ == "__main__":
    asyncio.run(main())
