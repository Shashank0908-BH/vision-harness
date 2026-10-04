"""Only explicitly registered capabilities may be proposed or executed."""

import tomllib
from pathlib import Path

from ..contracts import CandidatePlan
from .dispatch import validate_step


class Registry:
    def __init__(self, path: Path):
        self.entries = {entry["name"]: entry for entry in tomllib.loads(path.read_text())["tools"]}
        if not set(self.entries) <= {"components", "watershed", "crop", "measure", "stardist"}:
            raise ValueError("Capability registry names a tool without a registered implementation")

    def describe(self) -> list[dict]:
        return list(self.entries.values())

    def validate(self, plan: CandidatePlan, max_steps: int) -> None:
        if len(plan.steps) > max_steps:
            raise ValueError("Plan exceeds configured step limit")
        refs = {"original"}
        seen = {"original"}
        for step in plan.steps:
            if step.tool not in self.entries:
                raise ValueError(f"Tool {step.tool} is disabled")
            if step.step_id in seen:
                raise ValueError("Step IDs must be unique and cannot be original")
            if step.input_ref not in refs:
                raise ValueError("Input must be original or an earlier image-producing step")
            validate_step(step)
            seen.add(step.step_id)
            if step.tool != "measure":
                refs.add(step.step_id)
