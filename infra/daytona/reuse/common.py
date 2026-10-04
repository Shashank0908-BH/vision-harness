"""Experiment identity and file utilities; no model or cloud SDK imports."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NAME = "reuse-gpu-repair02"
SPLIT = "test-gpu-repair02"
LOCAL = ROOT / "runs/daytona" / NAME
REMOTE = Path("/root/vision-benchmarks") / NAME
REPORT = Path("reports/research-execution-20260922") / SPLIT


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def hashes(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
