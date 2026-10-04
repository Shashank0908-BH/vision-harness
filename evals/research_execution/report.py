"""Aggregate every planned attempt, including missing answers, without outcome retries."""

import argparse
import html
import json
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from vision_harness.tracing import write_json

from .prepare import REPORT, ROOT


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def cluster_interval(values):
    if not values:
        return None
    array = np.asarray(values, dtype=float)
    draws = np.random.default_rng(20260922).choice(array, (10000, len(array)), replace=True).mean(axis=1)
    return {"mean": float(array.mean()), "ci95": np.percentile(draws, [2.5, 97.5]).tolist(),
            "clusters": len(array), "unit": "image; repetitions averaged within image"}


def collect(split="test"):
    report = REPORT if split == "test" else REPORT / split
    selection = read(report / "selection.json")
    cohort = read(report / "cohort.json")
    records, summaries = [], {}
    repetitions = selection["repetitions"]
    for mode in selection["arms"]:
        job = ROOT / "jobs" / f"research-execution-{split}-{mode}"
        by_image = defaultdict(list)
        for config_path in sorted(job.glob("*/config.json")):
            config = read(config_path)
            by_image[Path(config["task"]["path"]).name].append(config_path.parent)
        for row in cohort:
            trials = sorted(by_image[row["id"]], key=lambda p: p.name)
            if len(trials) > repetitions:
                raise ValueError("More trials than frozen attempts; don't choose favorable retries")
            for index in range(repetitions):
                folder = trials[index] if index < len(trials) else None
                grading = read(folder / "verifier/grading.json", {}) if folder else {}
                answer = read(folder / "agent/run/answer.json", {}) if folder else {}
                result = read(folder / "result.json", {}) if folder else {}
                usage = {"input_tokens": 0, "output_tokens": 0}
                events_path = folder / "agent/run/events.jsonl" if folder else None
                stages = []
                if events_path and events_path.exists():
                    for line in events_path.read_text().splitlines():
                        event = json.loads(line)
                        if event["kind"] == "call_finished":
                            for key in usage:
                                usage[key] += (event["data"].get("usage") or {}).get(key, 0)
                        if event["kind"] == "stage":
                            stages.append(event["data"]["stage"])
                if grading and grading["expected"] != row["expected"]:
                    raise ValueError("Grader reference disagrees with frozen cohort")
                records.append({"mode": mode, "id": row["id"], "repetition_label": index+1,
                    "repetition_label_note": "Arbitrary stable order of independent Harbor trials, not synchronized random seeds",
                    "trial": str(folder.relative_to(ROOT)) if folder else None,
                    "expected": row["expected"], "count": grading.get("count"),
                    "answered": grading.get("answered", False),
                    "within_10_percent": grading.get("within_10_percent", False),
                    "percentage_error": grading.get("percentage_error"),
                    "review_status": answer.get("review_status", "missing"),
                    "status": answer.get("status", "missing"),
                    "error": answer.get("error") or grading.get("error") or result.get("exception_info"),
                    "elapsed_seconds": answer.get("elapsed_seconds"), "tokens": usage,
                    "segmentation": grading.get("segmentation"), "stages": stages})
        rows = [r for r in records if r["mode"] == mode]
        errors = [r["percentage_error"] for r in rows if r["answered"]]
        times = [r["elapsed_seconds"] for r in rows if r["elapsed_seconds"] is not None]
        image_success = [statistics.mean(r["within_10_percent"] for r in rows if r["id"] == c["id"]) for c in cohort]
        summaries[mode] = {"attempts": len(rows), "answered": len(errors),
            "within_10_percent": sum(r["within_10_percent"] for r in rows),
            "all_attempt_success_percent": statistics.mean(image_success)*100,
            "conditional_mape_percent": statistics.mean(errors) if errors else None,
            "complete_cohort_mape_percent": statistics.mean(errors) if len(errors) == len(rows) else None,
            "mean_seconds": statistics.mean(times) if times else None,
            "review_statuses": dict(Counter(r["review_status"] for r in rows)),
            "total_tokens": {k: sum(r["tokens"][k] for r in rows) for k in ("input_tokens", "output_tokens")},
            "success_image_cluster_interval": cluster_interval(image_success),
            "mean_instance_f1_answered_masks": statistics.mean(r["segmentation"]["f1"] for r in rows if r["segmentation"]) if any(r["segmentation"] for r in rows) else None}
    differences, per_image = [], []
    for row in cohort:
        success = {m: statistics.mean(r["within_10_percent"] for r in records if r["mode"] == m and r["id"] == row["id"])
                   for m in selection["arms"]}
        differences.append(success["full"]-success["vanilla"])
        details = {"id": row["id"], "expected": row["expected"], "arms": {}}
        for mode in selection["arms"]:
            attempts = [r for r in records if r["mode"] == mode and r["id"] == row["id"]]
            valid = [r for r in attempts if r["answered"]]
            counts = [r["count"] for r in valid]
            details["arms"][mode] = {
                "counts": [r["count"] for r in attempts], "answered": len(valid),
                "mean_count": statistics.mean(counts) if counts else None,
                "count_sd": statistics.stdev(counts) if len(counts) > 1 else None,
                "conditional_mean_percentage_error": statistics.mean(r["percentage_error"] for r in valid) if valid else None,
                "within_10_percent": sum(r["within_10_percent"] for r in attempts)}
        per_image.append(details)
    result = {"cohort_images": len(cohort), "repetitions": repetitions, "selection": selection,
              "metrics": summaries, "paired_success_difference": cluster_interval(differences),
              "per_image": per_image, "records": records}
    write_json(report / "results.json", result)
    render(report, result)
    print(json.dumps({"metrics": summaries, "paired_success_difference": result["paired_success_difference"]}, indent=2))


