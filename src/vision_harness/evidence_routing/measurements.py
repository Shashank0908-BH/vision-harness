"""Label-free measurements; no benchmark labels or correctness thresholds."""

import itertools
from pathlib import Path

import numpy as np

from ..contracts import Answer
from ..routing.catalog import sha256
from ..routing.executor import validate_labels
from .contracts import Candidate


def visual_candidate(answer: Answer, image_sha256: str, model: str) -> Candidate | None:
    if answer.status != "answered":
        if answer.value is not None:
            raise ValueError("An unanswered visual candidate cannot carry a count")
        return None
    if isinstance(answer.value, bool) or not isinstance(answer.value, (int, float)):
        raise ValueError("Visual candidate must contain a numeric count")
    if not set(answer.evidence_ids) <= {"original"}:
        raise ValueError("Visual-only answer cited evidence it was never given")
    return Candidate(
        plan_id="vanilla-astra",
        kind="visual_estimate",
        value=answer.value,
        evidence_id="original",
        model_family=model,
        checkpoint=None,
        parameters={},
        measurements={"instance_map_available": False},
        limitations=answer.limitations
        + ["Visual estimate without an instance map or measured count."],
        provenance={"image_sha256": image_sha256, "generated_before_specialist_outputs": True},
    )


def mask_candidate(procedure, evidence: dict, store, directory: Path):
    path = directory / "specialists" / procedure.plan_id / "labels.npz"
    original = Path(store.records["original"]["path"])
    image_hash = sha256(original)
    if evidence["worker"]["image_sha256"] != image_hash:
        raise ValueError("Candidate was measured on a different image")
    if evidence["worker"]["labels_sha256"] != sha256(path):
        raise ValueError("Candidate label checksum mismatch")
    image = store.load("original")
    with np.load(path, allow_pickle=False) as archive:
        labels = archive["labels"]
    ids = validate_labels(labels, image.shape[:2])
    if (
        evidence["procedure_id"] != procedure.plan_id
        or evidence["evidence_id"] != procedure.plan_id
    ):
        raise ValueError("Candidate identity differs from executed procedure")
    if isinstance(evidence["count"], bool) or len(ids) != evidence["count"]:
        raise ValueError("Candidate count differs from mask")
    if evidence["coordinates"] != store.coordinates("original"):
        raise ValueError("Candidate coordinates differ from original image")
    foreground = labels > 0
    unique, areas = np.unique(labels, return_counts=True)
    areas = areas[unique > 0]
    edge_ids = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    gray = image[..., 0]
    measurements = {
        "instance_map_available": True,
        "count": len(ids),
        "coordinates": store.coordinates("original"),
        "foreground_fraction": float(foreground.mean()),
        "border_instances": int(np.count_nonzero(edge_ids)),
        "area_quantiles_pixels": [float(x) for x in np.quantile(areas, [0, 0.25, 0.5, 0.75, 1])]
        if len(areas)
        else None,
        "foreground_mean_intensity_8bit": float(gray[foreground].mean())
        if foreground.any()
        else None,
        "background_mean_intensity_8bit": float(gray[~foreground].mean())
        if (~foreground).any()
        else None,
        "quality_probability": None,
    }
    return Candidate(
        plan_id=procedure.plan_id,
        kind="instance_measurement",
        value=len(ids),
        evidence_id=procedure.plan_id,
        model_family=procedure.model,
        checkpoint=procedure.checkpoint,
        parameters=procedure.parameters,
        measurements=measurements,
        limitations=procedure.limitations
        + ["Geometry and intensity summaries are not calibrated accuracy estimates."],
        provenance={
            "image_sha256": image_hash,
            "labels_sha256": sha256(path),
            "checkpoint_files": [f.model_dump() for f in procedure.files],
            "worker_versions": evidence["worker"].get("packages"),
            "worker_device": evidence["worker"].get("device"),
            "coverage": "entire original image",
        },
    ), labels


def disagreement(candidates: list[Candidate], masks: dict[str, np.ndarray]) -> dict:
    pairs = []
    for a, b in itertools.combinations(candidates, 2):
        denominator = max(a.value, b.value)
        entry = {
            "candidate_ids": [a.plan_id, b.plan_id],
            "absolute_count_difference": abs(a.value - b.value),
            "relative_count_difference": abs(a.value - b.value) / denominator
            if denominator
            else 0.0,
            "same_specialist_weights": bool(
                a.checkpoint and a.checkpoint == b.checkpoint and a.model_family == b.model_family
            ),
            "foreground_iou": None,
        }
        if a.plan_id in masks and b.plan_id in masks:
            if masks[a.plan_id].shape != masks[b.plan_id].shape:
                raise ValueError("Cannot compare masks in different image geometry")
            left, right = masks[a.plan_id] > 0, masks[b.plan_id] > 0
            union = np.count_nonzero(left | right)
            entry["foreground_iou"] = (
                float(np.count_nonzero(left & right) / union) if union else None
            )
        pairs.append(entry)
    return {
        "pairs": pairs,
        "relative_difference_denominator": "larger count; zero for two zeros",
        "limitations": [
            "Agreement does not establish correctness.",
            "Profiles sharing weights are not independent votes.",
            "Foreground IoU does not measure individual split/merge errors; empty union is undefined.",
        ],
    }
