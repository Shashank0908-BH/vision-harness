"""Three explicit phases: freeze image cohort, infer without labels, then score.

Local native workers use Harbor-validated ATIF traces. This is not a Harbor
container experiment and count MAPE is not BBBC039's published segmentation metric.
"""

import argparse
import json
import statistics
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from evals.atif import export
from evals.import_bbbc039 import QUESTION, decode_labels, digest, to_display
from vision_harness.config import load_settings
from vision_harness.routing.catalog import load_catalog, sha256
from vision_harness.routing.runtime import run_route, source_hash
from vision_harness.runtime import run
from vision_harness.tracing import write_json

SOURCE = Path("evals/datasets/generated/bbbc039-adaptive-20260922/source")
DATASET = Path("evals/datasets/generated/bbbc039-routing-20260922")
REPORT = Path("reports/bbbc039-routing-20260922")
RUNS = Path("runs/bbbc039-routing-20260922")
CATALOG = Path("catalog/microscopy-v1.json")
CONFIG = Path("configs/routing.toml")
VANILLA_CONFIG = Path("configs/poc-adaptive.toml")
ARCHIVES = {
    "images.zip": "6f30a5d4fe38c928ded972704f085975f8dc0d65d9aa366df00e5a9d449fddd7",
    "masks.zip": "f9e6043d8ca56344a4886f96a700d804d6ee982f31e2b2cd3194af2a053c2710",
    "metadata.zip": "a2c1f900bed9ba92a99553efd4c2ae98598433691c7401d818653ab61110deb2",
}


def prepare():
    if REPORT.exists() or DATASET.exists():
        raise ValueError("Refusing to replace a frozen cohort")
    for name, expected in ARCHIVES.items():
        if sha256(SOURCE / name) != expected:
            raise ValueError(f"Source archive hash mismatch: {name}")
    excluded = json.loads(Path("reports/bbbc039-adaptive-20260922/selection.json").read_text())["filenames"]
    with zipfile.ZipFile(SOURCE / "metadata.zip") as archive:
        population = archive.read("metadata/test.txt").decode().splitlines()
    filenames = sorted((n for n in population if n not in excluded),
                       key=lambda n: digest(("vision-specialist-routing-v1:" + n).encode()))[:6]
    selection = {
        "frozen_at": datetime.now(timezone.utc).isoformat(), "source": "https://bbbc.broadinstitute.org/BBBC039",
        "filenames": filenames, "excluded_previous_cohort": excluded,
        "rule": "first six remaining official test filenames sorted by SHA256(vision-specialist-routing-v1: + filename)",
        "source_archives_sha256": ARCHIVES, "catalog_sha256": sha256(CATALOG),
        "source_sha256": source_hash(),
        "config_sha256": {str(p): sha256(p) for p in [CONFIG, VANILLA_CONFIG]},
        "prompt_sha256": {str(p): sha256(p) for p in [Path("prompts/astra-routing.md"), Path("prompts/astra-adaptive.md"), Path("prompts/jev_plan_conditions.json"), Path("prompts/jev_review_estimate.json")]},
        "procedure_ids": [p.plan_id for p in load_catalog(CATALOG).procedures],
        "metrics": ["count MAPE across all six only if complete", "exact counts", "coverage", "review caution rate", "routing regret against best fixed candidate per image"],
        "policy": "one route and one fresh vanilla call sequence per task; SDK schema retries only; no outcome retries; all fixed candidates after chosen answer; labels read only in score phase",
        "preprocessing": "same fixed 1/99.8 percentile conversion to 8-bit replicated grayscale, no resizing",
        "caveat": "public test split, pretrained exposure unknown; developer has previous cohort results; not a preregistered independent replication",
    }
    write_json(REPORT / "selection.json", selection)
    images_directory = DATASET / "images"
    images_directory.mkdir(parents=True)
    rows = []
    # Deliberately never open annotation archive during this phase.
    with zipfile.ZipFile(SOURCE / "images.zip") as archive:
        names = {Path(n).stem: n for n in archive.namelist() if n.lower().endswith((".tif", ".tiff")) and not n.startswith("__MACOSX/")}
        for filename in filenames:
            raw = archive.read(names[Path(filename).stem])
            gray = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
            display, percentiles = to_display(gray)
            task_id = digest(filename.encode())[:12]
            path = images_directory / f"{task_id}.png"
            cv2.imwrite(str(path), cv2.cvtColor(display, cv2.COLOR_GRAY2BGR))
            rows.append({"id": task_id, "image": str(path), "source_filename": filename,
                         "image_sha256": sha256(path), "source_tiff_sha256": digest(raw),
                         "display_percentiles": percentiles, "question": QUESTION})
    write_json(DATASET / "inputs.json", rows)
    write_json(REPORT / "inputs.json", rows)
    print(f"Frozen {len(rows)} image-only tasks. No annotation archive opened.", flush=True)


