"""Validate complete executable plans before scoring or execution."""

import ast
import hashlib

from ..tracing import write_json
from .contracts import PlanSet


def program_hash(program):
    return hashlib.sha256(program.encode()).hexdigest()


def validate_plans(plans, task, candidates, usage):
    ids = [p.plan_id for p in plans.plans]
    if len(ids) != len(set(ids)) or plans.preferred_plan_id not in ids:
        raise ValueError("Plan IDs must be distinct and preference must name a plan")
    known = {c.candidate_id for c in candidates}
    ready = {u.candidate_id for u in usage.contracts if u.ready_for_trial}
    sources = {s for u in usage.contracts for s in u.source_ids}
    required = {r.requirement_id for r in task.requirements if r.required}
    all_requirements = {r.requirement_id for r in task.requirements}
    for plan in plans.plans:
        if not set(plan.candidate_ids) <= known & ready:
            raise ValueError("Plan uses an unretained or undocumented candidate")
        if not required <= set(plan.covered_requirement_ids) <= all_requirements:
            raise ValueError("Plan does not cover required task parts")
        if not plan.usage_source_ids or not set(plan.usage_source_ids) <= sources:
            raise ValueError("Plan cites unavailable usage documentation")
        for step in plan.steps:
            if not set(step.candidate_ids) <= set(plan.candidate_ids):
                raise ValueError("Step uses a candidate absent from its plan")
            if not set(step.requirement_ids) <= all_requirements:
                raise ValueError("Step refers to an unknown requirement")
        if not plan.python_program.strip():
            raise ValueError("Executable plan has an empty program")
        ast.parse(plan.python_program)


def propose(astra, task, candidates, usage, packet, images, folder):
    context = {"stage_packet": packet, "task": task.model_dump(),
               "candidates": [c.model_dump() for c in candidates], "usage": usage.model_dump()}
    for attempt in range(2):
        plans = astra.structured(
            "Propose two complete competing executable plans. Choose your preference. "
            "Use only ready_for_trial retained candidates. Link every task part to steps. "
            "Write complete Python programs, not pseudocode. Address previous review and execution failures. "
            "Use distinct plan IDs across rounds. Do not run inference before selection.",
            task.query, images, context, PlanSet,
        )
        write_json(folder / f"proposed-plans-{attempt+1}.json", plans.model_dump())
        try:
            validate_plans(plans, task, candidates, usage)
        except (ValueError, SyntaxError) as error:
            if attempt:
                raise
            astra.trace.emit("plan_contract_repair", {"error": str(error), "attempt": attempt+1})
            context["invalid_previous_proposal"] = plans.model_dump()
            context["validation_error_to_repair"] = str(error)
        else:
            write_json(folder / "plans.json", plans.model_dump())
            return plans
    raise AssertionError("Unreachable plan repair state")
