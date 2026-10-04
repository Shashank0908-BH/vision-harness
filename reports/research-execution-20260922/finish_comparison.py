"""Join the two completed comparisons without counting their shared control twice."""

import html
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parents[1]
FOLLOWUP = REPORT / "test-transport96"


def number(value, suffix=""):
    return "—" if value is None else f"{value:.2f}{suffix}"


def write_comparison():
    original = json.loads((REPORT / "results.json").read_text())
    followup = json.loads((FOLLOWUP / "results.json").read_text())
    assert original["metrics"]["vanilla"] == followup["metrics"]["vanilla"]
    assert original["selection"]["filenames"] == followup["selection"]["filenames"]
    assert original["repetitions"] == followup["repetitions"] == 3
    assert original["cohort_images"] == followup["cohort_images"] == 12
    interruption_path = REPORT / "infrastructure-interruption.json"
    interruption = json.loads(interruption_path.read_text()) if interruption_path.exists() else None
    interruption_note = (
        "Infrastructure interruption: macOS sleep logs show the laptop repeatedly slept while "
        "requests were active. The recorded failures remain in the denominator. These numbers "
        "describe this interrupted deployment run; they are not a clean estimate of the "
        "harness's accuracy or latency relative to vanilla."
    ) if interruption else ""
    conditions = [
        ("Vanilla Astra", original, "vanilla", "#79b9ff", "index.html"),
        ("Full harness · 48 KB", original, "full", "#c4a3ff", "index.html"),
        ("Full harness · 96 KB", followup, "full", "#63d8b1", "test-transport96/index.html"),
    ]
    rows, bars, summaries, timing_notes = [], [], {}, []
    for title, data, mode, color, link in conditions:
        summary = data["metrics"][mode]
        assert summary["attempts"] == 36
        summaries[title] = summary
        recorded_times = sum(r["elapsed_seconds"] is not None for r in data["records"] if r["mode"] == mode)
        timing_notes.append(f"{title}: {recorded_times}/36 runtimes recorded")
        rows.append(f'<tr><th><a href="{link}">{title}</a></th><td>{summary["answered"]}/36</td>'
                    f'<td><b>{summary["within_10_percent"]}/36 ({summary["all_attempt_success_percent"]:.2f}%)</b></td>'
                    f'<td>{number(summary["conditional_mape_percent"], "%")}</td>'
                    f'<td>{number(summary["mean_seconds"], " s")}</td>'
                    f'<td>{number(summary["mean_instance_f1_answered_masks"])}</td></tr>')
        interval = summary["success_image_cluster_interval"]["ci95"]
        bars.append(f'<div class="barrow"><span>{title}</span><div class="track">'
                    f'<div style="width:{summary["all_attempt_success_percent"]}%;background:{color}"></div></div>'
                    f'<strong>{summary["all_attempt_success_percent"]:.1f}%</strong>'
                    f'<small>95% image-bootstrap interval: {interval[0]*100:.1f}–{interval[1]*100:.1f}%</small></div>')
    cards = []
    per_image = []
    newer_images = {row["id"]: row for row in followup["per_image"]}
    for row in original["per_image"]:
        new_row = newer_images[row["id"]]
        assert row["expected"] == new_row["expected"]
        assert row["arms"]["vanilla"] == new_row["arms"]["vanilla"]
        entries = [("Vanilla", row["arms"]["vanilla"]),
                   ("Full · 48 KB", row["arms"]["full"]),
                   ("Full · 96 KB", new_row["arms"]["full"])]
        image_rows = []
        for label, details in entries:
            values = ", ".join("—" if value is None else str(value) for value in details["counts"])
            image_rows.append(f'<tr><th>{label}</th><td>{values}</td><td>{number(details["mean_count"])}</td>'
                              f'<td>{number(details["count_sd"])}</td><td>{details["within_10_percent"]}/3</td></tr>')
        sample = next(r for r in original["records"] if r["id"] == row["id"] and r["mode"] == "vanilla")
        image_path = ROOT / sample["trial"] / "agent/run/artifacts/original.png"
        image_url = Path(os.path.relpath(image_path, REPORT)).as_posix()
        cards.append(f'<article><h3>{row["id"]} <small>Reference: {row["expected"]} nuclei</small></h3>'
                     f'<img loading="lazy" src="{html.escape(image_url, quote=True)}" alt="Microscopy input for {row["id"]}">'
                     '<div class="scroll"><table><thead><tr><th>Condition</th><th>All three counts</th><th>Mean</th><th>SD</th><th>Within 10%</th></tr></thead>'
                     f'<tbody>{"".join(image_rows)}</tbody></table></div></article>')
        per_image.append({"id": row["id"], "expected": row["expected"], "conditions": dict(entries)})
    differences = {"48 KB minus vanilla": original["paired_success_difference"],
                   "96 KB minus vanilla": followup["paired_success_difference"]}
    difference_rows = "".join(f'<li>{label}: <b>{value["mean"]*100:+.2f} percentage points</b>; '
                              f'95% interval [{value["ci95"][0]*100:+.2f}, {value["ci95"][1]*100:+.2f}].</li>'
                              for label, value in differences.items())
    review_statuses = {title: summary["review_statuses"] for title, summary in summaries.items()}
    data = {"unique_trials": 108, "images": 12, "repetitions": 3,
            "infrastructure_interruption": interruption,
            "shared_baseline_trials": 36, "summaries": summaries,
            "paired_differences": differences, "per_image": per_image,
            "timing_coverage": timing_notes,
            "limits": ["The configuration follow-up reuses the same images and controls.",
                       "Intervals are descriptive, unadjusted image-cluster bootstrap intervals.",
                       "Extra research, pixels, code and inference are bundled; Jev's causal contribution is not isolated.",
                       "Conditional error/F1 omit missing outputs; primary success includes every planned attempt."]}
    (REPORT / "comparison.json").write_text(json.dumps(data, indent=2)+"\n")
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vision harness · repeated comparison</title><style>
:root{font-family:system-ui,sans-serif;color:#ecf2fa;background:#101721}body{max-width:1180px;margin:auto;padding:30px}h1{font-size:2.2rem;line-height:1.2}p,li{line-height:1.65;color:#c6d3e3}a{color:#8dcbff}small{color:#b3c5da;font-weight:normal}.box,article{padding:22px;margin:20px 0;background:#192536;border:1px solid #34475f;border-radius:14px}.flow{display:flex;flex-wrap:wrap;gap:9px}.flow span{padding:10px;background:#253a50;border-radius:8px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse}th,td{padding:12px;text-align:left;border-bottom:1px solid #34475f}thead th{color:#b3c5da;font-size:.9rem}tbody th{font-weight:500}.barrow{display:grid;grid-template-columns:210px 1fr 70px;gap:10px;margin:18px 0;align-items:center}.barrow small{grid-column:2/4}.track{height:20px;background:#34475f;border-radius:5px;overflow:hidden}.track div{height:100%}article img{display:block;width:100%;max-width:440px;height:auto;border-radius:8px;margin:16px auto}button{padding:10px 18px;margin:5px;background:#28415c;color:white;border:1px solid #6e87a4;border-radius:7px}pre{white-space:pre-wrap;overflow-wrap:anywhere}#cards{display:grid;grid-template-columns:1fr 1fr;gap:18px}#cards article{margin:0;min-width:0}article[hidden]{display:none}@media(max-width:800px){body{padding:16px}#cards{grid-template-columns:1fr}.barrow{grid-template-columns:1fr 60px}.barrow span{grid-column:1/3}.barrow small{grid-column:1/3}}</style></head><body>
<h1>Vision harness: the repeated experiment</h1>__INTERRUPTION__<p><b>12 real BBBC039 test images · 3 runs per condition · 108 unique trials.</b> Every condition includes all 36 planned attempts. The vanilla control is shared between the two comparisons.</p>
<div class="flow"><span>Original query + image</span>→<span>Research models/libraries</span>→<span>Jev scores candidates</span>→<span>Read usage docs</span>→<span>Astra programs</span>→<span>Jev scores plans</span>→<span>Codex execution</span>→<span>Artifact + visual checks</span>→<span>Jev review / bounded replan</span>→<span>Separate hidden-label grader</span></div>
<section class="box"><h2>Primary result: within 10% of the reference count</h2><p>Higher is better. Missing counts and failures score zero. A Jev confidence value is never used as the benchmark score.</p>__BARS__<div class="scroll"><table><thead><tr><th>Condition</th><th>Counts</th><th>Within 10%</th><th>Conditional MAPE</th><th>Mean recorded runtime</th><th>Mask F1</th></tr></thead><tbody>__ROWS__</tbody></table></div><ul>__DIFFERENCES__</ul><p>Repetitions are averaged within each image before resampling the 12 images. These are descriptive, unadjusted bootstrap intervals from a small pilot.</p></section>
<section class="box"><h2>Why there are two harness configurations</h2><p>The original 48 KB local request guard rejected complete Jev inputs. A development-only probe demonstrated that the service accepted a larger request. A separately frozen follow-up raised the local guard to 96 KB and ran all 36 harness attempts afresh. The original failures remain visible; none were replaced with favorable retries. Raising the cap can also change how many subjects are scored in one request.</p><p>The amendment was chosen before inspecting reference accuracy. It uses the same images and all 36 original controls, so it is a configuration follow-up, not a new independent validation cohort. <a href="transport-amendment.md">Read the amendment</a>.</p><p><a href="index.html">Original paginated traces</a> · <a href="test-transport96/index.html">96 KB paginated traces</a> · <a href="../../docs/research-execution-v3.md">Architecture and file map</a> · <a href="comparison.json">Combined data</a></p></section>
<details class="box"><summary>What the numbers mean and what they cannot establish</summary><ul><li><b>Conditional MAPE:</b> mean absolute percentage count error among returned counts; lower is better. It excludes missing answers, so read it with coverage.</li><li><b>Mask F1:</b> instance matching at IoU ≥ 0.5, averaged over returned masks. A correct total can still hide missed and extra objects.</li><li><b>Review status:</b> provisional answers remain provisional. A later API/planning failure may preserve an earlier reviewed answer and its matching mask.</li><li><b>Runtime:</b> means use recorded controller durations. __TIMING__.</li><li>The two harness jobs ran concurrently with four and three workers, respectively, using the same per-trial CPU/memory caps. Timing is observational under this load.</li><li>The full harness has original 16-bit pixels, research, code and specialist inference. This comparison cannot isolate Jev's contribution, establish broad multimodal superiority or validate medical use.</li><li>Data: <a href="https://bbbc.broadinstitute.org/BBBC039">BBBC039</a>. This counting task is derived from reference segmentation masks; it is not the dataset's original published score. Public pretrained exposure is unknown.</li></ul><pre>__REVIEW__</pre></details>
<h2>Inspect the images and all three counts</h2><p>A dash is a missing count. Means and sample standard deviations use available counts; the primary score still counts missing outputs as failures.</p><nav><button id="prev">Previous</button><span id="page"></span><button id="next">Next</button></nav><main id="cards">__CARDS__</main>
<script>let page=0;const cards=[...document.querySelectorAll('#cards article')];function draw(){page=Math.max(0,Math.min(page,Math.ceil(cards.length/4)-1));cards.forEach((card,i)=>card.hidden=i<page*4||i>=(page+1)*4);document.getElementById('page').textContent=`Page ${page+1} / ${Math.ceil(cards.length/4)}`;document.getElementById('prev').disabled=page===0;document.getElementById('next').disabled=(page+1)*4>=cards.length;}document.getElementById('prev').onclick=()=>{page--;draw()};document.getElementById('next').onclick=()=>{page++;draw()};draw();</script></body></html>'''
    for marker, content in {"__BARS__": "".join(bars), "__ROWS__": "".join(rows),
                            "__INTERRUPTION__": (f'<aside class="box"><b>{html.escape(interruption_note)}</b> '
                                                 '<a href="host-sleep-events.txt">Host evidence</a></aside>') if interruption else "",
                            "__DIFFERENCES__": difference_rows, "__CARDS__": "".join(cards),
                            "__TIMING__": html.escape("; ".join(timing_notes)),
                            "__REVIEW__": html.escape(json.dumps(review_statuses, indent=2))}.items():
        page = page.replace(marker, content)
    (REPORT / "comparison.html").write_text(page)
    markdown = ["# Combined repeated comparison", "", "12 BBBC039 images × 3 repetitions × 3 conditions = **108 unique trials**. The 36 vanilla trials are shared by both comparisons.", "",
                "| Condition | Counts returned | Within 10% | Conditional MAPE | Mean recorded runtime |", "|---|---:|---:|---:|---:|"]
    if interruption:
        markdown[2:2] = [f"> {interruption_note} [Host evidence](host-sleep-events.txt).", ""]
    for title, summary in summaries.items():
        markdown.append(f"| {title} | {summary['answered']}/36 | {summary['within_10_percent']}/36 ({summary['all_attempt_success_percent']:.2f}%) | {number(summary['conditional_mape_percent'], '%')} | {number(summary['mean_seconds'], ' s')} |")
    markdown += ["", "All planned trials remain in each condition's denominator. The 96 KB follow-up uses the same cohort and all controls; it is not an independent new validation set.", ""]
    for label, value in differences.items():
        markdown.append(f"- {label}: {value['mean']*100:+.2f} percentage points, with an image-cluster bootstrap 95% interval of [{value['ci95'][0]*100:+.2f}, {value['ci95'][1]*100:+.2f}].")
    markdown += ["", "These descriptive intervals use 12 image clusters, not 36 independent images. Conditional MAPE excludes missing answers and must be read with coverage. Extra research, pixels, code and inference are bundled, so Jev's causal contribution is not isolated.", "", "[Visual comparison and all repeated counts](comparison.html) · [Original traces](index.html) · [96 KB traces](test-transport96/index.html) · [Amendment](transport-amendment.md)"]
    (REPORT / "comparison.md").write_text("\n".join(markdown)+"\n")
    (REPORT / "comparison-complete.json").write_text(json.dumps({"status": "generated",
        "unique_trials": 108, "finished_at_utc": datetime.now(timezone.utc).isoformat()}, indent=2)+"\n")


if __name__ == "__main__":
    while not all((directory / "completion.json").exists() for directory in (REPORT, FOLLOWUP)):
        time.sleep(30)
    write_comparison()
