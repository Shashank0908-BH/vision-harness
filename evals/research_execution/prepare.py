"""Freeze a label-blind selection and create tasks with isolated reference artifacts."""

import argparse
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from evals.import_bbbc039 import QUESTION, decode_labels, to_display
from vision_harness.research_execution.contracts import Policy
from vision_harness.research_execution.replay import PREFIX_FILES
from vision_harness.tracing import write_json

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "evals/datasets/generated/bbbc039-adaptive-20260922/source"
REPORT = ROOT / "reports/research-execution-20260922"
TASKS = ROOT / "evals/tasks/generated/research-execution"
SEED = "vision-research-execution-v3-20260922:"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def independent_reference_count(red):
    """Plain flood fill, independent of OpenCV's connected-component implementation."""
    remaining = {(int(y), int(x)) for y, x in zip(*np.nonzero(red), strict=True)}
    count = 0
    while remaining:
        first = remaining.pop()
        value = red[first]
        stack = [first]
        count += 1
        while stack:
            y, x = stack.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    neighbor = (y+dy, x+dx)
                    if neighbor in remaining and red[neighbor] == value:
                        remaining.remove(neighbor)
                        stack.append(neighbor)
    return count


def source_snapshot():
    files = list((ROOT / "src/vision_harness").rglob("*.py")) + list((ROOT / "evals/research_execution").glob("*.py"))
    files += [ROOT / "configs/research-execution.toml", ROOT / "evals/research_execution/Dockerfile"]
    files += [ROOT / "evals/import_bbbc039.py", ROOT / "evals/atif.py"]
    files += [ROOT / "prompts" / name for name in (
        "astra-research-execution.md", "jev_plan_conditions.json", "jev_review_estimate.json")]
    return {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted(files)}


