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
from .preflight import commands as execution_commands
from .preflight import validate_report


def execute(plan, packet, folder, settings, trace, timeout):
    if not Path("/.dockerenv").exists():
        raise RuntimeError("Generated scientific code may run only in the isolated Docker task")
    folder.mkdir(parents=True, exist_ok=True)
    program = folder / "approved.py"
    program.write_text(plan.python_program)
    frozen_hash = program_hash(plan.python_program)
    write_json(folder / "approved-plan.json", plan.model_dump())
    write_json(folder / "outcome-schema.json", ExecutionOutcome.model_json_schema())
    commands = execution_commands(plan, packet.get("environment") or {}, folder)
    if commands:
        # This stdlib-only helper can run in either isolated scientific venv.
        (folder / "import-preflight.py").write_text(Path(__file__).with_name("preflight.py").read_text())
        write_json(folder / "execution-commands.json", commands)
    prompt = {
        "stage": "execute_approved_plan", "stage_packet": packet,
        "approved_plan": plan.model_dump(), "program_sha256": frozen_hash,
        "execution_commands": commands,
        "instructions": [
            "First run execution_commands.install if present, then approved setup commands in order. "
            "Stop on the first nonzero exit and return needs_replan; "
            "do not run the scientific program after a failed setup or invent an unapproved package installation.",
            "When execution_commands is supplied, run its exact preflight command after setup. "
            "Only if it exits 0, run its exact program command. Both use the selected interpreter and package path. "
            "Do not edit the preflight helper or its report. Without execution_commands, use the plan's declared Python launcher.",
            "The Python program is frozen. Do not edit it, change scientific parameters or substitute methods.",
            "Read stderr and report needs_replan if the program fails. Propose a specific repair for controller scoring.",
            "Report the actual Python program exit code separately from Codex's own exit code.",
            "Your job is execution and artifact production, not biological acceptance. Do not perform a second visual approval gate.",
            "When the unchanged program exits 0 and writes labels.npz plus execution-metadata.json, return executed. "
            "Qualitative doubts about missed, split or border nuclei are nonblocking concerns in failure_details; "
            "the controller will independently inspect the mask and pass the evidence to Jev. Never discard the outputs.",
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
    if commands and outcome.program_exit_code == 0:
        validate_report(folder / "import-preflight.json", plan)
    validate_handoff(outcome, folder, trace)
    return outcome


def validate_handoff(outcome, folder, trace):
    artifacts = all((folder / name).is_file() and not (folder / name).is_symlink()
                    for name in ("labels.npz", "execution-metadata.json"))
    if (not outcome.program_executed_unchanged or outcome.program_exit_code != 0
            or not artifacts or outcome.status == "execution_error"):
        raise RuntimeError("Execution needs replan: " + outcome.model_dump_json())
    if outcome.status == "needs_replan":
        # Do not rewrite the executor's concern as approval. The next controller
        # step validates geometry/IDs/metadata, then sends these concerns to Jev.
        trace.emit("execution_concerns_forwarded", {
            "plan_id": outcome.plan_id, "concerns": outcome.failure_details,
            "suggested_repair": outcome.suggested_repair,
            "independent_artifact_validation_pending": True})
