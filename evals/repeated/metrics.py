"""Repeated measurements, failure-aware summaries and instance matching."""

import json
import statistics

import cv2
import numpy as np

from vision_harness.routing.catalog import load_catalog, sha256
from vision_harness.tracing import write_json

from .data import CATALOG, DATA, REPEATS, REPORT, RUNS


def numeric_answer(answer):
    value = answer.get("value")
    return value if answer.get("status") == "answered" and isinstance(value, (int, float)) and not isinstance(value, bool) and np.isfinite(value) and value >= 0 else None


def match_instances(truth, prediction, threshold=.5):
    if truth.shape != prediction.shape or truth.ndim != 2:
        raise ValueError("Predicted and reference instance maps must share 2D geometry")
    if truth.dtype.kind not in "ui" or prediction.dtype.kind not in "ui" or np.any(truth < 0) or np.any(prediction < 0):
        raise ValueError("Instance labels must be nonnegative integers")
    gt_ids, gt = np.unique(truth, return_inverse=True)
    pr_ids, pr = np.unique(prediction, return_inverse=True)
    overlap = np.bincount(gt.ravel()*len(pr_ids)+pr.ravel(), minlength=len(gt_ids)*len(pr_ids)).reshape(len(gt_ids), len(pr_ids))
    union = overlap.sum(axis=1)[:, None] + overlap.sum(axis=0)[None, :] - overlap
    iou = np.divide(overlap, union, out=np.zeros_like(overlap, dtype=float), where=union > 0)
    iou = iou[gt_ids > 0][:, pr_ids > 0]
    neighbors = [np.flatnonzero(row >= threshold).tolist() for row in iou]
    matched = {}

    def augment(g, visited):
        for p in neighbors[g]:
            if p in visited:
                continue
            visited.add(p)
            if p not in matched or augment(matched[p], visited):
                matched[p] = g
                return True
        return False

    tp = sum(augment(g, set()) for g in range(len(neighbors)))
    n_gt, n_pred = iou.shape
    fp, fn = n_pred-tp, n_gt-tp
    return {"tp": tp, "fp": fp, "fn": fn, "truth_instances": n_gt, "predicted_instances": n_pred,
            "precision": tp/n_pred if n_pred else (1.0 if not n_gt else 0.0),
            "recall": tp/n_gt if n_gt else 1.0,
            "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.0,
            "instance_matching_score": tp/(tp+fp+fn) if tp+fp+fn else 1.0,
            "matched_mean_iou": float(np.mean([iou[g, p] for p, g in matched.items()])) if matched else None,
            "iou_threshold": threshold}


def bootstrap_mean(values, seed=2026092203, draws=10000):
    if not values:
        return None
    array = np.asarray(values, dtype=float)
    samples = np.random.default_rng(seed).choice(array, (draws, len(array)), replace=True).mean(axis=1)
    return {"mean": float(array.mean()), "ci95": [float(v) for v in np.percentile(samples, [2.5, 97.5])],
            "image_clusters": len(array), "draws": draws, "unit": "images, averaging repetitions within image; not independent patients"}


def summarize(records, arm, expected_repeats=REPEATS):
    valid = [r for r in records if r["values"].get(arm) is not None]
    errors = [abs(r["values"][arm]-r["expected"])/r["expected"]*100 for r in valid]
    repeats = []
    for repetition in range(1, expected_repeats+1):
        subset = [r for r in records if r["repeat"] == repetition]
        answered = [r for r in subset if r["values"].get(arm) is not None]
        errs = [abs(r["values"][arm]-r["expected"])/r["expected"]*100 for r in answered]
        repeats.append({"repeat": repetition, "answered": len(answered), "total": len(subset),
                        "full_cohort_mape": statistics.mean(errs) if errs and len(answered) == len(subset) else None,
                        "conditional_mape": statistics.mean(errs) if errs else None})
    repeat_maps = [r["full_cohort_mape"] for r in repeats]
    per_image = {}
    for r in records:
        per_image.setdefault(r["id"], []).append(r)
    cluster_errors = []
    prediction_sds = []
    for rows in per_image.values():
        vals = [r["values"].get(arm) for r in rows]
        if all(v is not None for v in vals) and len(vals) == expected_repeats:
            cluster_errors.append(statistics.mean(abs(v-rows[0]["expected"])/rows[0]["expected"]*100 for v in vals))
            prediction_sds.append(statistics.stdev(vals) if len(vals) > 1 else 0.0)
    complete = len(valid) == len(records)
    return {"completed": len(valid), "attempts": len(records), "coverage": len(valid)/len(records) if records else 0,
            "mape_percent": statistics.mean(errors) if errors and complete else None,
            "conditional_mape_percent": statistics.mean(errors) if errors else None,
            "mean_absolute_count_error": statistics.mean(abs(r["values"][arm]-r["expected"]) for r in valid) if valid else None,
            "within_5_percent": sum(e <= 5 for e in errors), "within_10_percent": sum(e <= 10 for e in errors),
            "above_20_percent": sum(e > 20 for e in errors), "exact": sum(e == 0 for e in errors),
            "all_attempt_success_at_10_percent": sum(e <= 10 for e in errors)/len(records) if records else None,
            "repetitions": repeats,
            "run_mape_mean": statistics.mean(repeat_maps) if all(v is not None for v in repeat_maps) else None,
            "run_mape_sd": statistics.stdev(repeat_maps) if len(repeat_maps)>1 and all(v is not None for v in repeat_maps) else None,
            "image_cluster_mape_interval_complete_images_only": bootstrap_mean(cluster_errors),
            "mean_within_image_count_sd_complete_images": statistics.mean(prediction_sds) if prediction_sds else None,
            "complete_images": len(cluster_errors)}