def render(report, result):
    def esc(value):
        return html.escape(str(value))

    def fmt(value, suffix=""):
        return "—" if value is None else f"{value:.2f}{suffix}"

    summary_rows = "".join(f'<tr><td>{esc(mode)}</td><td>{s["answered"]}/{s["attempts"]}</td>'
        f'<td>{s["within_10_percent"]}/{s["attempts"]} ({fmt(s["all_attempt_success_percent"], "%")})</td>'
        f'<td>{fmt(s["conditional_mape_percent"], "%")}</td><td>{fmt(s["mean_seconds"], " s")}</td>'
        f'<td>{esc(s["review_statuses"])}</td></tr>' for mode, s in result["metrics"].items())
    image_rows = "".join(f'<tr><td>{esc(row["id"])}</td><td>{row["expected"]}</td>' +
        "".join(f'<td>{esc(row["arms"][mode]["counts"])}<br><small>Mean {fmt(row["arms"][mode]["mean_count"])}; '
                f'SD {fmt(row["arms"][mode]["count_sd"])}</small></td>' for mode in ("vanilla", "full")) + '</tr>'
        for row in result["per_image"])
    cards = []
    for row in result["records"]:
        relative = Path(os.path.relpath(ROOT / row["trial"], report)).as_posix() if row["trial"] else None
        links = ""
        if relative:
            links = " · ".join(f'<a href="{relative}/{path}">{label}</a>' for path, label in
                [("agent/trajectory.json", "Harbor trajectory"), ("agent/run/events.jsonl", "Event trace"),
                 ("agent/run/answer.json", "Answer"), ("agent/run/task.json", "Structured query"),
                 ("agent/run/research-01/catalog.json", "Candidate catalog"),
                 ("agent/run/research-01/candidate-scores.json", "All candidate scores"),
                 ("agent/run/research-01/documents/usage-contracts.json", "Usage contracts"),
                 ("agent/run/round-01/plans.json", "Plans"),
                 ("agent/run/round-01/execution/codex-events.jsonl", "Shell execution"),
                 ("agent/run/round-01/execution/overlay.png", "First overlay"),
                 ("verifier/grading.json", "Independent grading")]
                if (ROOT / row["trial"] / path).exists())
        cards.append(f'<article data-mode="{row["mode"]}"><h3>{esc(row["id"])} · {esc(row["mode"])} · run {row["repetition_label"]}</h3>'
            f'<p>Count <b>{esc(row["count"])}</b> / reference {row["expected"]}; error {fmt(row["percentage_error"], "%")}. '
            f'Review: {esc(row["review_status"])}. Time: {fmt(row["elapsed_seconds"], " s")}.</p>'
            f'<p>{links}</p><details><summary>Stages and failure details</summary><pre>{esc(json.dumps({"stages": row["stages"], "error": row["error"]}, indent=2))}</pre></details></article>')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Research-execution harness benchmark</title><style>
