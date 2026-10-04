"""Freeze all official test fields before inference; keep labels out of inputs."""

import concurrent.futures
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import httpx
import numpy as np

from vision_harness.routing.catalog import sha256
from vision_harness.routing.runtime import source_hash
from vision_harness.tracing import write_json

NAME = "kromp-repeated-20260922"
DATA = Path("evals/datasets/generated") / NAME
REPORT = Path("reports") / NAME
RUNS = Path("runs") / NAME
SOURCE = Path("evals/datasets/generated/kromp-source")
BASE = "https://ftp.ebi.ac.uk/biostudies/fire/S-BIAD/634/S-BIAD634/Files/"
CATALOG = Path("catalog/microscopy-v1.json")
CONFIG = Path("configs/routing.toml")
VANILLA_CONFIG = Path("configs/poc-adaptive.toml")
REPEATS = 3
QUESTION = (
    "Estimate the total number of nuclei in this DAPI fluorescence microscopy image. "
    "Follow the annotation rules: count intact nuclei even when dim; exclude heavily damaged "
    "or wholly out-of-focus nuclei; count a partly out-of-focus nucleus when an in-focus "
    "part is visible. Count dividing nuclei as one unless clear borders separate them. "
    "Include visible border nuclei that meet these rules. Return the estimated count as a number."
)


def attributes(item):
    return {a["name"]: a.get("value") for a in item.get("attributes", [])}


def test_entries(metadata):
    items = [x for x in metadata if attributes(x).get("Train-/Testset split") == "test"]
    names = [x["path"] for x in items]
    if len(items) != 37 or len(set(names)) != 37:
        raise ValueError("Official test split differs from the reviewed 37 unique fields")
    return sorted(items, key=lambda x: x["path"])


def download(path, output):
    if output.exists():
        return
    for attempt in range(4):
        try:
            with httpx.Client(timeout=120, follow_redirects=True) as client:
                response = client.get(BASE + path)
                response.raise_for_status()
                output.parent.mkdir(parents=True, exist_ok=True)
                temporary = output.with_suffix(output.suffix + ".part")
                temporary.write_bytes(response.content)
                temporary.replace(output)
                return
        except httpx.HTTPError:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def prepare():
    if (REPORT / "protocol.json").exists() or (DATA / "inputs.json").exists():
        raise ValueError("Frozen experiment already exists")
    SOURCE.mkdir(parents=True, exist_ok=True)
    for name in ("file_list_raw_images.json", "file_list_annotations.json", "dataset/readme.txt"):
        download(name, SOURCE / Path(name).name)
    metadata = json.loads((SOURCE / "file_list_raw_images.json").read_text())
    selected = test_entries(metadata)
    annotations = json.loads((SOURCE / "file_list_annotations.json").read_text())
    annotation_paths = {x["path"] for x in annotations}
    resources = [CATALOG, CONFIG, VANILLA_CONFIG, Path("prompts/astra-routing.md"),
                 Path("prompts/astra-adaptive.md"), Path("prompts/jev_plan_conditions.json"),
                 Path("prompts/jev_review_estimate.json")]
    protocol = {
        "frozen_at": datetime.now(timezone.utc).isoformat(), "source": "https://www.ebi.ac.uk/biostudies/BioImages/studies/S-BIAD634",
        "paper": "https://www.nature.com/articles/s41597-020-00608-w",
        "selection": "ALL 37 official test images, no outcome-based selection", "repetitions": REPEATS,
        "filenames": [x["path"] for x in selected], "question": QUESTION,
        "source_sha256": source_hash(), "resources_sha256": {str(p): sha256(p) for p in resources},
        "metadata_sha256": {str(p): sha256(p) for p in [SOURCE / "file_list_raw_images.json", SOURCE / "file_list_annotations.json", SOURCE / "readme.txt"]},
        "script_sha256": {str(p): sha256(p) for p in sorted(Path("evals/repeated").glob("*.py")) if p.name in ("data.py", "runner.py", "metrics.py")},
        "protocol_document_sha256": sha256(Path("docs/repeated-benchmark.md")),
        "concurrency": {"jobs": 6, "native_workers": 3, "cellpose_mps_workers": 1},
        "retries": "only existing schema/output-token retry; no outcome or transport retries",
        "preprocessing": "preserve original uint8 intensities and dimensions; grayscale replication only",
        "prior_exposure": "public pretrained-model training overlap unknown",
    }
    write_json(REPORT / "protocol.json", protocol)
    tasks = []
    for item in selected:
        name = Path(item["path"]).name
        truth = "dataset/groundtruth/" + name
        if truth not in annotation_paths:
            raise ValueError(f"Missing published whole-image annotation: {name}")
        tasks.extend([(item["path"], DATA / "source/images" / name), (truth, DATA / "source/labels" / name)])
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda t: download(*t), tasks))
    rows, metadata_rows = [], []
    (DATA / "images").mkdir(exist_ok=True)
    for item in selected:
        path = DATA / "source/images" / Path(item["path"]).name
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if image is None or image.dtype != np.uint8:
            raise ValueError(f"Unexpected source bit depth; preserve selection and investigate: {path.name}")
        if image.ndim == 3:
            if image.shape[2] not in (3, 4) or not np.array_equal(image[..., 0], image[..., 1]) or not np.array_equal(image[..., 0], image[..., 2]):
                raise ValueError("Unexpected non-grayscale scientific input")
            image = image[..., 0]
        if image.ndim != 2:
            raise ValueError("Expected 2D image")
        task_id = hashlib.sha256(item["path"].encode()).hexdigest()[:12]
        target = DATA / "images" / f"{task_id}.png"
        cv2.imwrite(str(target), cv2.cvtColor(image, cv2.COLOR_GRAY2BGR))
        if not np.array_equal(cv2.imread(str(target), 0), image):
            raise ValueError("Lossless input conversion failed")
        row = {"id": task_id, "image": str(target), "question": QUESTION, "image_sha256": sha256(target),
               "source_filename": path.name, "source_sha256": sha256(path),
               "annotation_sha256": sha256(DATA / "source/labels" / path.name),
               "height": image.shape[0], "width": image.shape[1]}
        rows.append(row)
        metadata_rows.append({"id": task_id, "metadata": attributes(item)})
    write_json(DATA / "inputs.json", rows)
    write_json(REPORT / "inputs.json", rows)
    write_json(REPORT / "strata.json", metadata_rows)
    write_json(REPORT / "input-freeze.json", {"sha256": sha256(DATA / "inputs.json"), "complete_at": datetime.now(timezone.utc).isoformat(), "annotations_decoded": False})
    print(f"Prepared {len(rows)} official test images; labels downloaded but not decoded.", flush=True)
