"""Harbor runs the exact CLI; task references exist only in a separate verifier."""

import os
import shlex

from harbor.agents.base import AgentCapabilities
from harbor.agents.installed.base import BaseInstalledAgent

from evals.atif import export


class ResearchExecutionAgent(BaseInstalledAgent):
    capabilities = AgentCapabilities(atif=True)

    def __init__(self, *args, mode="full", development_replay=False, **kwargs):
        super().__init__(*args, **kwargs)
        if mode not in ("vanilla", "full"):
            raise ValueError("Unknown arm")
        self.mode = mode
        self.development_replay = development_replay is True or str(development_replay).lower() == "true"

    @staticmethod
    def name():
        return "research-execution"

    def version(self):
        return "0.1.0"

    async def install(self, environment):
        await self.exec_as_agent(environment,
            command="python -m vision_harness.research_execution.cli --help", cwd="/app")

    async def run(self, instruction, environment, context):
        command = ["python", "-m", "vision_harness.research_execution.cli", "--mode", self.mode,
                   "--query", instruction.strip(), "--output", "/logs/agent/run"]
        if self.development_replay:
            command.extend(["--development-prefix", "/data/development-prefix"])
        env = {k: os.environ[k] for k in ("OPENAI_API_KEY", "JEV_API_KEY", "TYPESAFE_API_KEY") if k in os.environ}
        await self.exec_as_agent(environment, command=shlex.join(command), cwd="/app", env=env)
        await self.exec_as_agent(environment, command="cp /logs/agent/run/answer.json /output/answer.json")
        await self.exec_as_agent(environment,
            command="if test -f /logs/agent/run/labels.npz; then cp /logs/agent/run/labels.npz /output/labels.npz; fi")

    def populate_context_post_run(self, context):
        folder = self.logs_dir / "run"
        if (folder / "events.jsonl").exists():
            trajectory = export(folder, self.logs_dir / "trajectory.json")
            context.n_input_tokens = trajectory.final_metrics.total_prompt_tokens
            context.n_output_tokens = trajectory.final_metrics.total_completion_tokens
            context.metadata = {"mode": self.mode, "protocol": "research-execution-0.1"}