def prepare(split, development_prefix=None):
    if split == "test" and development_prefix:
        raise ValueError("Held-out benchmark forbids development-prefix replay")
    directory = TASKS / split
    if directory.exists():
        raise ValueError(f"Task set already exists: {directory}; preserve it and use a new development name")
    with zipfile.ZipFile(SOURCE / "metadata.zip") as archive:
        official = archive.read("metadata/test.txt").decode().splitlines()
        validation = archive.read("metadata/validation.txt").decode().splitlines()
    excluded = set()
    for name in ("bbbc039-adaptive-20260922", "bbbc039-routing-20260922"):
        excluded.update(json.loads((ROOT / "reports" / name / "selection.json").read_text())["filenames"])
    selected = sorted(set(official)-excluded, key=lambda n: sha((SEED+n).encode()))[:12] if split == "test" else sorted(validation)[:1]
    report = REPORT if split == "test" else REPORT / split
    selection = {"frozen_at": datetime.now(timezone.utc).isoformat(), "source": "https://bbbc.broadinstitute.org/BBBC039",
                 "split": "official test" if split == "test" else "official validation; development only",
                 "filenames": selected, "excluded_previous_test_images": sorted(excluded),
                 "rule": f"SHA256({SEED} + filename), first 12 unused; no label-based selection",
                 "repetitions": 3 if split == "test" else 1, "arms": ["vanilla", "full"],
                 "development_prefix_replay": bool(development_prefix),
                 "policy": Policy().model_dump(), "source_snapshot": source_snapshot(), "enforce_source_snapshot": True,
                 "archives_sha256": {n: sha((SOURCE / n).read_bytes()) for n in ("images.zip", "masks.zip", "metadata.zip")},
                 "primary_metric": "all-attempt proportion within 10% of annotation-derived count; failures score zero",
                 "secondary_metrics": ["coverage", "conditional MAPE", "complete-cohort MAPE only if all answered", "instance F1 at IoU>=0.5", "time", "tokens", "image-cluster paired intervals"],
                 "answer_policy": "Return a validated mask's count with truthful review status. If downstream review fails, retain an explicitly unreviewed fallback, reported separately from full-chain completion. Absent validated artifact is failure.",
                 "input_policy": "same question and 1/99.8 percentile preview for both arms; tool arm also gets original uint16 file",
                 "retry_policy": "One recorded trial; one configured transient API retry per request, one catalog semantic repair, one research token-limit retry and up to two scored execution rounds within unchanged total budgets. No whole-trial outcome retries.",
                 "limitations": ["public benchmark; pretrained exposure unknown", "counting derived from segmentation labels, not original benchmark metric", "12 images are a pilot, not a broad multimodal claim", "CPU-only deployment and bounded catalog search"]}
    write_json(report / "selection.json", selection)  # before opening any reference masks
    image_build = json.loads((ROOT / "evals/datasets/generated/research-execution-toolchain/build.json").read_text())
    write_json(report / "toolchain.json", image_build)
    rows = []
    with zipfile.ZipFile(SOURCE / "images.zip") as images, zipfile.ZipFile(SOURCE / "masks.zip") as masks:
        image_names = {Path(n).stem: n for n in images.namelist() if n.lower().endswith((".tif", ".tiff")) and not n.startswith("__MACOSX/")}
        mask_names = {Path(n).name: n for n in masks.namelist() if n.endswith(".png") and not n.startswith("__MACOSX/")}
        for index, name in enumerate(selected, 1):
            task = directory / f"image-{index:02d}"
            environment = task / "environment"
            environment.mkdir(parents=True)
            raw = images.read(image_names[Path(name).stem])
            gray = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
            display, percentiles = to_display(gray)
            (environment / "input.tif").write_bytes(raw)
            cv2.imwrite(str(environment / "input.png"), display)
            if development_prefix:
                prefix = environment / "development-prefix"
                prefix.mkdir()
                for relative in PREFIX_FILES:
                    target = prefix / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(development_prefix / relative, target)
                intake_paths = list((development_prefix / "stage-packets").glob("*-intake.json"))
                if len(intake_paths) != 1:
                    raise ValueError("Expected one source intake packet")
                intake = json.loads(intake_paths[0].read_text())
                if intake["observed_input"]["sha256"] != sha(raw):
                    raise ValueError("Development prefix does not match validation input")
                write_json(prefix / "identity.json", {"source_run_directory": str(development_prefix),
                    "input_sha256": sha(raw), "not_a_fresh_trial": True,
                    "purpose": "development replay after adapter correction; benchmark must run every stage afresh",
                    "artifact_hashes": {r: sha((prefix / r).read_bytes()) for r in PREFIX_FILES}})
            rgb = cv2.imdecode(np.frombuffer(masks.read(mask_names[name]), np.uint8), cv2.IMREAD_COLOR)[..., ::-1]
            labels = decode_labels(rgb)
            # Separate implementation verifies reference decoding; these data never enter the task image.
            independent_count = independent_reference_count(rgb[..., 0])
            count = int(np.count_nonzero(np.unique(labels) > 0))
            assert independent_count == count and count > 0 and labels.shape == gray.shape
            tests = task / "tests"
            tests.mkdir()
            np.savez_compressed(tests / "reference.npz", labels=labels)
            shutil.copy2(Path(__file__).with_name("verifier.py"), tests / "verify.py")
            (tests / "test.sh").write_text("#!/bin/sh\nset -eu\npython /tests/verify.py\n")
            (tests / "Dockerfile").write_text(f"FROM {image_build['image']}\nUSER root\nCOPY . /tests\nWORKDIR /tests\n")
            app = environment / "app"
            shutil.copytree(ROOT / "src/vision_harness", app / "src/vision_harness", ignore=shutil.ignore_patterns("__pycache__"))
            (app / "configs").mkdir()
            shutil.copy2(ROOT / "configs/research-execution.toml", app / "configs/research-execution.toml")
            (app / "prompts").mkdir()
            for prompt in ("astra-research-execution.md", "jev_plan_conditions.json", "jev_review_estimate.json"):
                shutil.copy2(ROOT / "prompts" / prompt, app / "prompts" / prompt)
            prefix_copy = "COPY development-prefix /data/development-prefix\n" if development_prefix else ""
            (environment / "Dockerfile").write_text(f"FROM {image_build['image']}\nUSER root\nCOPY app /app\nCOPY input.tif /data/input.tif\nCOPY input.png /data/input.png\n{prefix_copy}ENV PYTHONPATH=/app/src\nWORKDIR /app\nUSER researcher\n")
            (task / "instruction.md").write_text(QUESTION+"\n")
            (task / "task.toml").write_text('''schema_version = "1.4"
artifacts = ["/output"]
[agent]
timeout_sec = 1560
user = "researcher"
[environment]
cpus = 2
memory_mb = 6144
storage_mb = 12000
build_timeout_sec = 300
network_mode = "public"
[verifier]
timeout_sec = 120
environment_mode = "separate"
user = "root"
''')
            rows.append({"id": task.name, "source_filename": name, "source_tiff_sha256": sha(raw),
                         "preview_sha256": sha((environment / "input.png").read_bytes()),
                         "percentiles": percentiles, "expected": count, "decoder_agreement": True})
    write_json(report / "cohort.json", rows)
    print(json.dumps({"tasks": str(directory), "images": len(rows), "split": split,
                      "references_outside_agent_build_context": True}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev-01")
    parser.add_argument("--development-prefix", type=Path)
    args = parser.parse_args()
    prepare(args.split, args.development_prefix)


if __name__ == "__main__":
    main()
