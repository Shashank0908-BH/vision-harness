"""Three arms in fresh Harbor-managed Daytona containers; no reference upload."""

import os
import shlex

from harbor.agents.base import AgentCapabilities
from harbor.agents.installed.base import BaseInstalledAgent

from evals.atif import export


class CohortAgent(BaseInstalledAgent):
    capabilities = AgentCapabilities(atif=True)

    def __init__(self, *args, mode="full", **kwargs):
        super().__init__(*args, **kwargs)
        if mode not in ("vanilla", "stardist", "full"):
            raise ValueError("Unknown arm")
        self.mode = mode

    @staticmethod
    def name():
        return "vision-daytona-cohort"

    def version(self):
        return "1.0.0"

    async def install(self, environment):
        # Fail within seconds if the cloud toolbox cannot perform Harbor setup.
        bootstrap = await self.exec_as_root(environment, command="id -u", timeout_sec=30)
        if bootstrap.return_code or bootstrap.stdout.strip() != "0":
            raise RuntimeError("Daytona toolbox must bootstrap Harbor as root")
        source = environment.environment_dir
        await environment.upload_dir(source / "app", "/app")
        for name in ("input.tif", "input.png"):
            await environment.upload_file(source / name, f"/data/{name}")
        result = await self.exec_as_root(environment,
            command="chown -R researcher:researcher /app /data /output /logs/agent /work", timeout_sec=30)
        if result.return_code:
            raise RuntimeError("Trial directory ownership setup failed")
        identity = await self.exec_as_agent(environment, command="id -u", timeout_sec=30)
        if identity.return_code or identity.stdout.strip() != "1000":
            raise RuntimeError("Model execution must run as unprivileged researcher (UID 1000)")
        result = await self.exec_as_agent(environment,
            command="/opt/venvs/science/bin/python-gpu -c 'import vision_harness; import tensorflow; import stardist'",
            cwd="/app", timeout_sec=120)
        if result.return_code:
            raise RuntimeError("Scientific imports failed")

    async def run(self, instruction, environment, context):
        if self.mode == "stardist":
            command = ["/opt/venvs/science/bin/python-gpu", "-m", "infra.daytona.benchmark.stardist",
                       "--output", "/logs/agent/run", "--query", instruction.strip()]
            provider_env = {}
        else:
            command = ["/opt/venvs/science/bin/python-gpu", "infra/daytona/run_harness.py",
                       "--mode", self.mode, "--query", instruction.strip(),
                       "--raw", "/data/input.tif", "--preview", "/data/input.png",
                       "--output", "/logs/agent/run", "--max-seconds", "7200",
                       "--max-provider-calls", "96", "--max-rounds", "4",
                       "--codex-timeout-seconds", "1200"]
            names = ("OPENAI_API_KEY",) if self.mode == "vanilla" else (
                "OPENAI_API_KEY", "JEV_API_KEY", "TYPESAFE_API_KEY")
            provider_env = {k: os.environ[k] for k in names if k in os.environ}
        await self.exec_as_agent(environment, command=shlex.join(command), cwd="/app", env=provider_env)
        await self.exec_as_agent(environment, command=(
            "test ! -L /logs/agent/run/answer.json && cp /logs/agent/run/answer.json /output/answer.json; "
            "if test -f /logs/agent/run/labels.npz && test ! -L /logs/agent/run/labels.npz; "
            "then cp /logs/agent/run/labels.npz /output/labels.npz; fi"))

    def populate_context_post_run(self, context):
        folder = self.logs_dir / "run"
        if (folder / "events.jsonl").exists():
            trajectory = export(folder, self.logs_dir / "trajectory.json")
            context.n_input_tokens = trajectory.final_metrics.total_prompt_tokens
            context.n_output_tokens = trajectory.final_metrics.total_completion_tokens
        context.metadata = {"mode": self.mode, "protocol": "bbbc039-daytona-three-arms-1"}
