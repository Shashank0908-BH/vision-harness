"""Map the published vector shapes to the disputed TIFF; diagnostic only.

Uses system Python with fontTools, NumPy, Pillow and OpenCV. Curves are sampled
for an approximate overlap check, not a replacement benchmark segmentation.
"""

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.svgLib.path import parse_path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/stardist-audit-20260922"
DATA = ROOT / "evals/datasets/generated/kromp-repeated-20260922"


class FlattenPen(BasePen):
    def __init__(self):
        super().__init__(None)
        self.contours = []
        self.current = []

    def _moveTo(self, point):
        if self.current:
            self.contours.append(self.current)
        self.current = [point]

    def _lineTo(self, point):
        self.current.append(point)

    def _curveToOne(self, p1, p2, p3):
        p0 = np.asarray(self.current[-1])
        p1, p2, p3 = map(np.asarray, (p1, p2, p3))
        for t in np.linspace(0, 1, 33)[1:]:
            self.current.append((1-t)**3*p0 + 3*(1-t)**2*t*p1 + 3*(1-t)*t*t*p2 + t**3*p3)

    def _qCurveToOne(self, p1, p2):
        p0 = np.asarray(self.current[-1])
        p1, p2 = map(np.asarray, (p1, p2))
        for t in np.linspace(0, 1, 33)[1:]:
            self.current.append((1-t)**2*p0 + 2*(1-t)*t*p1 + t*t*p2)

    def _closePath(self):
        if self.current:
            self.contours.append(self.current)
            self.current = []

    def _endPath(self):
        self._closePath()


def main():
    source = Path("/tmp/kromp-otherspecimen-3.svg")
    svg = REPORT / "otherspecimen_3.svg"
    svg.write_bytes(source.read_bytes())
    root = ET.parse(svg).getroot()
    group = next(g for g in root.iter() if g.attrib.get("id") == "Single_nuclei")
    truth = np.asarray(Image.open(DATA / "source/labels/otherspecimen_3.tif"))
    shapes, records = [], []
    for i, node in enumerate(group, 1):
        tag = node.tag.split("}")[-1]
        assert "transform" not in node.attrib
        if tag in ("polygon", "polyline"):
            points = [float(v) for v in re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", node.attrib["points"])]
            contours = [np.asarray(points).reshape(-1, 2)]
        elif tag == "path":
            pen = FlattenPen()
            parse_path(node.attrib["d"], pen)
            pen._endPath()
            contours = pen.contours
        else:
            raise ValueError(tag)
        mask = np.zeros(truth.shape, np.uint8)
        # Coordinates are kept in the image's native SVG coordinate system.
        cv2.fillPoly(mask, [np.rint(c).astype(np.int32) for c in contours], 1)
        labels, counts = np.unique(truth[mask.astype(bool)], return_counts=True)
        positive = [(int(label_id), int(counts[pos])) for pos, label_id in enumerate(labels) if label_id > 0]
        label, covered = max(positive, key=lambda pair: pair[1]) if positive else (0, 0)
        records.append({"shape": i, "tag": tag, "rasterized_area": int(mask.sum()),
                        "dominant_tiff_label": label, "fraction_inside_dominant_label": covered / int(mask.sum())})
        shapes.append(mask.astype(bool))
    overlap = []
    for i, first in enumerate(shapes):
        for j in range(i+1, len(shapes)):
            intersection = int(np.logical_and(first, shapes[j]).sum())
            if intersection:
                overlap.append({"first": i+1, "second": j+1,
                                "iou": intersection / int(np.logical_or(first, shapes[j]).sum())})
    result = {
        "source": "https://ftp.ebi.ac.uk/biostudies/fire/S-BIAD/634/S-BIAD634/Files/dataset/groundtruth_svgs/otherspecimen_3.svg",
        "sha256": hashlib.sha256(svg.read_bytes()).hexdigest(),
        "svg_shapes": len(shapes), "types": dict(Counter(r["tag"] for r in records)),
        "distinct_tiff_ids": len(np.unique(truth))-1,
        "shapes_per_dominant_tiff_id": dict(Counter(r["dominant_tiff_label"] for r in records)),
        "minimum_fraction_inside_dominant_label": min(r["fraction_inside_dominant_label"] for r in records),
        "largest_pairwise_shape_iou": max(r["iou"] for r in overlap),
        "caveat": "Approximate rasterization checks correspondence only; it is not used as a segmentation reference. Six redundant elements and two contours absent from TIFF explain why raw SVG element count is not the released TIFF object count.",
        "records": records, "overlapping_shape_pairs": overlap,
    }
    (REPORT / "svg-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    np.savez_compressed(REPORT / "svg-shapes-diagnostic.npz", masks=np.stack(shapes))
    # Retain the first contour in each near-identical group. All other pairs have
    # IoU < 0.1, so the 0.95 duplicate cutoff is far from an ambiguous boundary.
    redundant = set()
    for pair in overlap:
        if pair["iou"] > 0.95 and pair["first"] not in redundant:
            redundant.add(pair["second"])
    components = np.zeros(truth.shape, np.uint16)
    total = 0
    for value in np.unique(truth)[1:]:
        n, regions = cv2.connectedComponents((truth == value).astype(np.uint8), connectivity=8)
        for k in range(1, n):
            total += 1
            components[regions == k] = total
    correspondence = []
    for i, mask in enumerate(shapes, 1):
        if i in redundant:
            continue
        labels, counts = np.unique(components[mask], return_counts=True)
        positive = [(int(label_id), int(counts[pos])) for pos, label_id in enumerate(labels) if label_id > 0]
        label, covered = max(positive, key=lambda pair: pair[1]) if positive else (0, 0)
        correspondence.append({"svg_shape": i, "component": label,
                               "fraction": covered / int(mask.sum())})
    matched = [r for r in correspondence if r["fraction"] > 0.8]
    assert len(matched) == len({r["component"] for r in matched}) == total == 102
    np.savez_compressed(REPORT / "otherspecimen_3-components-diagnostic.npz", labels=components)
    (REPORT / "svg-component-correspondence.json").write_text(json.dumps({
        "components": total, "unique_svg_contours_at_iou_0p95": len(correspondence),
        "omitted_duplicate_elements": sorted(redundant), "matched_components": len(matched),
        "policy": "Repair only this source-verified TIFF. Do not split disconnected components globally.",
        "mapping": correspondence,
    }, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("records", "overlapping_shape_pairs", "shapes_per_dominant_tiff_id")}, indent=2))
    print("Shapes per TIFF label:", Counter(result["shapes_per_dominant_tiff_id"].values()))


if __name__ == "__main__":
    main()
