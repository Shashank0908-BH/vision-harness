"""Execute allowlisted procedures and derive evidence from actual instance maps."""

import json
import os
import subprocess
import time
from pathlib import Path

import numpy as np

from ..tracing import write_json
from .catalog import ROOT, sha256, verify_procedure
from .contracts import Procedure


def input_probe(image: np.ndarray) -> dict:
    gray = image[..., 0]
    return {
        "width": image.shape[1], "height": image.shape[0],
        "replicated_grayscale": bool(
            np.array_equal(gray, image[..., 1]) and np.array_equal(gray, image[..., 2])
        ),
        "distinct_levels": int(len(np.unique(gray))),
        "usable_range": bool(len(np.unique(gray)) > 8 and np.std(gray) > 1),
        "pixel_statistics_do_not_establish_modality": True,
    }


def validate_labels(labels: np.ndarray, shape: tuple) -> list[int]:
    if labels.shape != shape or not np.issubdtype(labels.dtype, np.integer):
        raise ValueError("Instance map must be an integer array in original image coordinates")
    if np.any(labels < 0) or np.max(labels, initial=0) > np.iinfo(np.int32).max:
        raise ValueError("Invalid instance label range")
    return [int(v) for v in np.unique(labels) if v > 0]


def worker_environment() -> dict:
    env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG", "SYSTEMROOT") if key in os.environ}
    env.update(TF_CPP_MIN_LOG_LEVEL="2", KERAS_HOME=str(ROOT / ".model-cache/keras"))
    return env


def execute(procedure: Procedure, store, trace, directory: Path) -> dict:
    verify_procedure(procedure)
    output = directory / "specialists" / procedure.plan_id
    output.mkdir(parents=True, exist_ok=False)
    original = Path(store.records["original"]["path"]).resolve()
    request = {
        "root": str(ROOT), "procedure": procedure.model_dump(),
        "image": str(original), "image_sha256": sha256(original),
        "output": str(output.resolve()),
    }
    write_json(output / "request.json", request)
    call_id = procedure.plan_id
    trace.emit("tool_started", {"call_id": call_id, "step": {"tool": procedure.adapter, "procedure": procedure.model_dump()}})
    start = time.monotonic()
    try:
        with (output / "worker.log").open("w") as log:
            subprocess.run(
                [str(ROOT / procedure.python), str(Path(__file__).with_name("worker.py")),
                 "--request", str((output / "request.json").resolve())],
                cwd=ROOT, env=worker_environment(), stdout=log, stderr=subprocess.STDOUT,
                check=True, timeout=240,
            )
        metadata = json.loads((output / "worker-result.json").read_text())
        if metadata["image_sha256"] != sha256(original) or metadata["labels_sha256"] != sha256(output / "labels.npz"):
            raise ValueError("Worker artifact integrity mismatch")
        image = store.load("original")
        with np.load(output / "labels.npz", allow_pickle=False) as data:
            labels = data["labels"]
        ids = validate_labels(labels, image.shape[:2])
        overlay, objects = image.copy(), []
        for instance_id in ids:
            mask = labels == instance_id
            ys, xs = np.where(mask)
            color = np.random.default_rng(instance_id).integers(64, 256, 3)
            overlay[mask] = (.55 * overlay[mask] + .45 * color).astype(np.uint8)
            objects.append({
                "id": instance_id, "area_pixels": int(len(xs)),
                "centroid_xy": [float(xs.mean()), float(ys.mean())],
                "box_xywh": [int(xs.min()), int(ys.min()), int(xs.max()-xs.min()+1), int(ys.max()-ys.min()+1)],
                "touches_border": bool(xs.min() == 0 or ys.min() == 0 or xs.max() == image.shape[1]-1 or ys.max() == image.shape[0]-1),
            })
        write_json(output / "instances.json", objects)
        overlay_id = store.save(overlay, procedure.plan_id + "-overlay")
        evidence = {
            "evidence_id": call_id, "procedure_id": procedure.plan_id,
            "count": len(ids), "count_rule": "number of unique positive instance IDs, including border instances",
            "coverage": "entire original image", "coordinates": store.coordinates("original"),
            "foreground_fraction": float(np.mean(labels > 0)),
            "border_instances": sum(o["touches_border"] for o in objects),
            "largest_instance_fraction": max((o["area_pixels"] for o in objects), default=0) / labels.size,
            "median_area_pixels": float(np.median([o["area_pixels"] for o in objects])) if objects else None,
            "overlay_id": overlay_id, "artifacts_directory": str(output),
            "elapsed_seconds": time.monotonic() - start, "worker": metadata,
            "calibrated_count_confidence": None,
            "limitations": procedure.limitations,
        }
        write_json(output / "evidence.json", evidence)
        trace.emit("evidence", evidence)
        return evidence
    except Exception as error:
        trace.emit("tool_error", {"call_id": call_id, "error": str(error)})
        raise
