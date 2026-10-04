"""Rescore saved predictions without new API calls or changing frozen outcomes."""

import copy
import hashlib
import json
import statistics
from pathlib import Path

import cv2
import numpy as np

from evals.annotation_integrity import audit_instance_labels
from evals.repeated.metrics import match_instances, paired, summarize

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/stardist-audit-20260922"
DATA = ROOT / "evals/datasets/generated/kromp-repeated-20260922"
OLD_REPORT = ROOT / "reports/kromp-repeated-20260922"
OLD_RUNS = ROOT / "runs/kromp-repeated-20260922"
DISPUTED = "5ce7aa249ca6"
DISPUTED_SHA = "d2ebc80c4f689195c27cacdd08df8adb0684f0f54aa549c719341c75686ad43c"


def read(path):
    return json.loads(path.read_text())


def main():
    official = read(REPORT / "independent-matching.json")
    assert official["all_tp_fp_fn_equal"]
    original = read(OLD_REPORT / "results.json")
    records = copy.deepcopy(original["records"])
    inputs = read(DATA / "inputs.json")
    references = []
    for row in inputs:
        path = DATA / "source/labels" / row["source_filename"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["annotation_sha256"]
        labels = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        integrity = audit_instance_labels(labels)
        if integrity["requires_reference_review"]:
            assert row["source_filename"] in ("otherspecimen_3.tif", "Ganglioneuroblastoma_8.tif")
            if row["source_filename"] == "Ganglioneuroblastoma_8.tif":
                assert integrity["unique_positive_ids"] == 183
                assert all(area < 5 for v in integrity["multipart_labels"] for area in v["component_areas"][1:])
        if row["id"] == DISPUTED:
            assert row["annotation_sha256"] == DISPUTED_SHA
            repaired = np.load(REPORT / "otherspecimen_3-components-diagnostic.npz")["labels"]
            assert np.array_equal(labels > 0, repaired > 0)
            assert audit_instance_labels(repaired)["unique_positive_ids"] == 102
            for record in records:
                if record["id"] != DISPUTED:
                    continue
                record["expected_original"] = record["expected"]
                record["expected"] = 102
                for pid in record["segmentation"]:
                    path = OLD_RUNS / f'repeat-{record["repeat"]}' / DISPUTED / "routing/specialists" / pid / "labels.npz"
                    pred = np.load(path, allow_pickle=False)["labels"]
                    record["segmentation"][pid] = match_instances(repaired, pred)
        references.append({"id": row["id"], "source_filename": row["source_filename"],
                           "annotation_sha256": row["annotation_sha256"], "integrity": integrity,
                           "scored_count": 102 if row["id"] == DISPUTED else integrity["unique_positive_ids"]})
    arms = list(records[0]["values"])
    lookup = {(r["id"], r["repeat"]): r for r in records}
    native = official["native_scored"]
    variants = sorted({r["variant"] for r in native})
    for result in native:
        record = lookup[result["id"], result["repeat"]]
        assert record["expected"] == result["expected"]
        record["values"][result["variant"]] = result["count"]
        record["segmentation"][result["variant"]] = result["matching"]
    scenarios = {"repaired_37": records,
                 "exclude_ambiguous_36": [r for r in records if r["id"] != DISPUTED]}
    # SVG-only interpretation is a sensitivity analysis, not our reference repair.
    alternate = copy.deepcopy(records)
    for row in alternate:
        if row["id"] == DISPUTED:
            row["expected"] = 104
    scenarios["svg_104_count_sensitivity_37"] = alternate
    summaries = {name: {arm: summarize(rows, arm) for arm in arms + variants} for name, rows in scenarios.items()}
    segments = {}
    for scenario, rows in list(scenarios.items())[:2]:
        segments[scenario] = {}
        for pid in records[0]["segmentation"]:
            entries = [r["segmentation"][pid] for r in rows]
            segments[scenario][pid] = {"mean_image_f1": statistics.mean(e["f1"] for e in entries),
                                       "mean_precision": statistics.mean(e["precision"] for e in entries),
                                       "mean_recall": statistics.mean(e["recall"] for e in entries)}
    parity = [r for r in native if r["pixel_identical_to_prior"] is not None]
    determinism = {}
    for variant in variants:
        groups = {}
        for r in native:
            if r["variant"] == variant:
                groups.setdefault(r["id"], []).append(r["array_sha256"])
        determinism[variant] = sum(len(v) == 3 and len(set(v)) == 1 for v in groups.values())
    procedures = list(original["records"][0]["segmentation"])
    rankable = [r for r in records if r["selected_id"]]
    regrets = []
    for r in rankable:
        errors = {p: abs(r["values"][p] - r["expected"])/r["expected"]*100 for p in procedures}
        regrets.append(errors[r["selected_id"]] - min(errors.values()))
    result = {
        "scope": "Reference repair and post-hoc scale diagnostics. No new Astra/Jev calls; no new harness accuracy claim.",
        "original_results_sha256": hashlib.sha256((OLD_REPORT / "results.json").read_bytes()).hexdigest(),
        "reference_policy": {"otherspecimen_3": "55 reused IDs -> 102 source-verified per-ID regions; preserves all foreground pixels",
                             "Ganglioneuroblastoma_8": "183 original IDs preserved; two fragments under 5 pixels are not new nuclei",
                             "svg_caveat": "110 elements -> 104 nonduplicate contours; 102 correspond one-to-one to released TIFF regions; two are absent from TIFF"},
        "native_comparisons": len(parity),
        "pixel_identical_native_vs_worker": sum(r["pixel_identical_to_prior"] for r in parity),
        "official_matching_checks": official["official_matcher_checks"],
        "official_matching_all_agree": official["all_tp_fp_fn_equal"],
        "native_fresh_inferences": len(native),
        "images_with_three_identical_maps": determinism,
        "references": references,
        "metrics": summaries,
        "segmentation": segments,
        "paired_vs_vanilla_repaired": {arm: paired(records, arm) for arm in arms + variants if arm != "vanilla"},
        "routing_repaired": {"trials": len(rankable), "best_choices_including_ties": sum(abs(r) < 1e-9 for r in regrets), "mean_regret_pp": statistics.mean(regrets)},
        "records_repaired": records,
    }
    (REPORT / "corrected-results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"native_comparisons": result["native_comparisons"], "pixel_identical": result["pixel_identical_native_vs_worker"], "metrics": {a: {k: v[k] for k in ("completed", "attempts", "conditional_mape_percent", "all_attempt_success_at_10_percent")} for a, v in summaries["repaired_37"].items()}, "segmentation": segments["repaired_37"]}, indent=2))


if __name__ == "__main__":
    main()
