"""Freeze and run standalone specialists; score only after image-only workers finish."""

import argparse
import base64
import hashlib
import html
import json
import os
import shutil
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from evals.scoring import score  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def render(report):
    cohort = json.loads((report / "cohort.json").read_text())
    protocol = json.loads((report / "protocol.json").read_text())
    historical_path = ROOT / protocol["historical_comparison"]
    if digest(historical_path) != protocol["historical_comparison_sha256"]:
        raise ValueError("Historical comparison changed")
    historical = json.loads(historical_path.read_text())
    historical_cohort = {r["id"]: r for r in historical["cohort"]}
    for row in cohort:
        assert historical_cohort[row["id"]]["sha256"] == row["sha256"]
    summaries, all_rows = [], []
    for model in ("cellpose", "stardist"):
        path = report / model / "results.json"
        rows = json.loads(path.read_text()) if path.exists() else []
        by_id = {r["id"]: r for r in rows}
        if len(by_id) != len(rows) or not set(by_id) <= {r["id"] for r in cohort}:
            raise ValueError("Duplicate or unexpected worker outputs")
        measurements = []
        for target in cohort:
            row = dict(by_id.get(target["id"], {"id": target["id"], "status": "error"}))
            if row["status"] == "answered":
                if row["input_sha256"] != target["sha256"]:
                    raise ValueError("Worker input differs from frozen cohort")
                import numpy as np

                labels_file = report / model / target["id"] / "labels.npz"
                labels = np.load(labels_file)["labels"]
                if labels.shape != (512, 512) or np.any(labels < 0):
                    raise ValueError("Invalid mask geometry")
                count = len(np.unique(labels[labels > 0]))
                if count != row["count"] or digest(labels_file) != row["labels_sha256"]:
                    raise ValueError("Count does not match saved mask")
            metrics = score({"status": row["status"], "value": row.get("count")}, target)
            row.update(model=model, metrics=metrics, reference=target["expected"])
            measurements.append(row)
        valid = [r for r in measurements if r["metrics"].get("valid_prediction")]
        summaries.append(
            {
                "model": model,
                "coverage": len(valid),
                "total": len(cohort),
                "mean_percentage_error": statistics.mean(
                    r["metrics"]["percentage_error"] for r in valid
                )
                if len(valid) == len(cohort)
                else None,
                "mean_inference_seconds": statistics.mean(r["inference_seconds"] for r in valid)
                if valid
                else None,
            }
        )
        all_rows.extend(measurements)
    write(
        report / "scores.json",
        {"summary": summaries, "trials": all_rows, "historical_summary": historical["summary"]},
    )
    title = "BBBC001: standalone microscopy specialists"
    note = (
        "Six previously inspected development images; one fixed configuration per specialist. "
        "Counts are computed from instance masks. No Astra or Jev in the new runs. "
        "Historical Astra comparisons are reused from the explicitly linked earlier run, not new inference. "
        "This is native local execution, not a Harbor harness evaluation. "
        "BBBC001 has count labels but no instance masks here; segmentation precision/recall is not measured."
    )
    if (report / "recovery.json").exists():
        note += (
            " StarDist had one metadata-only startup failure before inference; "
            "the preserved recovery record documents the fix. No prediction or threshold was changed."
        )
    md = [
        "# " + title,
        "",
        note,
        "",
        "| New specialist | Counts | Mean counting error ↓ | Mean inference time |",
        "|---|---:|---:|---:|",
    ]
    table = []
    for row in summaries:
        error = (
            f"{row['mean_percentage_error']:.2f}%"
            if row["mean_percentage_error"] is not None
            else "Incomplete"
        )
        seconds = (
            f"{row['mean_inference_seconds']:.2f} s"
            if row["mean_inference_seconds"] is not None
            else "—"
        )
        md.append(f"| {row['model']} | {row['coverage']}/{row['total']} | {error} | {seconds} |")
        table.append(
            f"<tr><th>{row['model']}</th><td>{row['coverage']}/{row['total']}</td><td>{error}</td><td>{seconds}</td></tr>"
        )
    md.extend(
        [
            "",
            "Inference time excludes dependency imports, model loading/downloads and artifact generation. Cold-start and total worker times are in each model.json. CPU and MPS differ; historical API runtimes are not directly comparable.",
            "",
            "## Historical context",
            "",
            "Source: [earlier three-mode run](../bbbc001-no-review-20260922/index.html).",
            "",
        ]
    )
    hist_html = []
    for row in historical["summary"]:
        text = f"{row['mode']}: {row['benchmark_percentage_error']:.2f}% counting error"
        md.append("- " + text)
        hist_html.append("<li>" + text + "</li>")
    md.extend(
        [
            "",
            "## Per-image counts",
            "",
            "| Image | Human mean | Historical vanilla | Cellpose-SAM | StarDist |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    details = []
    lookup = {(r["model"], r["id"]): r for r in all_rows}
    vanilla = {
        r["task_id"]: r["answer"]["value"] for r in historical["trials"] if r["mode"] == "vanilla"
    }
    inputs = {r["id"]: r for r in json.loads((report / "inputs.json").read_text())}
    (report / "originals").mkdir(exist_ok=True)
    for target in cohort:
        tid = target["id"]
        rows = [lookup[(model, tid)] for model in ("cellpose", "stardist")]
        md.append(
            f"| {target['title']} | {target['expected']} | {vanilla[tid]:g} | {rows[0].get('count', 'error')} | {rows[1].get('count', 'error')} |"
        )
        cards = []
        original = Path(inputs[tid]["path"])
        if digest(original) != target["sha256"]:
            raise ValueError("Original image changed before rendering")
        shutil.copy2(original, report / "originals" / (tid + ".png"))
        original_b64 = base64.b64encode(original.read_bytes()).decode()
        for model, row in zip(("cellpose", "stardist"), rows, strict=True):
            if row["status"] != "answered":
                cards.append(f"<article><h3>{model}: error</h3></article>")
                continue
            url = f"{model}/{tid}"
            embedded = base64.b64encode((report / url / "numbered.png").read_bytes()).decode()
            cards.append(
                f"<article><h3>{model}: {row['count']} · error {row['metrics']['percentage_error']:.2f}%</h3>"
                f'<a href="{url}/numbered.png"><img alt="{model} numbered nuclei" src="data:image/png;base64,{embedded}"></a>'
                f'<p><a href="{url}/labels.npz">Instance mask</a> · <a href="{url}/instances.json">Measurements</a> · <a href="{url}/result.json">Trace</a></p></article>'
            )
        details.append(
            f"<details open><summary>{html.escape(target['title'])} · human mean {target['expected']} · historical vanilla {vanilla[tid]:g}</summary>"
            f"<p>Human counts: {target['human_counts'][0]} and {target['human_counts'][1]}. Instance IDs are local to each model; matching numbers do not identify the same nucleus.</p>"
            f'<details><summary>Original image</summary><img style="max-width:512px" alt="Original fluorescence image" src="data:image/png;base64,{original_b64}"></details><div class="grid">'
            + "".join(cards)
            + "</div></details>"
        )
    md.extend(
        [
            "",
            "[Visual report](index.html) · [Protocol](protocol.json) · [Exact scores](scores.json)",
            "",
            "Images: BBBC001v1, David Root and Anne Carpenter, CC BY-NC-SA 3.0. No settings were tuned against these counts.",
        ]
    )
    (report / "README.md").write_text("\n".join(md) + "\n")
    recovery_link = (
        '<p><a href="recovery.json">Startup recovery record</a></p>'
        if (report / "recovery.json").exists()
        else ""
    )
    (report / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{title}</title><style>body{{font:16px/1.6 system-ui;background:#101521;color:#e9effa;max-width:1200px;margin:auto;padding:24px}}a{{color:#9ed7ff}}table{{border-collapse:collapse;width:100%}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #405069}}.scroll{{overflow:auto}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}img{{width:100%;height:auto}}details{{margin:24px 0;padding:16px;background:#1c2638;border-radius:12px}}summary{{cursor:pointer;font-weight:bold}}article{{min-width:0}}@media(max-width:650px){{.grid{{grid-template-columns:1fr}}body{{padding:12px}}}}</style>"
        f'<h1>{title}</h1><p>{note}</p><div class="scroll"><table><thead><tr><th>Specialist</th><th>Counts</th><th>Mean error ↓</th><th>Inference/image</th></tr></thead><tbody>{"".join(table)}</tbody></table></div>'
        "<p>Inference excludes imports, loading/downloads and artifact generation. These CPU/MPS timings differ from historical API runtimes.</p>"
        '<h2>Historical context</h2><p><a href="../bbbc001-no-review-20260922/index.html">Previous run and traces</a></p><ul>'
        + "".join(hist_html)
        + "</ul>"
        '<p><a href="protocol.json">Frozen protocol</a> · <a href="scores.json">Exact scores</a> · <a href="cellpose/model.json">Cellpose checkpoint/settings</a> · <a href="stardist/model.json">StarDist checkpoint/settings</a></p>'
        + recovery_link
        + "".join(details)
        + "<footer>BBBC001v1 · David Root and Anne Carpenter · CC BY-NC-SA 3.0. Click an overlay to inspect at full resolution.</footer></html>"
    )
    print(json.dumps(summaries, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    report = args.report.resolve()
    if args.report_only:
        render(report)
        return
    report.mkdir(parents=True, exist_ok=False)
    dataset = ROOT / "evals/datasets/generated/bbbc001-20260922"
    cohort = [json.loads(line) for line in (dataset / "manifest.jsonl").read_text().splitlines()]
    write(report / "cohort.json", cohort)
    inputs = []
    for row in cohort:
        path = dataset / row["image"]
        if digest(path) != row["sha256"]:
            raise ValueError("Dataset image differs from published import")
        inputs.append({"id": row["id"], "path": str(path), "sha256": row["sha256"]})
    write(report / "inputs.json", inputs)
    source = Path(__file__).parent
    (report / "source").mkdir()
    for path in source.glob("*.py"):
        shutil.copy2(path, report / "source" / path.name)
    historical = "reports/bbbc001-no-review-20260922/results.json"
    write(
        report / "protocol.json",
        {
            "frozen_at": datetime.now(timezone.utc).isoformat(),
            "cohort": "All six BBBC001v1 images; previously inspected development set",
            "models": {"cellpose": "cpsam_v2", "stardist": "2D_versatile_fluo"},
            "attempts": 1,
            "no_label_based_tuning": True,
            "execution": "Sequential native workers in isolated environments; not Harbor",
            "metric": "Mean of 100*abs(predicted count-human mean)/human mean across all six images",
            "missing_policy": "No complete mean score when any image fails",
            "worker_inputs": "Only image paths, IDs and checksums; no annotation file is read by workers",
            "historical_comparison": historical,
            "historical_comparison_sha256": digest(ROOT / historical),
            "source_hashes": {p.name: digest(p) for p in source.glob("*.py")},
            "limits": "1800-second timeout per six-image worker; one model resident at a time",
            "preprocessing": {
                "cellpose": "RGB replicated grayscale; built-in normalization; no diameter rescaling; float32; batch_size=1; default segmentation thresholds",
                "stardist": "One grayscale channel; percentile normalization 1/99.8; pretrained thresholds; no geometric resize; CPU",
            },
            "limitations": [
                "Not held out from project development",
                "Prior pretraining exposure unknown",
                "Two human counts disagree",
                "Count labels cannot establish mask accuracy",
                "Historical Astra run is not contemporaneous",
                "RSS does not fully account for accelerator allocations",
            ],
        },
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(s in k.upper() for s in ("API_KEY", "TOKEN", "SECRET"))
    }
    env.update(PYTHONUNBUFFERED="1", TF_CPP_MIN_LOG_LEVEL="2", MPLBACKEND="Agg")
    exits = {}
    for model in ("cellpose", "stardist"):
        command = [
            str(ROOT / f".venv-{model}/bin/python"),
            str(source / "worker.py"),
            "--model",
            model,
            "--inputs",
            str(report / "inputs.json"),
            "--output",
            str(report / model),
        ]
        print(f"Starting {model}; log: {report / (model + '.log')}", flush=True)
        with (report / f"{model}.log").open("w") as log:
            try:
                completed = subprocess.run(
                    command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=1800
                )
                exits[model] = completed.returncode
            except subprocess.TimeoutExpired:
                exits[model] = "timeout"
        write(report / "execution.json", exits)
        print(f"Finished {model}: {exits[model]}", flush=True)
    render(report)
    if any(value != 0 for value in exits.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
