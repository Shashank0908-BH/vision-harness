"""Freeze all 50 official BBBC039 test images and a separate validation canary."""

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from evals.import_bbbc039 import QUESTION, decode_labels, to_display
from evals.research_execution.prepare import independent_reference_count
from vision_harness.research_execution.contracts import Policy

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RUN = ROOT / "runs/daytona/bbbc039-full-20260923"
SOURCE = ROOT / "evals/datasets/generated/bbbc039-adaptive-20260922/source"
ARMS = ["vanilla", "stardist", "full"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def prepare():
    if RUN.exists():
        raise ValueError("Experiment already exists; do not overwrite frozen inputs")
    with zipfile.ZipFile(SOURCE / "metadata.zip") as archive:
        selected = sorted(archive.read("metadata/test.txt").decode().splitlines())
        canary = sorted(archive.read("metadata/validation.txt").decode().splitlines())[:1]
    assert len(selected) == len(set(selected)) == 50 and not set(canary) & set(selected)
    exposed = set()
    for report in (ROOT / "reports").glob("*/selection.json"):
        data = json.loads(report.read_text())
        exposed.update(set(data.get("filenames", [])) & set(selected))
    policy = Policy(version="research-execution-daytona-0.1", max_rounds=4,
                    max_provider_calls=96, max_seconds=7200, codex_timeout_seconds=1200)
    selection = {"protocol": "bbbc039-daytona-three-arms-1", "frozen_at": datetime.now(timezone.utc).isoformat(),
        "source": "https://bbbc.broadinstitute.org/BBBC039", "split": "entire official test split",
        "filenames": selected, "validation_canary": canary, "previously_used_test_images": sorted(exposed),
        "repetitions": 3, "arms": ARMS, "n_test_attempts": 450, "query": QUESTION,
        "policy": policy.model_dump(), "concurrency": 1, "outcome_retries": 0,
        "pass_rule": "valid returned integer count within 10% of annotation-derived count, inclusive",
        "pass_at_3": "fraction of images with at least one pass among exactly three fresh attempts; pending images not scored",
        "mean_score": "mean binary pass across all attempts; failed/abstained/timed-out attempts score zero",
        "secondary": ["conditional mean absolute percentage error (MAPE) with coverage",
            "full-cohort MAPE only when every attempt answered", "per-image mean-count error when all three answered",
            "mean clipped count score max(0,1-absolute_count_error/reference_count), failures zero",
            "instance F1 at IoU >= 0.5 for StarDist and full harness", "latency, tokens, failure stage",
            "paired image-cluster bootstrap intervals; previous-test-exposure sensitivity"],
        "stardist": {"checkpoint": "2D_versatile_fluo", "weights_sha256": sha(ROOT / "models/stardist/weights_best.h5"),
            "input": "native original uint16, axes YX", "normalization": "csbdeep p1/p99.8, no clipping",
            "prob_thresh": 0.479071463157368, "nms_thresh": 0.3, "n_tiles": [1, 1],
            "border": "included", "seed": 0, "parameter_tuning": False},
        "input_policy": "same unchanged query and p1/p99.8 PNG preview for Astra arms; tools also get original TIFF",
        "isolation": "fresh non-root Daytona container per attempt; references in separate verifier only; local Harbor artifacts",
        "answer_policy": "full harness returns observed instance count with approved/provisional review status; both graded",
        "limitations": ["public data and unknown pretraining exposure", "some test images previously used in this project",
            "50 independent images, not 150 independent images per arm", "fixed StarDist repetitions may be identical",
            "counting endpoint is derived from a segmentation benchmark", "GPU and four-round budget differ from previous pilot"],
        "archives_sha256": {n: sha(SOURCE / n) for n in ("images.zip", "masks.zip", "metadata.zip")}}
    write(RUN / "selection.json", selection)  # freeze membership before opening reference labels
    app = RUN / "frozen"
    files = list((ROOT / "src/vision_harness").rglob("*.py"))
    files += list(HERE.glob("*.py"))
    files += [ROOT / p for p in ("infra/daytona/run_harness.py", "evals/atif.py",
        "configs/research-execution.toml", "prompts/astra-research-execution.md",
        "prompts/jev_plan_conditions.json", "prompts/jev_review_estimate.json")]
    for path in files:
        target = app / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    # Do not advertise a draft protocol in these frozen cloud trial manifests.
    entry = app / "infra/daytona/run_harness.py"
    entry.write_text(entry.read_text().replace("Not yet frozen; budgets must be declared before a new cohort",
        "bbbc039-daytona-three-arms-1; all 50 official test images; 3 attempts per arm"))
    source_hashes = {str(p.relative_to(app)): sha(p) for p in sorted(app.rglob("*")) if p.is_file()}
    write(RUN / "source-manifest.json", source_hashes)
    verifier = (ROOT / "evals/research_execution/verifier.py").read_text().replace(
        'answer.get("mode") == "full"', 'answer.get("mode") in ("full", "stardist")')
    verifier = verifier.replace('count = answer.get("count")',
        'count = answer.get("count")\n        if answer.get("mode") not in ("vanilla", "full", "stardist"):\n            raise ValueError("Invalid arm")')
    rows = []
    with zipfile.ZipFile(SOURCE / "images.zip") as images, zipfile.ZipFile(SOURCE / "masks.zip") as masks:
        image_names = {Path(n).stem: n for n in images.namelist() if n.lower().endswith((".tif", ".tiff")) and not n.startswith("__MACOSX/")}
        mask_names = {Path(n).name: n for n in masks.namelist() if n.endswith(".png") and not n.startswith("__MACOSX/")}
        for split, names in (("test", selected), ("canary", canary)):
            for index, name in enumerate(names, 1):
                task = RUN / "tasks" / split / f"image-{index:02d}"
                env = task / "environment"
                env.mkdir(parents=True)
                raw = images.read(image_names[Path(name).stem])
                gray = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
                display, percentiles = to_display(gray)
                (env / "input.tif").write_bytes(raw)
                cv2.imwrite(str(env / "input.png"), display)
                shutil.copytree(app, env / "app")
                for n in ("science.lock", "torch.lock", "configure_cuda.py"):
                    shutil.copy2(HERE.parent / n, env / n)
                shutil.copy2(HERE / "Dockerfile", env / "Dockerfile")
                shutil.copytree(ROOT / "models/stardist", env / "stardist")
                (env / ".dockerignore").write_text("*\n!Dockerfile\n!science.lock\n!torch.lock\n!configure_cuda.py\n!stardist\n!stardist/**\n")
                rgb = cv2.imdecode(np.frombuffer(masks.read(mask_names[name]), np.uint8), cv2.IMREAD_COLOR)[..., ::-1]
                labels = decode_labels(rgb)
                expected = int(np.count_nonzero(np.unique(labels) > 0))
                assert expected == independent_reference_count(rgb[..., 0]) and labels.shape == gray.shape
                tests = task / "tests"
                tests.mkdir()
                np.savez_compressed(tests / "reference.npz", labels=labels)
                (tests / "verify.py").write_text(verifier)
                (tests / "test.sh").write_text("#!/bin/sh\nset -eu\npython /tests/verify.py\n")
                # A separate verifier owns /tests; Harbor skips uploading tests in this mode.
                # This context is never used to build the agent's image.
                (tests / "Dockerfile").write_text("FROM python:3.12.13-slim\nRUN pip install --no-cache-dir numpy==2.5.3\nRUN mkdir -p /output /tests /logs/verifier\nCOPY . /tests\nWORKDIR /tests\n")
                (task / "instruction.md").write_text(QUESTION + "\n")
                (task / "task.toml").write_text('''schema_version = "1.4"
artifacts = ["/output"]
[agent]
timeout_sec = 7320
user = "researcher"
[environment]
cpus = 8
memory_mb = 32768
storage_mb = 81920
gpus = 1
gpu_types = ["RTX-4090"]
build_timeout_sec = 2400
network_mode = "public"
workdir = "/app"
[verifier]
timeout_sec = 120
environment_mode = "separate"
user = "root"
[verifier.environment]
cpus = 1
memory_mb = 2048
storage_mb = 4096
gpus = 0
build_timeout_sec = 600
network_mode = "no-network"
''')
                rows.append({"split": split, "id": task.name, "source_filename": name,
                    "raw_sha256": sha(env / "input.tif"), "preview_sha256": sha(env / "input.png"),
                    "percentiles": percentiles, "expected": expected, "decoder_agreement": True,
                    "previously_used": name in exposed})
    write(RUN / "cohort.json", rows)
    task_hashes = {str(p.relative_to(RUN)): sha(p) for p in sorted((RUN / "tasks").rglob("*")) if p.is_file()}
    write(RUN / "task-manifest.json", task_hashes)
    for split, attempts in (("test", 3), ("canary", 1)):
        config = {"job_name": split, "jobs_dir": str(RUN / "jobs"), "n_attempts": attempts,
            "n_concurrent_trials": 1, "quiet": True, "retry": {"max_retries": 0},
            "environment": {"type": "daytona", "delete": True, "kwargs": {
                "auto_snapshot": False, "auto_stop_interval_mins": 150, "auto_delete_interval_mins": 0,
                "labels": {"vision.owner": "vision-lab-20260923", "vision.experiment": "bbbc039-full-20260923"}}},
            "agents": [{"import_path": "infra.daytona.benchmark.agent:CohortAgent",
                        "model_name": "StarDist-2D_versatile_fluo" if arm == "stardist" else "gpt-6-astra",
                        "kwargs": {"mode": arm}} for arm in ARMS],
            "datasets": [{"path": str(RUN / "tasks" / split)}]}
        write(RUN / f"{split}-config.json", config)
    print(json.dumps({"run": str(RUN), "test_images": 50, "attempts": 450, "canary_attempts": 3}))


if __name__ == "__main__":
    prepare()
