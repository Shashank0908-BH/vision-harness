"""The repaired workflow, unchanged budgets, and a no-provider plumbing canary."""

import os
import shlex

from evals.research_execution.harbor_agent import ResearchExecutionAgent


class WorkspaceAgent(ResearchExecutionAgent):
    async def run(self, instruction, environment, context):
        env = {k: os.environ[k] for k in ("OPENAI_API_KEY", "JEV_API_KEY", "TYPESAFE_API_KEY") if k in os.environ}
        command = ["/opt/venvs/science/bin/python-gpu", "/app/infra/daytona/reuse/entry.py",
                   "--query", instruction.strip(), "--output", "/logs/agent/run"]
        await self.exec_as_agent(environment, command=shlex.join(command), cwd="/app", env=env)
        await self.exec_as_agent(environment, command="cp /logs/agent/run/answer.json /output/answer.json; "
            "if test -f /logs/agent/run/labels.npz; then cp /logs/agent/run/labels.npz /output/labels.npz; fi")


class PlumbingAgent(ResearchExecutionAgent):
    async def run(self, instruction, environment, context):
        # No provider calls and no reference-derived answer; verifies execution,
        # GPU access, output transfer, separate grading, and hidden mount boundaries.
        await self.exec_as_agent(environment,
            command="/opt/venvs/science/bin/python-gpu /app/infra/daytona/reuse/smoke.py", cwd="/app")

    def populate_context_post_run(self, context):
        pass
