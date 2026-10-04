"""Import the complete published BBBC001 counting benchmark, without rendering scenes.

Usage: python -m evals.import_bbbc001 DATASET_DIRECTORY REPORT_DIRECTORY
The only pixel transformation is lossless 8-bit grayscale TIFF -> RGB PNG.
"""

import csv
import hashlib
import io
import json
import subprocess
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from vision_harness.tracing import write_json

PAGE = "https://bbbc.broadinstitute.org/BBBC001"
BASE = "https://data.broadinstitute.org/bbbc/BBBC001/"
FILES = ("BBBC001_v1_images_tif.zip", "BBBC001_v1_counts.txt")
QUESTION = (
    "Count the cells in this fluorescence microscopy image of Hoechst-stained nuclei. "
    "Return your estimated total cell count as a number."
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(dataset: Path, report: Path):
    if dataset.exists() or report.exists():
        raise ValueError("Use new dataset/report directories; frozen inputs are never overwritten")
    dataset.mkdir(parents=True)
    report.mkdir(parents=True)
    source = dataset / "source"
    source.mkdir()
    downloads = []
    for name in FILES:
        with urllib.request.urlopen(BASE + name, timeout=60) as response:
            data = response.read()
        (source / name).write_bytes(data)
        downloads.append({"url": BASE + name, "sha256": digest(data), "bytes": len(data)})
    counts = list(csv.DictReader(io.StringIO((source / FILES[1]).read_text()), delimiter="\t"))
    if len(counts) != 6:
        raise ValueError("Expected the complete six-image BBBC001v1 release")
    rows = []
    with zipfile.ZipFile(source / FILES[0]) as archive:
        members = {Path(name).name: name for name in archive.namelist() if name.endswith(".tif")}
        if set(members) != {row["Image"] for row in counts}:
            raise ValueError("Archive and annotation file do not match")
        for i, annotation in enumerate(counts):
            filename = annotation["Image"]
            raw = archive.read(members[filename])
            gray = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
            if gray.shape != (512, 512) or gray.dtype != np.uint8:
                raise ValueError("Unexpected source image format")
            rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            ok, encoded = cv2.imencode(".png", rgb)
            if not ok or not np.array_equal(cv2.imdecode(encoded, 0), gray):
                raise ValueError("PNG conversion did not preserve every source pixel")
            task_id = digest(filename.encode())[:12]
            relative = f"images/{task_id}.png"
            (dataset / "images").mkdir(exist_ok=True)
            (dataset / relative).write_bytes(encoded.tobytes())
            human = [int(annotation[f"manual count #{n}"]) for n in (1, 2)]
            rows.append(
                {
                    "id": task_id,
                    "family": "microscopy_cell_count",
                    "split": "test",
                    "title": f"BBBC001 field {i + 1}",
                    "image": relative,
                    "question": QUESTION,
                    "expected": sum(human) / 2,
                    "tolerance": 0,
                    "metric": "bbbc001_percentage_error",
                    "human_counts": human,
                    "source_filename": filename,
                    "source_tiff_sha256": digest(raw),
                    "sha256": digest(encoded.tobytes()),
                }
            )
    (dataset / "manifest.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    protocol = {
        "name": "Complete BBBC001v1 counting benchmark",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "source_page": PAGE,
        "downloads": downloads,
        "dataset_directory": str(dataset),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "working_tree": "Benchmark adapter/report additions; inference runtime unchanged from source commit.",
        "modes": ["vanilla", "tools", "select", "review", "full"],
        "repetitions": 1,
        "selection": "All six published images, in annotation-file order; no exclusions.",
        "split_note": "BBBC001 has no official train/test split. 'test' is a local Harbor routing label only.",
        "task": "Published cell-counting task; identical neutral instruction for every image and mode.",
        "primary_metric": "Mean over all six images of 100 * abs(prediction - mean(two human counts)) / mean(two human counts); lower is better.",
        "missing_policy": "No official full-dataset score if any prediction is missing, negative, nonfinite or an error. Show coverage and answered-subset error separately; do not rank partial scores against complete scores.",
        "preprocessing": "Lossless 8-bit grayscale TIFF to RGB PNG by channel replication. No resize, contrast adjustment, denoising, annotation overlays or synthetic pixels.",
        "leakage": "Only PNG and question enter the agent environment; counts, original filenames, source URLs and dataset metadata stay in verifier/report. Prior model exposure to this public dataset cannot be ruled out.",
        "limitations": [
            "Only six images from one experiment, not broad multimodal evidence.",
            "Published human counts disagree; their mean is the reference, not an exact biological truth.",
            "Current OpenCV tools are color/white-background tools, not microscopy segmentation models.",
            "Independent plans and different compute per mode prevent a clean causal estimate of Jev selection alone.",
            "No model/rubric/threshold tuning or selective retry after outcomes.",
        ],
        "license": "CC BY-NC-SA 3.0; images and ground truth by David Root and Anne Carpenter.",
        "license_url": "https://creativecommons.org/licenses/by-nc-sa/3.0/",
        "attribution": "BBBC001v1, Moffat et al. (Cell, 2006), Broad Bioimage Benchmark Collection; Ljosa et al. (Nature Methods, 2012).",
        "runtime_hashes": {
            str(p): digest(p.read_bytes())
            for folder in ("src", "configs", "prompts")
            for p in sorted(Path(folder).rglob("*"))
            if p.is_file() and p.suffix in (".py", ".toml", ".md", ".json")
        },
    }
    write_json(report / "protocol.json", protocol)
    write_json(report / "cohort.json", rows)
    print(
        f"Imported {len(rows)} original microscopy images; pixel equality verified. Protocol: {report / 'protocol.json'}"
    )


if __name__ == "__main__":
    prepare(Path(sys.argv[1]), Path(sys.argv[2]))
