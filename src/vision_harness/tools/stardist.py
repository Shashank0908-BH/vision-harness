"""Pinned fluorescence-nucleus segmenter; no labels or provider calls."""

import hashlib
import importlib.metadata
import os
import time
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from ..contracts import Evidence
from ..tracing import write_json

CHECKPOINT = "2D_versatile_fluo"
WEIGHTS_SHA256 = "42202bd269c8106782316f1a2c75afb3f5ffa65e525c2e155ee0ced3a95da349"
CHECKPOINT_HASHES = {
    "weights_best.h5": WEIGHTS_SHA256,
    "config.json": "836da16282c3e0db1ba2e58f377e977419887ace8c737ebde16a094d58d50f74",
    "thresholds.json": "5cd6aac6e923f8659b63a9e297485920d45a59dad35371ddb8b6ae4be398d805",
}
PROFILES = {"default": None, "sensitive": 0.35, "conservative": 0.60}


def validate_step(step):
    if step.arguments.segmentation_profile not in PROFILES:
        raise ValueError("stardist requires segmentation_profile: default/sensitive/conservative")
    for key, value in step.arguments.model_dump().items():
        if key != "segmentation_profile" and value is not None:
            raise ValueError(f"{key} is not used by stardist; set it to null")


def probe(store):
    image = store.load("original")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return Evidence(
        evidence_id="probe",
        tool="microscopy_input_probe",
        version="1",
        input_artifact_id="original",
        parameters={},
        measurements={
            "width": image.shape[1],
            "height": image.shape[0],
            "replicated_grayscale": bool(
                np.array_equal(image[..., 0], image[..., 1])
                and np.array_equal(image[..., 0], image[..., 2])
            ),
            "intensity_percentiles": np.percentile(gray, [1, 50, 99, 99.8]).tolist(),
            "gray_stddev": float(gray.std()),
        },
        coordinate_system=store.coordinates("original"),
        artifact_ids=[],
        quality_flags=[
            "Intensity statistics alone do not establish biological identity or segmentation accuracy."
        ],
    )


@lru_cache(maxsize=1)
def load_model():
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    import tensorflow as tf
    from stardist.models import StarDist2D

    tf.config.set_visible_devices([], "GPU")
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    folder = Path("models/stardist").resolve()
    for name, expected in CHECKPOINT_HASHES.items():
        path = folder / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(
                "Missing or unexpected pinned StarDist checkpoint; prepare models/stardist"
            )
    return StarDist2D(config=None, name=folder.name, basedir=folder.parent)


def execute(step, input_id, evidence_id, store):
    validate_step(step)
    image = store.load(input_id)
    if store.records[input_id].get("kind") in {"binary_mask", "instance_labels"}:
        raise ValueError("StarDist requires the original intensity image or a crop, not a mask")
    if not np.array_equal(image[..., 0], image[..., 1]) or not np.array_equal(
        image[..., 0], image[..., 2]
    ):
        raise ValueError("This adapter requires single-channel fluorescence replicated as RGB")
    from csbdeep.utils import normalize

    started = time.perf_counter()
    model = load_model()
    profile = step.arguments.segmentation_profile
    probability = PROFILES[profile]
    if probability is None:
        probability = float(model.thresholds.prob)
    labels, details = model.predict_instances(
        normalize(image[..., 0], 1, 99.8), axes="YX", prob_thresh=probability, nms_thresh=0.3
    )
    if (
        labels.shape != image.shape[:2]
        or not np.issubdtype(labels.dtype, np.integer)
        or np.any(labels < 0)
    ):
        raise ValueError("Invalid specialist instance map")
    ids = np.unique(labels)
    ids = ids[ids > 0]
    origin = store.records[input_id]["origin"]
    overlay = image.copy()
    objects = []
    for label in ids:
        ys, xs = np.where(labels == label)
        color = np.random.default_rng(int(label)).integers(64, 256, 3)
        region = labels == label
        overlay[region] = (0.55 * overlay[region] + 0.45 * color).astype(np.uint8)
        objects.append(
            {
                "id": int(label),
                "area_pixels": int(len(xs)),
                "centroid": [float(xs.mean()), float(ys.mean())],
                "box": [
                    int(xs.min()),
                    int(ys.min()),
                    int(xs.max() - xs.min() + 1),
                    int(ys.max() - ys.min() + 1),
                ],
                "touches_border": bool(
                    xs.min() == 0
                    or ys.min() == 0
                    or xs.max() == image.shape[1] - 1
                    or ys.max() == image.shape[0] - 1
                ),
            }
        )
    directory = store.directory.parent / "evidence"
    directory.mkdir(exist_ok=True)
    map_path = directory / (evidence_id + "-labels.npz")
    np.savez_compressed(map_path, labels=labels.astype(np.int32), object_scores=details["prob"])
    write_json(directory / (evidence_id + "-instances.json"), objects)
    mask_id = store.save(
        (labels > 0).astype(np.uint8) * 255, evidence_id + "-mask", origin, kind="binary_mask"
    )
    overlay_id = store.save(overlay, evidence_id + "-overlay", origin, kind="instance_overlay")
    # Native label arrays stay separate: they must not be decoded as ordinary RGB inputs.
    areas = [o["area_pixels"] for o in objects]
    scores = np.asarray(details["prob"])
    return Evidence(
        evidence_id=evidence_id,
        tool="stardist",
        version=importlib.metadata.version("stardist"),
        input_artifact_id=input_id,
        parameters={
            "checkpoint": CHECKPOINT,
            "weights_sha256": WEIGHTS_SHA256,
            "segmentation_profile": profile,
            "probability_threshold": probability,
            "overlap_threshold": 0.3,
            "normalization_percentiles": [1, 99.8],
            "resize": None,
            "device": "cpu",
            "include_border_instances": True,
            "execution_seconds_including_first_load": time.perf_counter() - started,
        },
        measurements={
            "instance_count": len(objects),
            "target": "predicted fluorescent nuclei",
            "count_derivation": "Number of distinct positive instance IDs; no arithmetic correction or extrapolation",
            "full_original_coverage": input_id == "original",
            "foreground_fraction": float(np.mean(labels > 0)),
            "border_instance_count": sum(o["touches_border"] for o in objects),
            "area_pixels": {
                "minimum": min(areas, default=0),
                "median": float(np.median(areas)) if areas else 0,
                "maximum": max(areas, default=0),
            },
            "native_object_score": {
                "minimum": float(scores.min()) if len(scores) else None,
                "mean": float(scores.mean()) if len(scores) else None,
                "calibrated_count_confidence": False,
            },
            "raw_labels_path": str(map_path.relative_to(store.directory.parent)),
            "raw_labels_sha256": hashlib.sha256(map_path.read_bytes()).hexdigest(),
            "instances_path": f"evidence/{evidence_id}-instances.json",
        },
        coordinate_system=store.coordinates(input_id),
        artifact_ids=[mask_id, overlay_id],
        primary_artifact_id=mask_id,
        quality_flags=[
            "Pretrained on fluorescent nuclei; predicted instances are estimates, not validated identities.",
            "Touching nuclei may merge, fragments may split, dim nuclei may be missed.",
            "A nucleus count estimates cell count under a one-nucleus-per-cell assumption.",
            "Native object scores and threshold agreement are not calibrated count confidence.",
            "Cropped counts must not be extrapolated or summed over overlaps without explicit reconciliation.",
        ],
    )
