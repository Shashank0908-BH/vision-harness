"""Launch real Harbor jobs without placing credentials in persisted job config."""

import asyncio
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


def launch(path: Path, offline=False):
    from harbor.job import Job
    from harbor.models.job.config import AgentConfig, EnvironmentConfig, JobConfig, TaskConfig

    load_dotenv(Path(".env"), override=True)
    config = tomllib.loads(path.read_text())
    tasks = sorted(Path(config["tasks"]).glob("*/task.toml"))
    if not tasks:
        raise ValueError("No Harbor tasks found. Run vision build-tasks first.")
    if not offline:
        from vision_harness.config import require_key

        require_key("OPENAI_API_KEY")
        if any(mode in ("select", "review", "full") for mode in config["modes"]):
            require_key("TYPESAFE_API_KEY")
    prefix = "offline" if offline else "live"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")

    async def execute():
        failures = []
        for mode in config["modes"]:
            job_config = JobConfig(
                job_name=f"{prefix}-{mode}-{stamp}",
                jobs_dir=Path(config["jobs"]),
                n_attempts=config["repetitions"],
                n_concurrent_trials=config["concurrency"],
                environment=EnvironmentConfig(type="docker"),
                agents=[
                    AgentConfig(
                        import_path="evals.harbor_agent:VisionAgent",
                        model_name=config["model"],
                        kwargs={
                            "mode": mode,
                            "offline": offline,
                            "runtime_config": config.get("runtime_config", "configs/poc.toml"),
                        },
                    )
                ],
                tasks=[TaskConfig(path=t.parent.resolve()) for t in tasks],
            )
            job = await Job.create(job_config)
            result = await job.run()
            print(
                f"Completed {job_config.job_name}; results in {job.job_dir if hasattr(job, 'job_dir') else config['jobs']}"
            )
            if result.stats.n_errored_trials:
                failures.append((mode, result.stats.n_errored_trials))
        if failures:
            raise RuntimeError(
                f"All modes attempted; errored trials by mode: {failures}. Inspect job results."
            )

    asyncio.run(execute())