:root{font-family:system-ui;color:#e8edf5;background:#101721}body{max-width:1180px;margin:auto;padding:32px}h1{font-size:2.2rem}p{line-height:1.6;color:#c5d0df}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:14px;border-bottom:1px solid #344356}a{color:#85c8ff}article,.box{background:#182433;border:1px solid #344356;border-radius:12px;padding:20px;margin:18px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}button,select{padding:10px;margin:5px;background:#25374d;color:white;border:1px solid #526881;border-radius:6px}.flow{display:flex;flex-wrap:wrap;gap:8px}.flow span{background:#25374d;padding:10px;border-radius:6px}small{color:#adc0d7}</style>
<h1>Research → score → execute → measure</h1>
<p>BBBC039 fluorescence microscopy: <strong>__N__ images × __R__ runs × two arms</strong>. Split: __SPLIT__. __REPLAY__ This is a local counting task derived from reference segmentation masks, not the published benchmark's original score.</p>
<div class="flow"><span>Structured query</span>→<span>Web research</span>→<span>Jev candidate scores</span>→<span>Usage documentation</span>→<span>Astra plans</span>→<span>Jev plan scores</span>→<span>Codex shell + model inference</span>→<span>Artifact checks + visual review</span>→<span>Jev review / replan</span></div>
<div class="box"><h2>All attempts stay in the denominator</h2><p>“Within 10%” is the primary outcome: missing answers and execution failures score zero. Conditional MAPE measures error only among answered tasks; compare it together with coverage. Provisional outputs are scored but are not presented as Jev-approved. Jev confidence is not calibrated accuracy.</p><table><thead><tr><th>Arm</th><th>Answered</th><th>Within 10%</th><th>Conditional MAPE</th><th>Mean runtime</th><th>Review status</th></tr></thead><tbody>__SUMMARY__</tbody></table></div>
<p>Both arms receive the same question and contrast-mapped preview. The full harness also reads original 16-bit pixels and uses research, code and pretrained models. Linux CPU execution: this evaluates the complete capability package, not the isolated causal contribution of Jev or extra inference budget.</p>
<details><summary>Protocol and uncertainty</summary><pre>__PROTOCOL__</pre></details>
<details><summary>Repeated counts per image and their variation</summary><p>Means and sample standard deviations use available counts. A missing count stays missing and contributes a failure to the primary score.</p><table><thead><tr><th>Image</th><th>Reference</th><th>Vanilla counts</th><th>Full-harness counts</th></tr></thead><tbody>__IMAGES__</tbody></table></details>
<h2>Inspect each attempt</h2><label>Arm <select id="mode"><option value="all">Both</option><option>full</option><option>vanilla</option></select></label><button id="prev">Previous</button><span id="page"></span><button id="next">Next</button><main>__CARDS__</main>
<script>let page=0;const cards=[...document.querySelectorAll('article')],mode=document.getElementById('mode');function draw(){const rows=cards.filter(x=>mode.value==='all'||x.dataset.mode===mode.value);page=Math.max(0,Math.min(page,Math.ceil(rows.length/6)-1));cards.forEach(x=>x.hidden=true);rows.slice(page*6,page*6+6).forEach(x=>x.hidden=false);document.getElementById('page').textContent=`Page ${page+1} / ${Math.max(1,Math.ceil(rows.length/6))}`;}mode.onchange=()=>{page=0;draw()};document.getElementById('prev').onclick=()=>{page--;draw()};document.getElementById('next').onclick=()=>{page++;draw()};draw();</script></html>'''
    page = page.replace("__N__", str(result["cohort_images"])).replace("__R__", str(result["repetitions"]))
    page = page.replace("__SPLIT__", esc(result["selection"].get("split", "unspecified")))
    page = page.replace("__REPLAY__", "Development prefix replay: not an independent complete benchmark trial." if result["selection"].get("development_prefix_replay") else "Every attempt runs independently from the original query and input.")
    page = page.replace("__SUMMARY__", summary_rows).replace("__CARDS__", "".join(cards)).replace("__IMAGES__", image_rows)
    page = page.replace("__PROTOCOL__", esc(json.dumps({"selection": result["selection"], "paired_success_difference": result["paired_success_difference"]}, indent=2)))
    (report / "index.html").write_text(page)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="test")
    collect(parser.parse_args().split)
