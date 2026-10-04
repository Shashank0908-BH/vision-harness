"""Export observable events to Harbor ATIF; no private reasoning is fabricated."""

import json
import os
from pathlib import Path

from harbor.models.trajectories import Agent, FinalMetrics, Metrics, Observation, Step, Trajectory
from harbor.utils.trajectory_validator import TrajectoryValidator

from vision_harness.tracing import write_json


def export(directory: Path, output: Path):
    manifest = json.loads((directory / "manifest.json").read_text())
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    steps, tool_calls = [], {}
    input_tokens = output_tokens = 0
    for event in events:
        kind, data = event["kind"], event["data"]
        number = len(steps) + 1
        base = dict(
            step_id=number,
            timestamp=event["time"],
            source="agent",
            message=f"{kind}: " + json.dumps(data),
            extra={"event_kind": kind},
        )
        if kind == "input":
            original = directory / "artifacts/original.png"
            base.update(
                source="user",
                message=[
                    {"type": "text", "text": data["question"]},
                    {
                        "type": "image",
                        "source": {
                            "path": os.path.relpath(original, output.parent),
                            "media_type": "image/png",
                        },
                    },
                ],
            )
        elif kind == "tool_started":
            tool_calls[data["call_id"]] = len(steps)
            base.update(
                llm_call_count=0,
                tool_calls=[
                    {
                        "tool_call_id": data["call_id"],
                        "function_name": data["step"]["tool"],
                        "arguments": data["step"],
                    }
                ],
            )
        elif kind in ("evidence", "tool_error"):
            call_id = data.get("evidence_id", data.get("call_id"))
            if call_id in tool_calls:
                target = steps[tool_calls[call_id]]
                target.observation = Observation.model_validate(
                    {"results": [{"source_call_id": call_id, "content": json.dumps(data)}]}
                )
        elif kind == "call_finished":
            request = json.loads(
                (directory / "calls" / f"{data['call_id']}.request.json").read_text()
            )
            response = json.loads(
                (directory / "calls" / f"{data['call_id']}.response.json").read_text()
            )
            usage = data.get("usage") or {}
            inp, out = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
            input_tokens += inp
            output_tokens += out
            base.update(
                model_name=response.get("model", request.get("model")),
                llm_call_count=1,
                metrics=Metrics(prompt_tokens=inp, completion_tokens=out),
                message=json.dumps({"request": request, "response": response}),
            )
        steps.append(Step(**base))
    trajectory = Trajectory(
        schema_version="ATIF-v1.7",
        session_id=manifest["run_id"],
        agent=Agent(
            name="vision-harness", version="0.1.0", model_name=manifest["config"]["models"]["astra"]
        ),
        steps=steps,
        notes="Observable events only. Offline runs contain deterministic stand-ins, not model inference.",
        extra={"mode": manifest["mode"], "offline": manifest["offline"]},
        final_metrics=FinalMetrics(
            total_prompt_tokens=input_tokens,
            total_completion_tokens=output_tokens,
            total_steps=len(steps),
            extra={"elapsed_seconds": manifest["elapsed_seconds"]},
        ),
    )
    # Revalidate mutated observation fields before serialization.
    trajectory = Trajectory.model_validate(trajectory.model_dump())
    write_json(output, trajectory.to_json_dict())
    validator = TrajectoryValidator()
    if not validator.validate(output):
        raise ValueError(f"Invalid exported trajectory: {validator.get_errors()}")
    return trajectory
