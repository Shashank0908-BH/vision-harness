"""Validate complete executable plans before scoring or execution."""

import ast
import hashlib

from ..tracing import write_json
from .contracts import PlanSet
from .preflight import validate_dependencies


def program_hash(program):
    return hashlib.sha256(program.encode()).hexdigest()


def validate_installed_calls(tree, environment):
    if (environment or {}).get("tensorflow_soft_placement_required"):
        predicts = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                       and n.func.attr == "predict_instances" for n in ast.walk(tree))
        disables = any(isinstance(n, ast.Call) and isinstance(n.func, (ast.Attribute, ast.Name))
                       and (n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id)
                       == "set_soft_device_placement"
                       and any(isinstance(a, ast.Constant) and a.value is False
                               for a in n.args + [k.value for k in n.keywords])
                       for n in ast.walk(tree))
        if predicts and disables:
            raise ValueError("Keep TensorFlow soft device placement enabled in the StarDist inference process: "
                             "tf.data includes CPU-only operations. Verify GPU network tensor devices without "
                             "disabling soft placement. A separate strict probe process is allowed.")
    if not (environment or {}).get("verified_local_api", {}).get("stardist"):
        return
    aliases = {"StarDist2D"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "stardist.models":
            aliases.update(a.asname or a.name for a in node.names if a.name == "StarDist2D")

    def is_class(node):
        return ((isinstance(node, ast.Name) and node.id in aliases)
                or (isinstance(node, ast.Attribute) and node.attr == "StarDist2D"))

    instances = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        loader = (isinstance(node.func, ast.Attribute) and node.func.attr == "from_pretrained"
                  and is_class(node.func.value))
        if loader:
            args = node.args + [k.value for k in node.keywords if k.arg == "name_or_alias"]
            if any(isinstance(a, ast.Constant) and a.value == "2D_versatile_fluo" for a in args):
                raise ValueError("Use the supplied local StarDist constructor for the cached checkpoint, not from_pretrained")
        if is_class(node.func) or loader:
            for assignment in ast.walk(tree):
                if isinstance(assignment, ast.Assign) and assignment.value is node:
                    instances.update(t.id for t in assignment.targets if isinstance(t, ast.Name))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "predict_instances" and isinstance(node.func.value, ast.Name)
                and node.func.value.id in instances and any(k.arg == "b" for k in node.keywords)):
            raise ValueError("StarDist 0.9.2 b belongs in predict_kwargs={'b': ...} with sparse=True, not top-level predict_instances")


def validate_plans(plans, task, candidates, usage, environment=None):
    ids = [p.plan_id for p in plans.plans]
    if len(ids) != len(set(ids)) or plans.preferred_plan_id not in ids:
        raise ValueError("Plan IDs must be distinct and preference must name a plan")
    known = {c.candidate_id for c in candidates}
    ready = {u.candidate_id for u in usage.contracts if u.ready_for_trial}
    sources = {s for u in usage.contracts for s in u.source_ids}
    required = {r.requirement_id for r in task.requirements if r.required}
    all_requirements = {r.requirement_id for r in task.requirements}
    for plan in plans.plans:
        validate_dependencies(plan, environment or {})
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
        validate_installed_calls(ast.parse(plan.python_program), environment)


def propose(astra, task, candidates, usage, packet, images, folder):
    context = {"stage_packet": packet, "task": task.model_dump(),
               "candidates": [c.model_dump() for c in candidates], "usage": usage.model_dump()}
    for attempt in range(2):
        plans = astra.structured(
            "Propose two complete competing executable plans. Choose your preference. "
            "Use only ready_for_trial retained candidates. Link every task part to steps. "
            "Write complete Python programs, not pseudocode. Address previous review and execution failures. "
            "Select python_executable from measured python_environments when supplied. Package inventories "
            "are interpreter-specific; declare missing packages as exact package==version pins in install_requirements. "
            "The executor installs these to the selected interpreter's private target, constraining measured versions. "
            "Use setup_commands for additional approved setup checks. An import check is not an installation. "
            "Use distinct plan IDs across rounds. Do not run inference before selection.",
            task.query, images, context, PlanSet,
        )
        write_json(folder / f"proposed-plans-{attempt+1}.json", plans.model_dump())
        try:
            validate_plans(plans, task, candidates, usage, packet.get("environment"))
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
