"""Hidden verifier: executes in a fresh container after the agent has stopped."""

import json
from pathlib import Path

import numpy as np


def match_instances(truth, prediction, threshold=0.5):
    if truth.shape != prediction.shape or prediction.dtype.kind not in "ui" or np.any(prediction < 0):
        raise ValueError("Invalid prediction geometry or instance IDs")
    gt_ids, gt = np.unique(truth, return_inverse=True)
    pr_ids, pr = np.unique(prediction, return_inverse=True)
    overlap = np.bincount(gt.ravel()*len(pr_ids)+pr.ravel(),
        minlength=len(gt_ids)*len(pr_ids)).reshape(len(gt_ids), len(pr_ids))
    union = overlap.sum(axis=1)[:, None] + overlap.sum(axis=0)[None, :] - overlap
    iou = np.divide(overlap, union, out=np.zeros_like(overlap, dtype=float), where=union > 0)
    iou = iou[gt_ids > 0][:, pr_ids > 0]
    neighbors = [np.flatnonzero(row >= threshold).tolist() for row in iou]
    matched = {}

    def augment(g, seen):
        for p in neighbors[g]:
            if p not in seen:
                seen.add(p)
                if p not in matched or augment(matched[p], seen):
                    matched[p] = g
                    return True
        return False

    tp = sum(augment(g, set()) for g in range(len(neighbors)))
    ng, npred = iou.shape
    return {"tp": tp, "fn": ng-tp, "fp": npred-tp,
            "f1": 2*tp/(ng+npred) if ng+npred else 1,
            "iou_threshold": threshold}


def grade(output=Path("/output"), tests=Path("/tests"), destination=Path("/logs/verifier")):
    truth = np.load(tests / "reference.npz", allow_pickle=False)["labels"]
    expected = int(np.count_nonzero(np.unique(truth) > 0))
    result = {"expected": expected, "count": None, "answered": False, "within_10_percent": False,
              "percentage_error": None, "segmentation": None}
    try:
        answer = json.loads((output / "answer.json").read_text())
        count = answer.get("count")
        valid = answer.get("status") == "answered" and type(count) is int and count >= 0
        result.update(answer=answer)
        if valid and answer.get("mode") == "full":
            prediction = np.load(output / "labels.npz", allow_pickle=False)["labels"]
            measured = int(np.count_nonzero(np.unique(prediction) > 0))
            if measured != count:
                raise ValueError("Claimed count differs from final instance map")
            result["segmentation"] = match_instances(truth, prediction)
        if valid:
            error = abs(count-expected)/expected * 100
            result.update(count=count, answered=True, percentage_error=error,
                          within_10_percent=error <= 10)
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "grading.json").write_text(json.dumps(result, indent=2)+"\n")
    (destination / "reward.json").write_text(json.dumps({"within_10_percent": float(result["within_10_percent"]),
        "answered": float(result["answered"])}))
    return result


if __name__ == "__main__":
    grade()
