"""Deterministic image measurements. No semantic object claims or invented confidence."""

import math

import cv2
import numpy as np

from ..artifacts import ArtifactStore
from ..contracts import Evidence, Step


def color_mask(image: np.ndarray, color: str, saturation_min=80, value_min=40) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    if color == "any":
        # Explicit white-background assumption; includes dark and colored foreground.
        selected = (saturation >= saturation_min) | (value < 200)
    else:
        ranges = {"red": ((0, 10), (170, 179)), "green": ((35, 85),), "blue": ((90, 135),)}
        selected = np.zeros(hue.shape, dtype=bool)
        for low, high in ranges[color]:
            selected |= (hue >= low) & (hue <= high)
        selected &= (saturation >= saturation_min) & (value >= value_min)
    return selected.astype(np.uint8) * 255


def probe(store: ArtifactStore) -> Evidence:
    image = store.load("original")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    coverage = {}
    for color in ("red", "green", "blue"):
        fractions = [float(np.mean(color_mask(image, color, s) > 0)) for s in (60, 80, 100)]
        coverage[color] = {
            "fraction_at_saturation_80": fractions[1],
            "fraction_range_across_thresholds": max(fractions) - min(fractions),
        }
    return Evidence(
        evidence_id="probe",
        tool="fixed_probes",
        version=cv2.__version__,
        input_artifact_id="original",
        parameters={"saturation_thresholds": [60, 80, 100], "value_min": 40},
        measurements={
            "gray_stddev": float(gray.std()),
            "color_coverage": coverage,
            "laplacian_variance": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        },
        coordinate_system=store.coordinates("original"),
        artifact_ids=[],
        quality_flags=[
            "Color coverage does not establish object identity or separation.",
            "Laplacian variance is an uncalibrated sharpness diagnostic, not a blur verdict.",
        ],
    )


def validate_step(step: Step) -> None:
    a = step.arguments
    required = {
        "components": ("color", "min_area", "saturation_min", "value_min"),
        "watershed": ("color", "min_area", "saturation_min", "value_min", "marker_fraction"),
        "crop": ("box",),
        "measure": ("points",),
    }[step.tool]
    for field, value in a.model_dump().items():
        if field in required and value is None:
            raise ValueError(f"{step.tool} requires {field}")
        if field not in required and value is not None:
            raise ValueError(f"{field} is not used by {step.tool}; set it to null")


def execute(step: Step, input_id: str, evidence_id: str, store: ArtifactStore) -> Evidence:
    validate_step(step)
    image = store.load(input_id)
    height, width = image.shape[:2]
    a = step.arguments
    parameters = a.model_dump(exclude_none=True)
    artifacts, flags = [], []
    measurements = {}
    primary = None
    origin = store.records[input_id]["origin"]
    if step.tool == "crop":
        x, y, w, h = a.box
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
            raise ValueError("Crop rectangle is outside the input image")
        primary = store.save(
            image[y : y + h, x : x + w], evidence_id + "-crop", (origin[0] + x, origin[1] + y)
        )
        artifacts = [primary]
        measurements = {"box": list(a.box)}
    elif step.tool == "measure":
        for x, y in a.points:
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError("Measurement point is outside the input image")
        measurements = {"distance_pixels": math.dist(*a.points), "points": a.points}
        flags = [
            "Point locations were supplied by the planner; only the distance arithmetic is verified."
        ]
    else:
        mask = color_mask(image, a.color, a.saturation_min, a.value_min)
        _, labels = cv2.connectedComponents(mask, connectivity=8)
        if step.tool == "watershed" and np.any(mask):
            distance = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
            seeds = (distance > a.marker_fraction * distance.max()).astype(np.uint8)
            _, markers = cv2.connectedComponents(seeds)
            markers = markers + 1
            markers[(mask > 0) & (seeds == 0)] = 0
            labels = cv2.watershed(image.copy(), markers)
            labels = np.where((labels > 1) & (mask > 0), labels - 1, 0)
            flags.append(
                "Watershed boundaries and marker fraction can change area and instance counts."
            )
        components = []
        overlay = image.copy()
        clean_mask = np.zeros(mask.shape, np.uint8)
        for label in np.unique(labels):
            if label <= 0:
                continue
            ys, xs = np.where(labels == label)
            if len(xs) < a.min_area:
                continue
            x, y, w, h = (
                int(xs.min()),
                int(ys.min()),
                int(xs.max() - xs.min() + 1),
                int(ys.max() - ys.min() + 1),
            )
            border = x == 0 or y == 0 or x + w == width or y + h == height
            components.append(
                {
                    "id": len(components) + 1,
                    "box": [x, y, w, h],
                    "area_pixels": len(xs),
                    "centroid": [float(xs.mean()), float(ys.mean())],
                    "touches_border": border,
                }
            )
            clean_mask[ys, xs] = 255
            cv2.rectangle(overlay, (x, y), (x + w - 1, y + h - 1), (0, 0, 0), 1)
            cv2.putText(
                overlay,
                str(len(components)),
                (x, max(12, y)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 0, 0),
                1,
            )
        primary = store.save(clean_mask, evidence_id + "-mask", origin)
        artifacts = [primary, store.save(overlay, evidence_id + "-overlay", origin)]
        measurements = {
            "component_count": len(components),
            "components": components,
            "foreground_fraction": float(np.mean(clean_mask > 0)),
        }
        flags += ["Pixel components are not verified semantic objects."]
        if a.color == "any":
            flags.append("Foreground segmentation assumes a light, low-saturation background.")
        if any(c["touches_border"] for c in components):
            flags.append("Some components touch the image or crop border.")
    return Evidence(
        evidence_id=evidence_id,
        tool=step.tool,
        version=cv2.__version__,
        input_artifact_id=input_id,
        parameters=parameters,
        measurements=measurements,
        coordinate_system=store.coordinates(input_id),
        artifact_ids=artifacts,
        primary_artifact_id=primary,
        quality_flags=flags,
    )
