"""Reusable GPU entry: explicit interpreter/import preflight within original budgets."""

import argparse
from pathlib import Path

from infra.daytona.run_harness import inventory as gpu_inventory
from vision_harness.config import load_settings
from vision_harness.research_execution import runtime
from vision_harness.research_execution.contracts import Policy


def inventory():
    value = gpu_inventory()
    value["installation"] = (
        "Shared environments and checkpoints are read-only. Install additional packages per trial with "
        "uv pip install --python <selected interpreter> --target <its package_target> PACKAGE. "
        "Use the exact env and unset values from python_environments for setup checks; the executor uses them "
        "explicitly for both import preflight and inference. Pin new packages and constrain existing runtime "
        "versions to avoid silently replacing NumPy, TensorFlow or Torch. Do not assume science packages exist "
        "in Torch. The distribution scikit-image supplies the skimage imports. Record every install."
    )
    for executable, spec in value["python_environments"].items():
        family = "torch" if executable.startswith("/opt/venvs/torch/") else "science"
        target = f"/home/researcher/packages/{family}"
        spec["package_target"] = target
        spec["env"]["PYTHONPATH"] = f"{target}:/app/src:/app"
    value["execution_isolation"] = "Private filesystem and PID namespace inside one reused GPU workspace; no prior trials or references mounted"
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runtime.inventory = inventory
    runtime.run(args.query, "full", load_settings(Path("configs/research-execution.toml")), args.output,
                policy=Policy(version="research-execution-reuse-gpu-operational03"))
