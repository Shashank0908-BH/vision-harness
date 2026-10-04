"""Create Harbor task bundles using an explicit allowlist of agent-visible files."""

import json
import shutil
from pathlib import Path

from vision_harness.tracing import write_json


def build(dataset: Path, output: Path, split="dev", limit=0, specialist=False):
    if split not in ("dev", "test") or limit < 0:
        raise ValueError("split must be dev/test and limit nonnegative")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Task output must be empty; rebuild into a new directory")
    rows = [json.loads(line) for line in (dataset / "manifest.jsonl").read_text().splitlines()]
    rows = [row for row in rows if row["split"] == split]
    if limit:
        rows = rows[:limit]
    if not rows:
        raise ValueError("No matching dataset rows")
    for row in rows:
        task = output / row["id"]
        environment = task / "environment"
        bundle = environment / "app"
        bundle.mkdir(parents=True)
        for file in ("pyproject.toml", "requirements-runtime.txt"):
            shutil.copy2(file, bundle / file)
        if specialist:
            shutil.copy2("requirements-stardist.txt", bundle / "requirements-runtime.txt")
            model_directory = bundle / "models/stardist"
            model_directory.mkdir(parents=True)
            for name in ("config.json", "thresholds.json", "weights_best.h5"):
                shutil.copy2(Path("models/stardist") / name, model_directory / name)
        for directory in ("src", "configs", "prompts"):
            shutil.copytree(
                directory, bundle / directory, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
        (bundle / "evals").mkdir()
        shutil.copy2("evals/__init__.py", bundle / "evals/__init__.py")
        shutil.copy2(dataset / row["image"], environment / "input.png")
        dockerfile = """FROM python:3.12.13-slim
WORKDIR /app
COPY app/requirements-runtime.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY app /app
RUN pip install --no-cache-dir --no-deps /app
COPY input.png /data/input.png
RUN mkdir -p /output /logs/agent /logs/verifier
"""
        if specialist:
            dockerfile = dockerfile.replace(
                "WORKDIR /app\n",
                "RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libgomp1 && rm -rf /var/lib/apt/lists/*\nWORKDIR /app\n",
            )
        (environment / "Dockerfile").write_text(dockerfile)
        (task / "instruction.md").write_text(row["question"] + "\n")
        (task / "task.toml").write_text(f'''schema_version = "1.4"
[metadata]
family = "{row["family"]}"
split = "{split}"
dataset_id = "{row["id"]}"
[agent]
timeout_sec = 1200.0
[verifier]
timeout_sec = 60.0
[environment]
build_timeout_sec = 600.0
cpus = 2
memory_mb = {4096 if specialist else 2048}
storage_mb = {8192 if specialist else 4096}
''')
        tests = task / "tests"
        tests.mkdir()
        shutil.copy2("evals/scoring.py", tests / "score.py")
        write_json(
            tests / "expected.json",
            {key: row[key] for key in ("expected", "tolerance", "metric") if key in row},
        )
        (tests / "test.sh").write_text(
            "#!/bin/bash\nset -euo pipefail\npython /tests/score.py /output/answer.json /tests/expected.json /logs/verifier/reward.json\n"
        )
        solution = task / "solution"
        solution.mkdir()
        reference = {
            "status": "answered",
            "value": row["expected"],
            "explanation": "Reference answer from dataset ground truth",
            "evidence_ids": [],
            "limitations": [],
        }
        (solution / "solve.sh").write_text(
            "#!/bin/bash\nset -euo pipefail\nmkdir -p /output\ncat > /output/answer.json <<'ANSWER'\n"
            + json.dumps(reference)
            + "\nANSWER\n"
        )
