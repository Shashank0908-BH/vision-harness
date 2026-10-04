"""Actual Codex CLI execution inside the task's externally isolated container."""

import json
import os
import signal
import subprocess
import time
from pathlib import Path

from ..config import require_key
from ..tracing import redact, write_json
from .contracts import ExecutionOutcome
from .planning import program_hash


def execute(plan, packet, folder, settings, trace, timeout):
    if not Path("/.dockerenv").exists():
        raise RuntimeError("Generated scientific code may run only in the isolated Docker task")
    folder.mkdir(parents=True, exist_ok=True)
    program = folder / "approved.py"
    program.write_text(plan.python_program)
    frozen_hash = program_hash(plan.python_program)
    write_json(folder / "approved-plan.json", plan.model_dump())
    write_json(folder / "outcome-schema.json", ExecutionOutcome.model_json_schema())
    prompt = {
        "stage": "execute_approved_plan", "stage_packet": packet,
        "approved_plan": plan.model_dump(), "program_sha256": frozen_hash,
        "instructions": [
            "Execute the provided setup commands and then python approved.py in this work directory.",
            "The Python program is frozen. Do not edit it, change scientific parameters or substitute methods.",
            "Read stderr and report needs_replan if the program fails. Propose a specific repair for controller scoring.",
            "Do not search for images, benchmark answers, labels, counts or source dataset identities.",
            "Do not access credentials, /proc, other processes, host paths, Docker or any verifier.",
            "Do not print environment variables. Do not make unrelated files or commands.",
            "Use local /opt/checkpoints/stardist if the approved plan calls for that pretrained checkpoint.",
            "Record executed setup actions, exact output paths and factual failure details in the final JSON.",
        ],
    }
    command = ["codex", "exec", "--ignore-user-config", "--ephemeral", "--json",
               "--skip-git-repo-check", "--sandbox", "danger-full-access",
               "--model", settings.models.astra,
               "-c", f'model_reasoning_effort="{settings.models.reasoning_effort}"',
               "-c", 'shell_environment_policy.inherit="core"',
               "--output-schema", str(folder / "outcome-schema.json"),
               "--output-last-message", str(folder / "outcome.json"), "-"]
    # No provider key is placed in argv, task configuration, image, or output files.
    environment = {k: v for k, v in os.environ.items()
                   if k not in ("OPENAI_API_KEY", "JEV_API_KEY", "TYPESAFE_API_KEY")}
    environment["CODEX_API_KEY"] = require_key("OPENAI_API_KEY")
    call_id = trace.call("astra-codex", "execute_approved_plan", {
        "model": settings.models.astra, "command": command, "packet": prompt,
        "timeout_seconds": timeout, "external_isolation": "task-only Docker container"})
    started = time.monotonic()
    timed_out = False
    process = subprocess.Popen(command, cwd=folder, env=environment, text=True,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(json.dumps(prompt), timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
    (folder / "codex-events.jsonl").write_text(redact(stdout))
    (folder / "codex-stderr.txt").write_text(redact(stderr))
    usage = {"input_tokens": 0, "output_tokens": 0}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        trace.emit("codex_event", event)
        if event.get("type") == "turn.completed":
            for name in usage:
                usage[name] += event.get("usage", {}).get(name, 0)
    trace.response(call_id, {"model": settings.models.astra, "usage": usage,
                            "returncode": process.returncode, "timed_out": timed_out},
                   time.monotonic() - started)
    if timed_out:
        raise TimeoutError("Codex execution exceeded its round time budget")
    if process.returncode:
        raise RuntimeError(f"Codex exit {process.returncode}: {redact(stderr)[-2000:]}")
    outcome = ExecutionOutcome.model_validate_json((folder / "outcome.json").read_text())
    unchanged = program_hash(program.read_text()) == frozen_hash
    write_json(folder / "program-integrity.json", {"sha256": frozen_hash,
                                                  "unchanged_after_execution": unchanged,
                                                  "semantic_enforcement": "prompt plus artifact checks; not a formal sandbox policy"})
    if not unchanged or outcome.plan_id != plan.plan_id:
        raise ValueError("Execution changed the approved program or returned another plan ID")
    if outcome.status != "executed" or not outcome.program_executed_unchanged:
        raise RuntimeError("Execution needs replan: " + outcome.model_dump_json())
    return outcome
