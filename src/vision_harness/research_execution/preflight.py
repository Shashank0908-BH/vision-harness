"""Interpreter-specific import checks, run only inside an isolated execution task.

Checking import statements does not execute the approved scientific program or
load its checkpoints. Conditional/dynamic imports remain runtime checks.
"""

import ast
import json
import os
import re
import shlex
import sys
from pathlib import Path


def import_statements(program):
    return [ast.unparse(node) for node in ast.parse(program).body
            if isinstance(node, (ast.Import, ast.ImportFrom))]


def validate_dependencies(plan, environment):
    specs = environment.get("python_environments", {})
    if not specs:
        return
    if plan.python_executable not in specs:
        raise ValueError("Plan must select python_executable from measured python_environments")
    pins = {}
    for requirement in plan.install_requirements:
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.+_-]*)", requirement)
        if not match:
            raise ValueError("install_requirements must be exact package==version pins")
        name, version = match.groups()
        name = re.sub(r"[-_.]+", "-", name).lower()
        if name in pins and pins[name] != version:
            raise ValueError(f"Conflicting installation pins for {name}")
        pins[name] = version
    modules = specs[plan.python_executable].get("modules", {})
    roots = set()
    for statement in import_statements(plan.python_program):
        node = ast.parse(statement).body[0]
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif node.module and not node.level:
            roots.add(node.module.split(".")[0])
    for root in roots:
        facts = modules.get(root)
        if facts and not facts["module_found"]:
            distribution = re.sub(r"[-_.]+", "-", facts["distribution"]).lower()
            if distribution not in pins:
                raise ValueError(f"{root} is absent from {plan.python_executable}; declare a pinned "
                                 f"{distribution} in install_requirements before scoring")
    for facts in modules.values():
        distribution = re.sub(r"[-_.]+", "-", facts["distribution"]).lower()
        if facts.get("version") and distribution in pins and pins[distribution] != facts["version"]:
            raise ValueError(f"Do not replace measured {distribution}={facts['version']} in a private overlay")


def commands(plan, environment, folder):
    """Use the same interpreter and explicit non-secret variables for both steps."""
    validate_dependencies(plan, environment)
    specs = environment.get("python_environments", {})
    if not specs:
        return None  # Legacy non-GPU plans retain their recorded execution contract.
    if plan.python_executable not in specs:
        raise ValueError("Plan must select a measured python_executable")
    spec = specs[plan.python_executable]
    prefix = ["env"]
    for name in spec.get("unset", []):
        prefix += ["-u", name]
    prefix += [f"{k}={v}" for k, v in spec.get("env", {}).items()]
    prefix += [f"VISION_PYTHON_LAUNCHER={plan.python_executable}"]
    prefix += [plan.python_executable]
    result = {
        "preflight": shlex.join(prefix + [str(folder / "import-preflight.py"),
                                         str(folder / "approved.py"),
                                         str(folder / "import-preflight.json")]),
        "program": shlex.join(prefix + [str(folder / "approved.py")]),
    }
    if plan.install_requirements:
        if not spec.get("package_target"):
            raise ValueError("Pinned installs require a private package_target")
        constraints = folder / "runtime-constraints.txt"
        constraints.write_text("\n".join(sorted({f"{m['distribution']}=={m['version']}"
                               for m in spec.get("modules", {}).values() if m.get("version")})) + "\n")
        result["install"] = shlex.join(["uv", "pip", "install", "--python", plan.python_executable,
                                      "--target", spec["package_target"], "--constraint", str(constraints),
                                      *plan.install_requirements])
    return result


def validate_report(path, plan):
    report = json.loads(path.read_text())
    if report.get("launcher") != plan.python_executable or report.get("ok") is not True:
        raise RuntimeError("Import preflight failed for the selected interpreter")
    checks = report.get("checks", [])
    if ([c.get("statement") for c in checks] != import_statements(plan.python_program)
            or any(c.get("ok") is not True for c in checks)):
        raise RuntimeError("Import preflight did not cover the approved program's imports")
    return report


def main():
    program, destination = map(Path, sys.argv[1:])
    # Imports cannot compete with a model for GPU memory. This setting is scoped
    # to this short-lived process; the subsequent program retains GPU access.
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    namespace, checks = {}, []
    for statement in import_statements(program.read_text()):
        try:
            exec(compile(statement, str(program), "exec"), namespace)
            checks.append({"statement": statement, "ok": True})
        except Exception as error:
            checks.append({"statement": statement, "ok": False,
                           "error": f"{type(error).__name__}: {error}"})
    report = {"ok": all(c["ok"] for c in checks), "executable": sys.executable,
              "launcher": os.environ.get("VISION_PYTHON_LAUNCHER", sys.executable),
              "checks": checks, "scope": "unconditional module-level imports; no model inference"}
    destination.write_text(json.dumps(report, indent=2) + "\n")
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
