"""Independent StarDist-library matching check; run after native.py completes."""

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
os.environ["MPLCONFIGDIR"] = str(ROOT / ".model-cache/matplotlib")
from stardist.matching import matching  # noqa: E402

REPORT = ROOT / "reports/stardist-audit-20260922"
DATA = ROOT / "evals/datasets/generated/kromp-repeated-20260922"
RUNS = ROOT / "runs/stardist-audit-native-20260922"
OLD = ROOT / "runs/kromp-repeated-20260922"
DISPUTED = "5ce7aa249ca6"


def main():
    assert (RUNS / "inference-finished.json").exists()
    inputs = {r["id"]: r for r in json.loads((DATA / "inputs.json").read_text())}
    prior = json.loads((ROOT / "reports/kromp-repeated-20260922/results.json").read_text())
    old_records = {(r["id"], r["repeat"]): r for r in prior["records"]}
    native = json.loads((REPORT / "native-results.json").read_text())
    protocol = json.loads((REPORT / "protocol.json").read_text())
    verified, scored = [], []
    for row in native:
        original = np.asarray(Image.open(DATA / "source/labels" / inputs[row["id"]]["source_filename"]))
        folder = RUNS / f'repeat-{row["repeat"]}' / row["id"] / row["variant"]
        pred = np.load(folder / "labels.npz", allow_pickle=False)["labels"]
        pid = protocol["variants"][row["variant"]]["prior_id"]
        if pid:
            check = matching(original, pred, thresh=0.5)._asdict()
            previous = old_records[row["id"], row["repeat"]]["segmentation"][pid]
            ok = all(check[k] == previous[k] for k in ["tp", "fp", "fn"])
            verified.append({"id": row["id"], "repeat": row["repeat"], "variant": row["variant"], "tp_fp_fn_equal_to_old_scorer": ok})
        truth = original
        if row["id"] == DISPUTED:
            truth = np.load(REPORT / "otherspecimen_3-components-diagnostic.npz")["labels"]
            assert np.array_equal(truth > 0, original > 0)
            assert len(np.unique(truth)) - 1 == 102
        metrics = {key: value.item() if isinstance(value, np.generic) else value
                   for key, value in matching(truth, pred, thresh=0.5)._asdict().items()}
        scored.append({**row, "expected": int(np.count_nonzero(np.unique(truth))), "matching": metrics})
    # Independently validate Cellpose's original saved matching too.
    for row in prior["records"]:
        truth = np.asarray(Image.open(DATA / "source/labels" / inputs[row["id"]]["source_filename"]))
        pred = np.load(OLD / f'repeat-{row["repeat"]}' / row["id"] / "routing/specialists/cellpose-sam/labels.npz")["labels"]
        check = matching(truth, pred, thresh=0.5)._asdict()
        previous = row["segmentation"]["cellpose-sam"]
        verified.append({"id": row["id"], "repeat": row["repeat"], "variant": "cellpose-sam", "tp_fp_fn_equal_to_old_scorer": all(check[k] == previous[k] for k in ["tp", "fp", "fn"])})
    result = {"official_matcher_checks": len(verified), "all_tp_fp_fn_equal": all(r["tp_fp_fn_equal_to_old_scorer"] for r in verified), "checks": verified, "native_scored": scored}
    (REPORT / "independent-matching.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("checks", "native_scored")}, indent=2))


if __name__ == "__main__":
    main()
