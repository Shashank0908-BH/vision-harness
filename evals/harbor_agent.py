"""Harbor adapter: runs the same CLI installed in the task image."""

import os
import shlex

from harbor.agents.base import AgentCapabilities
from harbor.agents.installed.base import BaseInstalledAgent

from .atif import export


class VisionAgent(BaseInstalledAgent):
    capabilities = AgentCapabilities(atif=True)

    def __init__(
        self, *args, mode="full", offline=False, runtime_config="configs/poc.toml", **kwargs
    ):
        super().__init__(*args, **kwargs)
        if mode not in ("vanilla", "tools", "select", "review", "full"):
            raise ValueError("Invalid harness mode")
        self.mode = mode
        self.offline = offline is True or str(offline).lower() == "true"
        self.runtime_config = runtime_config

    @staticmethod
    def name():
        return "vision-harness"

    def version(self):
        return "0.1.0"

    async def install(self, environment):
        # The task image installs the locked runtime; no second implementation is installed here.
        await self.exec_as_agent(environment, command="vision --help", cwd="/app")

    async def run(self, instruction, environment, context):
        command = [
            "vision",
            "run",
            "--image",
            "/data/input.png",
            "--prompt",
            instruction,
            "--mode",
            self.mode,
            "--config",
            self.runtime_config,
            "--output",
            "/logs/agent/run",
        ]
        if self.offline:
            command.append("--offline")
        if self.model_name:
            command.extend(["--model", self.model_name])
        # Secret values are supplied only to this exec call, never job JSON or command arguments.
        env = (
            {
                key: os.environ[key]
                for key in ("OPENAI_API_KEY", "TYPESAFE_API_KEY", "JEV_API_KEY")
                if key in os.environ
            }
            if not self.offline
            else {}
        )
        await self.exec_as_agent(environment, command=shlex.join(command), env=env, cwd="/app")
        await self.exec_as_agent(
            environment, command="cp /logs/agent/run/answer.json /output/answer.json"
        )

    def populate_context_post_run(self, context):
        directory = self.logs_dir / "run"
        if (directory / "events.jsonl").exists():
            trajectory = export(directory, self.logs_dir / "trajectory.json")
            context.n_input_tokens = trajectory.final_metrics.total_prompt_tokens
            context.n_output_tokens = trajectory.final_metrics.total_completion_tokens
            context.metadata = {"mode": self.mode, "offline": self.offline}
