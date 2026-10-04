"""Reference-label checks. Disconnected regions require review, not auto-counting."""

import cv2
import numpy as np


def audit_instance_labels(labels: np.ndarray) -> dict:
    if labels.ndim != 2 or labels.dtype.kind not in "ui" or np.any(labels < 0):
        raise ValueError("Expected a nonnegative integer 2D instance map")
    ids = np.unique(labels)
    ids = ids[ids > 0]
    multipart = []
    total_components = 0
    for label in ids:
        n, _, stats, _ = cv2.connectedComponentsWithStats(
            (labels == label).astype(np.uint8), connectivity=8
        )
        total_components += n - 1
        if n > 2:
            multipart.append({
                "label": int(label),
                "component_areas": sorted(stats[1:, cv2.CC_STAT_AREA].tolist(), reverse=True),
            })
    return {
        "unique_positive_ids": len(ids),
        "per_id_connected_components": total_components,
        "multipart_labels": multipart,
        "requires_reference_review": bool(multipart),
        "policy": "Do not replace the instance count with a component count automatically. "
        "Fragments, occlusion and reused IDs require source verification.",
    }