def infer():
    selection = json.loads((REPORT / "selection.json").read_text())
    if sha256(CATALOG) != selection["catalog_sha256"] or source_hash() != selection["source_sha256"]:
        raise ValueError("Frozen catalog or source changed")
    for name, expected in {**selection["config_sha256"], **selection["prompt_sha256"]}.items():
        if sha256(Path(name)) != expected:
            raise ValueError(f"Frozen configuration changed: {name}")
    RUNS.mkdir(parents=True, exist_ok=False)
    settings = load_settings(CONFIG)
    vanilla_settings = load_settings(VANILLA_CONFIG)
    for row in json.loads((DATASET / "inputs.json").read_text()):
        image = Path(row["image"])
        if sha256(image) != row["image_sha256"]:
            raise ValueError("Frozen image changed")
        output = RUNS / row["id"] / "routing"
        result = run_route(image, row["question"], settings, CATALOG, output, compare_all=True)
        export(output, output / "trajectory.json")
        print(json.dumps({"id": row["id"], "arm": "routing", "status": result["status"], "review_status": result["review_status"], "stage": result.get("stage")}), flush=True)
        output = RUNS / row["id"] / "vanilla"
        run(image, row["question"], vanilla_settings, mode="vanilla", output=output)
        export(output, output / "trajectory.json")
        answer = json.loads((output / "answer.json").read_text())
        print(json.dumps({"id": row["id"], "arm": "vanilla", "status": answer["status"]}), flush=True)
    write_json(RUNS / "inference-complete.json", {"completed_at": datetime.now(timezone.utc).isoformat(), "source_sha256": source_hash()})


def summarize(values, expected):
    valid = [(v, t) for v, t in zip(values, expected, strict=True) if v is not None]
    return {"completed": len(valid), "total": len(expected),
            "mape_percent": statistics.mean(abs(v-t)/t*100 for v, t in valid) if len(valid) == len(expected) else None,
            "exact": sum(v == t for v, t in valid)}


