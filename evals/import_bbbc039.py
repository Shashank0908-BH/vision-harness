"""Prepare a preselected official-test cohort; never invent images or labels.

Download archives and freeze selection.json before calling prepare. Ground truth
stays outside the agent environment. The derived count task is not the published
BBBC039 segmentation metric.
"""

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import cv2
import numpy as np

from vision_harness.tracing import write_json

QUESTION = (
    "Count the nuclei in this fluorescence microscopy image of Hoechst-stained U2OS nuclei. "
    "Return your estimated total nucleus count as a number, including visible border nuclei."
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def decode_labels(rgb):
    """Official example: label equal red-channel values, full 2D connectivity."""
    red = rgb[..., 0]
    labels = np.zeros(red.shape, np.int32)
    offset = 0
    for value in np.unique(red):
        if value == 0:
            continue
        number, components = cv2.connectedComponents(
            (red == value).astype(np.uint8), connectivity=8
        )
        foreground = components > 0
        labels[foreground] = components[foreground] + offset
        offset += number - 1
    return labels


def to_display(gray):
    """Fixed contrast mapping for every arm; no spatial change or label access."""
    if gray.ndim != 2 or gray.dtype != np.uint16:
        raise ValueError("Expected the published 16-bit single-channel TIFF")
    low, high = np.percentile(gray, [1, 99.8])
    if high <= low:
        raise ValueError("Input has no usable percentile range; preserve selection, investigate")
    display = np.rint(np.clip((gray.astype(np.float64) - low) / (high - low), 0, 1) * 255)
    return display.astype(np.uint8), [float(low), float(high)]


def prepare(dataset, report):
    selection = json.loads((report / "selection.json").read_text())
    if (dataset / "manifest.jsonl").exists():
        raise ValueError("Frozen dataset already exists")
    source = dataset / "source"
    with zipfile.ZipFile(source / "metadata.zip") as archive:
        official = archive.read("metadata/test.txt").decode().splitlines()
    selected = sorted(
        official,
        key=lambda n: digest(("vision-adaptive-stardist-v1:" + n).encode()),
    )[:6]
    assert selected == selection["filenames"]
    assert digest((source / "metadata.zip").read_bytes()) == selection["metadata_sha256"]
    rows = []
    with (
        zipfile.ZipFile(source / "images.zip") as images,
        zipfile.ZipFile(source / "masks.zip") as masks,
    ):
        image_names = {
            Path(n).stem: n
            for n in images.namelist()
            if n.lower().endswith((".tif", ".tiff")) and not n.startswith("__MACOSX/")
        }
        mask_names = {
            Path(n).name: n
            for n in masks.namelist()
            if n.endswith(".png") and not n.startswith("__MACOSX/")
        }
        for index, name in enumerate(selected, 1):
            raw_image = images.read(image_names[Path(name).stem])
            gray = cv2.imdecode(np.frombuffer(raw_image, np.uint8), cv2.IMREAD_UNCHANGED)
            if gray.shape != (520, 696):
                raise ValueError("Unexpected source geometry")
            display, percentiles = to_display(gray)
            raw_mask = masks.read(mask_names[name])
            bgr = cv2.imdecode(np.frombuffer(raw_mask, np.uint8), cv2.IMREAD_COLOR)
            labels = decode_labels(bgr[..., ::-1])
            if labels.shape != gray.shape:
                raise ValueError("Image and mask geometry differ")
            count = int(np.count_nonzero(np.unique(labels) > 0))
            if count <= 0:
                raise ValueError(
                    "Zero-label target needs a separately declared metric; do not substitute another image"
                )
            task_id = digest(name.encode())[:12]
            relative = f"images/{task_id}.png"
            (dataset / "images").mkdir(exist_ok=True)
            (dataset / "annotations").mkdir(exist_ok=True)
            ok, png = cv2.imencode(".png", cv2.cvtColor(display, cv2.COLOR_GRAY2BGR))
            assert ok and np.array_equal(cv2.imdecode(png, 0), display)
            (dataset / relative).write_bytes(png.tobytes())
            np.savez_compressed(dataset / "annotations" / f"{task_id}.npz", labels=labels)
            rows.append(
                {
                    "id": task_id,
                    "family": "fluorescence_nucleus_count",
                    "split": "test",
                    "title": f"BBBC039 test image {index}",
                    "image": relative,
                    "question": QUESTION,
                    "expected": count,
                    "tolerance": 0,
                    "metric": "nuclei_count_percentage_error",
                    "source_filename": name,
                    "source_tiff_sha256": digest(raw_image),
                    "source_mask_sha256": digest(raw_mask),
                    "sha256": digest(png.tobytes()),
                    "display_percentiles": percentiles,
                    "annotation_labels_sha256": digest(
                        (dataset / "annotations" / f"{task_id}.npz").read_bytes()
                    ),
                }
            )
    (dataset / "manifest.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    write_json(report / "cohort.json", rows)
    # Deliberately do not display annotations while configuring the experiment.
    print(
        f"Prepared {len(rows)} frozen test images; annotation counts saved for verifier/report only"
    )


if __name__ == "__main__":
    prepare(Path(sys.argv[1]), Path(sys.argv[2]))
