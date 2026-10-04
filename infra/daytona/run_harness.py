"""Cloud entry point with measured hardware and explicit long-run budgets.

Keeps the existing local experiment frozen. The inventory override is scoped to
this process and is recorded in cloud-launch.json before provider calls begin.
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

from vision_harness.config import load_settings
from vision_harness.research_execution import runtime
from vision_harness.research_execution.contracts import Policy

LOCAL_INVENTORY = runtime.inventory


def inventory():
    result = LOCAL_INVENTORY()
    quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
    memory = Path("/sys/fs/cgroup/memory.max").read_text().strip()
    gpu = subprocess.check_output([
        "nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"
    ], text=True, timeout=15).strip()
    assert gpu, "GPU inventory is empty"
    torch_python = "/opt/venvs/torch/bin/python"
    versions = json.loads(subprocess.check_output([
        torch_python, "-c", "import json,importlib.metadata as m; print(json.dumps({p:m.version(p) for p in ['torch','cellpose']}))"
    ], text=True, timeout=15))
    result.update(
        accelerator=gpu,
        resources={"cpu_cores": None if quota == "max" else int(quota)/int(period),
                   "memory_gib": None if memory == "max" else int(memory)/1024**3,
                   "source": "cgroup v2 and nvidia-smi; unknown physical pixel scale"},
        additional_python_environments={torch_python: versions},
        installation="Use uv pip install --python <chosen environment Python> for approved dependencies; record changes. Do not use system pip or pip --user for these isolated virtual environments.",
        execution_instructions=[
            "GPU is available; select and document CPU/CUDA use explicitly and verify actual device placement.",
            "Controller and TensorFlow use /opt/venvs/science/bin/python-gpu.",
            "For PyTorch/Cellpose use: env -u LD_LIBRARY_PATH /opt/venvs/torch/bin/python.",
            "TensorFlow and PyTorch run in separate processes with separate CUDA library paths.",
            "Do not infer that a pretrained model is accurate merely because its code executes on a GPU.",
        ],
    )
    return result


def positive(value):
    value = int(value)
    if value <= 0:
        raise argparse.ArgumentTypeError("Expected a positive integer")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true", help="Show measured hardware and budgets; makes no model calls")
    parser.add_argument("--mode", choices=["vanilla", "full"])
    parser.add_argument("--query")
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/research-execution.toml"))
    parser.add_argument("--max-seconds", type=positive, default=7200)
    parser.add_argument("--max-provider-calls", type=positive, default=96)
    parser.add_argument("--codex-timeout-seconds", type=positive, default=1200)
    parser.add_argument("--max-rounds", type=positive, default=4)
    args = parser.parse_args()
    policy = Policy(version="research-execution-daytona-0.1", max_seconds=args.max_seconds, max_provider_calls=args.max_provider_calls,
                    codex_timeout_seconds=args.codex_timeout_seconds, max_rounds=args.max_rounds)
    measured = inventory()
    launch = {"entry_point": "infra/daytona/run_harness.py", "inventory": measured,
              "policy": policy.model_dump(), "benchmark_protocol": "Not yet frozen; budgets must be declared before a new cohort"}
    if args.describe:
        print(json.dumps(launch, indent=2))
        return
    if not all((args.mode, args.query, args.raw, args.preview, args.output)):
        parser.error("--mode, --query, --raw, --preview and --output are required")
    if not os.environ.get("LD_LIBRARY_PATH"):
        parser.error("Use /opt/venvs/science/bin/python-gpu so child inference processes inherit CUDA paths")
    if args.output.exists():
        parser.error("Output already exists; choose a fresh directory for each attempt")
    if not args.raw.is_file() or not args.preview.is_file():
        parser.error("Both input files must exist")
    args.output.mkdir(parents=True)
    (args.output / "cloud-launch.json").write_text(json.dumps(launch, indent=2) + "\n")
    runtime.inventory = inventory
    runtime.run(args.query, args.mode, load_settings(args.config), args.output,
                raw=args.raw, preview=args.preview, policy=policy)


if __name__ == "__main__":
    main()