def score():
    if not (RUNS / "inference-complete.json").exists():
        raise ValueError("Do not open labels before inference completes")
    selection = json.loads((REPORT / "selection.json").read_text())
    if sha256(SOURCE / "masks.zip") != ARCHIVES["masks.zip"]:
        raise ValueError("Annotation archive hash changed")
    rows = json.loads((DATASET / "inputs.json").read_text())
    outcomes = []
    with zipfile.ZipFile(SOURCE / "masks.zip") as masks:
        names = {Path(n).name: n for n in masks.namelist() if n.endswith(".png") and not n.startswith("__MACOSX/")}
        for row in rows:
            raw = masks.read(names[row["source_filename"]])
            labels = decode_labels(cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)[..., ::-1])
            expected = int(np.count_nonzero(np.unique(labels) > 0))
            if expected <= 0:
                raise ValueError("MAPE undefined for zero target; do not replace this image")
            route = RUNS / row["id"] / "routing"
            decision = json.loads((route / "decision.json").read_text()) if (route / "decision.json").exists() else None
            answer = json.loads((route / "answer.json").read_text())
            vanilla = json.loads((RUNS / row["id"] / "vanilla" / "answer.json").read_text())
            values = {}
            for pid in selection["procedure_ids"]:
                path = route / "specialists" / pid / "evidence.json"
                values[pid] = json.loads(path.read_text())["count"] if path.exists() else None
            if decision and answer.get("decision_sha256") and sha256(route / "decision.json") != answer["decision_sha256"]:
                raise ValueError("Frozen decision modified")
            outcomes.append({**row, "expected": expected, "annotation_sha256": digest(raw),
                             "procedure_counts": values, "decision": decision, "harness": answer,
                             "vanilla": vanilla,
                             "harness_total_seconds_including_comparison": json.loads((route / "manifest.json").read_text())["elapsed_seconds"]})
    expected = [r["expected"] for r in outcomes]
    metrics = {pid: summarize([r["procedure_counts"][pid] for r in outcomes], expected) for pid in selection["procedure_ids"]}
    for name, key in [("vanilla_astra", "vanilla"), ("harness_with_review", "harness")]:
        metrics[name] = summarize([r[key]["value"] if r[key]["status"] == "answered" and isinstance(r[key]["value"], (int, float)) else None for r in outcomes], expected)
    for name, key in [("astra_preferred_measurement", "astra_preferred_id"), ("jev_selected_measurement", "selected_id")]:
        metrics[name] = summarize([r["procedure_counts"].get(r["decision"][key]) if r["decision"] else None for r in outcomes], expected)
    regrets, top_choices = [], []
    for r in outcomes:
        counts = r["procedure_counts"]
        if r["decision"] and all(v is not None for v in counts.values()):
            errors = {k: abs(v-r["expected"])/r["expected"]*100 for k, v in counts.items()}
            best = min(errors.values())
            selected_error = errors[r["decision"]["selected_id"]]
            regrets.append(selected_error-best)
            top_choices.append(abs(selected_error-best) < 1e-9)
            r["candidate_ape_percent"] = errors
            r["routing_regret_percentage_points"] = selected_error-best
    result = {"metrics": metrics, "rows": outcomes,
              "routing_diagnostics": {"complete_tasks": len(regrets), "top_choice_matches_oracle_including_ties": sum(top_choices),
                                      "mean_regret_percentage_points": statistics.mean(regrets) if len(regrets) == len(outcomes) else None},
              "review_counts": {s: sum(r["harness"]["review_status"] == s for r in outcomes) for s in ["supported", "caution", "not_completed", "not_run"]},
              "scope": "Six new official-test images; local derived count MAPE, not published segmentation performance. Jev receives structured evidence, not pixels."
              }
    write_json(REPORT / "results.json", result)
    lines = ["# Specialist routing experiment", "", result["scope"], "", "| Arm | Numeric results | Count MAPE | Exact |", "|---|---:|---:|---:|"]
    for name, metric in metrics.items():
        value = f'{metric["mape_percent"]:.2f}%' if metric["mape_percent"] is not None else "Incomplete"
        lines.append(f'| {name} | {metric["completed"]}/{metric["total"]} | {value} | {metric["exact"]} |')
    lines += ["", "Astra preference and Jev selection measurement rows are policy diagnostics from the frozen decision, not separate answer-generation arms.", "The harness returns estimates with either supported or caution review status. This differs from the historical full harness abstention policy; do not pool their scores.", "", "Review: " + json.dumps(result["review_counts"]), "", "Routing diagnostics: " + json.dumps(result["routing_diagnostics"])]
    (REPORT / "final-score.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"metrics": metrics, "review": result["review_counts"], "routing": result["routing_diagnostics"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "infer", "score"])
    phase = parser.parse_args().phase
    {"prepare": prepare, "infer": infer, "score": score}[phase]()