def paired(records, arm, baseline="vanilla"):
    groups = {}
    for r in records:
        groups.setdefault(r["id"], []).append(r)
    error_diff, success_diff = [], []
    for rows in groups.values():
        differences = []
        success_differences = []
        for r in rows:
            a, b = r["values"].get(arm), r["values"].get(baseline)
            ea = abs(a-r["expected"])/r["expected"]*100 if a is not None else None
            eb = abs(b-r["expected"])/r["expected"]*100 if b is not None else None
            if ea is not None and eb is not None:
                differences.append(ea-eb)
            success_differences.append(100*(int(ea is not None and ea<=10)-int(eb is not None and eb<=10)))
        if len(differences) == REPEATS:
            error_diff.append(statistics.mean(differences))
        if len(rows) == REPEATS:
            success_diff.append(statistics.mean(success_differences))
    return {"baseline": baseline, "error_difference_pp_complete_paired_images": bootstrap_mean(error_diff),
            "all_attempt_success_difference_pp": bootstrap_mean(success_diff),
            "interpretation": "negative error difference favors arm; positive success difference favors arm; intervals cluster by image"}


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def score():
    if not (RUNS / "inference-finished.json").exists():
        raise ValueError("Keep test labels closed until all scheduled inference finishes")
    rows = read_json(DATA / "inputs.json")
    strata = {r["id"]: r["metadata"] for r in read_json(REPORT / "strata.json")}
    procedures = [p.plan_id for p in load_catalog(CATALOG).procedures]
    records, references = [], []
    label_fingerprints = {p: {} for p in procedures}
    import hashlib
    for row in rows:
        label_path = DATA / "source/labels" / row["source_filename"]
        if sha256(label_path) != row["annotation_sha256"]:
            raise ValueError("Annotation checksum changed")
        truth = cv2.imread(str(label_path), cv2.IMREAD_UNCHANGED)
        if truth is None or truth.ndim != 2 or truth.dtype.kind not in "ui":
            raise ValueError("Expected original integer instance annotations")
        expected = int(np.count_nonzero(np.unique(truth) > 0))
        if expected <= 0:
            raise ValueError("Zero-reference count needs separately declared scoring; do not omit image")
        if truth.shape != (row["height"], row["width"]):
            raise ValueError("Reference coordinates differ from image")
        references.append({"id": row["id"], "source_filename": row["source_filename"], "count": expected,
                           "annotation_sha256": row["annotation_sha256"]})
        for repeat in range(1, REPEATS+1):
            directory = RUNS / f"repeat-{repeat}" / row["id"]
            route = directory / "routing"
            answer = read_json(route / "answer.json", {"status": "missing", "value": None})
            vanilla = read_json(directory / "vanilla/answer.json", {"status": "missing", "value": None})
            tools = read_json(directory / "astra-tools/answer.json", {"status": "missing", "value": None})
            candidate = read_json(route / "candidate-answer.json", {"status": "missing", "value": None})
            decision = read_json(route / "decision.json", {})
            proposal = read_json(route / "proposal.json", {})
            values = {"vanilla": numeric_answer(vanilla), "astra_tools_paired": numeric_answer(tools),
                      "jev_selection_stage": numeric_answer(candidate), "full_harness": numeric_answer(answer),
                      "strict_support_diagnostic": numeric_answer(answer) if answer.get("review_status")=="supported" else None}
            segments = {}
            for pid in procedures:
                folder = route / "specialists" / pid
                evidence = read_json(folder / "evidence.json")
                values[pid] = None
                if evidence:
                    with np.load(folder / "labels.npz", allow_pickle=False) as z:
                        pred = z["labels"]
                    if sha256(folder / "labels.npz") != evidence["worker"]["labels_sha256"]:
                        raise ValueError("Saved instance map changed")
                    count = int(np.count_nonzero(np.unique(pred) > 0))
                    if count != evidence["count"]:
                        raise ValueError("Evidence count differs from actual mask")
                    values[pid] = count
                    segments[pid] = match_instances(truth, pred)
                    label_fingerprints[pid].setdefault(row["id"], []).append(hashlib.sha256(pred.tobytes()).hexdigest())
            values["astra_preferred_measurement"] = values.get(proposal.get("preferred_id"))
            values["jev_selected_measurement"] = values.get(decision.get("selected_id"))
            records.append({"id": row["id"], "repeat": repeat, "expected": expected,
                            "class": (strata[row["id"]].get("Testset class") or "unknown").split(":")[0],
                            "values": values, "segmentation": segments, "selected_id": decision.get("selected_id"),
                            "astra_preferred_id": proposal.get("preferred_id"), "review_status": answer.get("review_status", "missing"),
                            "review_support": answer.get("review_support"),
                            "statuses": {"full_harness": answer.get("status"), "vanilla": vanilla.get("status"), "astra_tools_paired": tools.get("status"), "jev_selection_stage": candidate.get("status")},
                            "error_stage": answer.get("stage"), "error_type": answer.get("error_type"),
                            "decision_scores": decision.get("assessments", [])})
    arms = list(records[0]["values"])
    summary = {arm: summarize(records, arm) for arm in arms}
    by_class = {cls: {arm: summarize([r for r in records if r["class"]==cls], arm) for arm in arms} for cls in sorted({r["class"] for r in records})}
    segmentation = {}
    for pid in procedures:
        entries = [r["segmentation"][pid] for r in records if pid in r["segmentation"]]
        segmentation[pid] = {"completed": len(entries), "attempts": len(records),
                             "mean_image_f1": statistics.mean(e["f1"] for e in entries) if entries else None,
                             "mean_instance_matching_score": statistics.mean(e["instance_matching_score"] for e in entries) if entries else None,
                             "mean_precision": statistics.mean(e["precision"] for e in entries) if entries else None,
                             "mean_recall": statistics.mean(e["recall"] for e in entries) if entries else None,
                             "images_with_three_bitwise_identical_maps": sum(len(v)==REPEATS and len(set(v))==1 for v in label_fingerprints[pid].values())}
    for arm, key in [("full_harness_selected", "selected_id"), ("astra_preferred", "astra_preferred_id")]:
        entries = [r["segmentation"][r[key]] for r in records if r[key] in r["segmentation"]]
        segmentation[arm] = {"completed": len(entries), "mean_image_f1": statistics.mean(e["f1"] for e in entries) if entries else None,
                             "mean_instance_matching_score": statistics.mean(e["instance_matching_score"] for e in entries) if entries else None,
                             "scope": "selected mask quality, independent of final answer status"}
    rank_records = [r for r in records if r["selected_id"] and all(r["values"][p] is not None for p in procedures)]
    regrets, optimal = [], 0
    for r in rank_records:
        err = {p: abs(r["values"][p]-r["expected"])/r["expected"]*100 for p in procedures}
        regret = err[r["selected_id"]]-min(err.values())
        regrets.append(regret)
        optimal += abs(regret)<1e-9
    result = {"cohort_images": len(rows), "repetitions": REPEATS, "records": records, "metrics": summary,
              "paired_vs_vanilla": {arm: paired(records, arm) for arm in arms if arm!="vanilla"},
              "paired_full_vs_fixed": {p: paired(records, "full_harness", p) for p in procedures},
              "by_class": by_class, "segmentation": segmentation,
              "routing": {"rankable_trials": len(rank_records), "best_candidate_choices_including_ties": optimal,
                          "mean_regret_pp": statistics.mean(regrets) if regrets else None},
              "review": {s: sum(r["review_status"]==s for r in records) for s in sorted({r["review_status"] for r in records})},
              "statistical_scope": "three fresh repetitions per image; bootstrap over images, not independent patients; public training exposure unknown"}
    write_json(REPORT / "references.json", references)
    write_json(REPORT / "results.json", result)
    print(json.dumps({"images": len(rows), "repetitions": REPEATS, "metrics": {a: {k: summary[a][k] for k in ["completed", "attempts", "mape_percent", "conditional_mape_percent", "run_mape_sd", "all_attempt_success_at_10_percent"]} for a in arms}, "review": result["review"], "routing": result["routing"]}, indent=2))
