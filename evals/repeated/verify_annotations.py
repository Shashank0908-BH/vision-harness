"""Independent reference count verification; use the StarDist environment for Pillow."""

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

report = Path(__file__).resolve().parents[2] / "reports/kromp-repeated-20260922"
root = report.parents[1]
assert (root / "runs/kromp-repeated-20260922/inference-finished.json").exists()
references = json.loads((report / "references.json").read_text())
checks = []
for row in references:
    path = (
        root
        / "evals/datasets/generated/kromp-repeated-20260922/source/labels"
        / row["source_filename"]
    )
    labels = np.asarray(Image.open(path))
    count = int(np.count_nonzero(np.unique(labels) > 0))
    assert count == row["count"], row["id"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row["annotation_sha256"]
    checks.append(
        {
            "id": row["id"],
            "pillow_count": count,
            "matches_scoring_decoder": True,
            "dtype": str(labels.dtype),
            "shape": list(labels.shape),
        }
    )
(report / "independent-annotation-check.json").write_text(
    json.dumps(
        {
            "decoder": "Pillow, distinct positive integer labels; independent of OpenCV scoring decoder",
            "checks": checks,
        },
        indent=2,
    )
    + "\n"
)
print("Independent Pillow annotation decoding matched all", len(checks), "reference counts.")
