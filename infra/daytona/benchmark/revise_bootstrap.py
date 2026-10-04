"""Preserve the failed setup run; fork its frozen science with a bootstrap fix."""

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def revise(original, revised):
    if revised.exists():
        raise ValueError("Revision already exists; never overwrite an experiment")
    if list((original / "jobs/test").glob("*/config.json")):
        raise ValueError("Test attempts already exist; do not revise a started benchmark")
    revised.mkdir(parents=True)
    for name in ("frozen", "tasks"):
        shutil.copytree(original / name, revised / name)
    for name in ("selection.json", "cohort.json"):
        shutil.copy2(original / name, revised / name)
    here = Path(__file__).resolve().parent
    replacements = [revised / "frozen/infra/daytona/benchmark/agent.py"]
    replacements += list((revised / "tasks").glob("*/*/environment/app/infra/daytona/benchmark/agent.py"))
    for path in replacements:
        shutil.copy2(here / "agent.py", path)
    shutil.copy2(here / "environment.py", revised / "frozen/infra/daytona/benchmark/environment.py")
    for path in (revised / "tasks").glob("*/*/environment/Dockerfile"):
        shutil.copy2(here / "Dockerfile", path)
    for path in (revised / "tasks").glob("*/*/tests/Dockerfile"):
        contents = path.read_text()
        if "COPY . /tests" not in contents:
            path.write_text(contents.replace("WORKDIR /tests", "COPY . /tests\nWORKDIR /tests"))
    old_hashes = json.loads((original / "task-manifest.json").read_text())
    new_hashes = {str(p.relative_to(revised)): sha(p) for p in sorted((revised / "tasks").rglob("*")) if p.is_file()}
    changes = {name: {"before": old_hashes[name], "after": digest} for name, digest in new_hashes.items()
               if old_hashes[name] != digest}
    assert all(p.endswith("/environment/Dockerfile") or p.endswith("/tests/Dockerfile")
               or p.endswith("/environment/app/infra/daytona/benchmark/agent.py") for p in changes)
    write(revised / "task-manifest.json", new_hashes)
    write(revised / "source-manifest.json", {str(p.relative_to(revised / "frozen")): sha(p)
        for p in sorted((revised / "frozen").rglob("*")) if p.is_file()})
    for split in ("canary", "test"):
        config = json.loads((original / f"{split}-config.json").read_text())
        config["jobs_dir"] = str(revised / "jobs")
        config["datasets"][0]["path"] = str(revised / "tasks" / split)
        config["environment"]["kwargs"]["labels"]["vision.experiment"] = revised.name
        config["environment"].pop("type", None)
        config["environment"]["import_path"] = "infra.daytona.benchmark.environment:CohortEnvironment"
        write(revised / f"{split}-config.json", config)
    revision = {"time": datetime.now(timezone.utc).isoformat(), "original": str(original),
        "revised": str(revised), "reason": "Toolbox user blocked Harbor bootstrap; separate verifier image omitted its test script and references",
        "fix": "Root toolbox, checked UID 1000 agents, separate verifier resources, bounded infrastructure RPCs, shell file checks, module entry point preventing StarDist package shadowing",
        "transport_retry_policy": "At most 3 attempts for idempotent infrastructure RPCs; never retries model inference",
        "cohort_and_scoring_unchanged": True, "scientific_source_and_model_settings_unchanged": True,
        "test_attempts_before_revision": 0, "changed_task_files": changes}
    write(revised / "infrastructure-revision.json", revision)
    write(original / "superseded_by.json", {"path": str(revised), "reason": revision["reason"]})
    print(json.dumps({"revised": str(revised), "changed_infrastructure_files": len(changes)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("original", type=Path)
    parser.add_argument("revised", type=Path)
    args = parser.parse_args()
    revise(args.original.resolve(), args.revised.resolve())
