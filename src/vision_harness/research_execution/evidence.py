"""Independent artifact checks and count extraction; never uses reference labels."""

import base64
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from ..tracing import write_json


def image_content(path):
    return {"type": "input_image", "image_url": "data:image/png;base64," +
            base64.b64encode(Path(path).read_bytes()).decode(), "detail": "high"}


def probe(raw):
    image = cv2.imread(str(raw), cv2.IMREAD_UNCHANGED)
    if image is None or image.ndim != 2 or image.dtype != np.uint16:
        raise ValueError("Expected a 2D original uint16 TIFF")
    return {"path": "/data/input.tif", "shape": list(image.shape),
            "dtype": str(image.dtype), "channels": 1, "min": int(image.min()),
            "max": int(image.max()), "percentiles": dict(zip(["p1", "p50", "p99", "p99.8"], np.percentile(image, [1, 50, 99, 99.8]).tolist(), strict=True)),
            "spatial_calibration": "not supplied", "preview_mapping": "1/99.8 percentile to uint8, unchanged geometry",
            "sha256": hashlib.sha256(Path(raw).read_bytes()).hexdigest()}


def inspect_artifacts(folder, outcome, original_shape, preview):
    # Fixed paths are part of the contract; don't follow model-supplied paths outside this round.
    labels_path = folder / "labels.npz"
    metadata_path = folder / "execution-metadata.json"
    if labels_path.is_symlink() or metadata_path.is_symlink():
        raise ValueError("Scientific outputs cannot be symlinks")
    with np.load(labels_path, allow_pickle=False) as archive:
        labels = archive["labels"]
    if list(labels.shape) != list(original_shape):
        raise ValueError("Instance map was not restored to original image geometry")
    if not np.issubdtype(labels.dtype, np.integer) or np.any(labels < 0):
        raise ValueError("Expected nonnegative integer instance IDs")
    ids, areas = np.unique(labels[labels > 0], return_counts=True)
    fragmented = []
    for ident in ids:
        components, _ = cv2.connectedComponents((labels == ident).astype(np.uint8), connectivity=8)
        if components > 2:
            fragmented.append({"id": int(ident), "components": components - 1})
    metadata = json.loads(metadata_path.read_text())
    if not isinstance(metadata, dict) or not metadata:
        raise ValueError("Missing actual execution metadata")
    overlay = cv2.imread(str(preview))
    boundaries = np.zeros(labels.shape, np.uint8)
    boundaries[1:] |= ((labels[1:] != labels[:-1]) & (labels[1:] > 0)).astype(np.uint8)
    boundaries[:, 1:] |= ((labels[:, 1:] != labels[:, :-1]) & (labels[:, 1:] > 0)).astype(np.uint8)
    overlay[boundaries > 0] = [0, 255, 0]
    cv2.imwrite(str(folder / "overlay.png"), overlay)
    measured = {"plan_id": outcome.plan_id, "count": len(ids),
                "count_rule": "unique positive instance IDs, including border instances",
                "shape": list(labels.shape), "dtype": str(labels.dtype),
                "minimum_label": int(labels.min()), "maximum_label": int(labels.max()),
                "independent_checks": {"original_geometry": True, "integer_dtype": True,
                    "nonnegative_ids": True, "count_recomputed_from_saved_labels": True},
                "foreground_fraction": float(np.mean(labels > 0)),
                "area_percentiles": np.percentile(areas, [0, 25, 50, 75, 100]).tolist() if len(areas) else [],
                "fragmented_instance_ids": fragmented, "fragmentation_repaired": False,
                "labels_sha256": hashlib.sha256(labels_path.read_bytes()).hexdigest(),
                "execution_metadata": metadata, "program_unchanged": outcome.program_executed_unchanged}
    write_json(folder / "measured.json", measured)
    return measured
