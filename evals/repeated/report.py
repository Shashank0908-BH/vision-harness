"""Human-readable results without hiding incomplete trials or paired ablations."""

import html
import json
import statistics

import cv2
import numpy as np
from markdown_it import MarkdownIt

from vision_harness.tracing import write_json

from .data import DATA, REPEATS, REPORT, RUNS

LABELS = {
    "vanilla": "Vanilla Astra",
    "astra_tools_paired": "Astra + preferred specialist (paired)",
    "jev_selection_stage": "Astra + Jev selection (pre-review stage)",
    "full_harness": "Full current harness",
    "strict_support_diagnostic": "Strict-support diagnostic",
    "stardist-default": "Fixed StarDist default",
    "stardist-sensitive": "Fixed StarDist sensitive",
    "stardist-conservative": "Fixed StarDist conservative",
    "cellpose-sam": "Fixed Cellpose-SAM",
    "astra_preferred_measurement": "Astra-preferred measurement only",
    "jev_selected_measurement": "Jev-selected measurement only",
}


def esc(value):
    return html.escape(str(value), quote=True)


def number(value, digits=2, suffix=""):
    return "—" if value is None else f"{value:.{digits}f}{suffix}"


def render():
    result = json.loads((REPORT / "results.json").read_text())
    inputs = json.loads((DATA / "inputs.json").read_text())
    rows, md = (
        [],
        [
            "# Repeated external microscopy benchmark",
            "",
            "37 official Kromp test images × 3 fresh repetitions per image.",
            "",
            "| Arm | Counts returned | Complete-cohort MAPE | Conditional MAPE | Run MAPE SD | Within 10%, all attempts |",
            "|---|---:|---:|---:|---:|---:|",
        ],
    )
    for arm, m in result["metrics"].items():
        interval = m["image_cluster_mape_interval_complete_images_only"]
        ci = (
            "—"
            if not interval
            else f"{interval['ci95'][0]:.2f}–{interval['ci95'][1]:.2f} ({interval['image_clusters']} images)"
        )
        cells = [
            LABELS[arm],
            f"{m['completed']}/{m['attempts']}",
            number(m["mape_percent"], suffix="%"),
            number(m["conditional_mape_percent"], suffix="%"),
            number(m["run_mape_sd"]),
            number(100 * m["all_attempt_success_at_10_percent"], suffix="%"),
        ]
        rows.append(
            "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in cells) + f"<td>{esc(ci)}</td></tr>"
        )
        md.append("| " + " | ".join(cells) + " |")
    md += [
        "",
        "Conditional MAPE uses only returned numeric answers. A missing complete-cohort MAPE means one or more outputs were absent. All-attempt within-10% success counts missing outputs as failures.",
        "",
        "Run SD is the sample standard deviation of three complete cohort MAPEs; it is not uncertainty over new images. Confidence intervals resample images, averaging repetitions within image; they do not establish generalization to independent patients.",
        "",
        "Review statuses: " + json.dumps(result["review"]),
        "",
        "Routing: " + json.dumps(result["routing"]),
    ]
    md += [
        "",
        "## Three-run averages",
        "",
        "These are conditional returned-answer MAPEs; coverage can differ between repetitions. SD is in percentage points.",
        "",
        "| Arm | Run 1 | Run 2 | Run 3 | Mean ± run SD |",
        "|---|---:|---:|---:|---:|",
    ]
    repeated_rows = []
    repeated_summary = {}
    for arm, metric in result["metrics"].items():
        values = [r["conditional_mape"] for r in metric["repetitions"]]
        complete = len(values) == REPEATS and all(v is not None for v in values)
        mean = statistics.mean(values) if complete else None
        sd = statistics.stdev(values) if complete else None
        repeated_summary[arm] = {
            "conditional_run_mapes": values,
            "mean": mean,
            "sample_sd": sd,
            "scope": "each repetition uses returned counts only; coverage may differ",
        }
        cells = [LABELS[arm]] + [
            number(r["conditional_mape"], suffix="%") + f" ({r['answered']}/{r['total']})"
            for r in metric["repetitions"]
        ]
        cells.append(number(mean, suffix="%") + " ± " + number(sd) + " pp")
        repeated_rows.append("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in cells) + "</tr>")
        md.append("| " + " | ".join(cells) + " |")
    (REPORT / "final-score.md").write_text("\n".join(md) + "\n")
    write_json(REPORT / "repetition-summary.json", repeated_summary)
    seg_rows = []
    for arm, m in result["segmentation"].items():
        seg_rows.append(
            f"<tr><td>{esc(LABELS.get(arm, arm))}</td><td>{m['completed']}/111</td><td>{number(m['mean_image_f1'])}</td><td>{number(m['mean_instance_matching_score'])}</td><td>{esc(m.get('images_with_three_bitwise_identical_maps', 'n/a'))}</td></tr>"
        )
    class_rows = []
    for cls, metrics in result["by_class"].items():
        cells = [cls, str(metrics["vanilla"]["attempts"] // 3)]
        for arm in [
            "vanilla",
            "astra_tools_paired",
            "jev_selection_stage",
            "full_harness",
            "cellpose-sam",
            "stardist-sensitive",
        ]:
            m = metrics[arm]
            cells.append(
                number(m["conditional_mape_percent"], suffix="%")
                + f" [{m['completed']}/{m['attempts']}]"
            )
        class_rows.append("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in cells) + "</tr>")
    paired_rows = []
    for arm, p in result["paired_vs_vanilla"].items():
        delta = p["error_difference_pp_complete_paired_images"]
        success = p["all_attempt_success_difference_pp"]

        def describe(v):
            return (
                "No complete paired images"
                if not v
                else f"{v['mean']:+.2f} pp; 95% CI {v['ci95'][0]:+.2f} to {v['ci95'][1]:+.2f}; n={v['image_clusters']} images"
            )

        paired_rows.append(
            f"<tr><td>{esc(LABELS[arm])}</td><td>{esc(describe(delta))}</td><td>{esc(describe(success))}</td></tr>"
        )
    pages = []
    for index, item in enumerate(inputs, 1):
        samples = sorted(
            [r for r in result["records"] if r["id"] == item["id"]], key=lambda r: r["repeat"]
        )
        directory = REPORT / "previews" / item["id"]
        directory.mkdir(parents=True, exist_ok=True)
        original = cv2.imread(item["image"])
        ratio = min(1, 696 / original.shape[1])
        size = (round(original.shape[1] * ratio), round(original.shape[0] * ratio))
        cv2.imwrite(
            str(directory / "original.png"),
            cv2.resize(original, size, interpolation=cv2.INTER_AREA),
        )
        # Reference visualization is made only after inference/scoring has finished.
        truth_path = DATA / "source/labels" / item["source_filename"]
        truth = cv2.imread(str(truth_path), cv2.IMREAD_UNCHANGED)
        reference = original.copy()
        ids = np.unique(truth)
        for label in ids[ids > 0]:
            mask = (truth == label).astype(np.uint8)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(reference, contours, -1, (80, 230, 180), 2)
        cv2.imwrite(
            str(directory / "reference.png"),
            cv2.resize(reference, size, interpolation=cv2.INTER_AREA),
        )
        trial_rows = []
        links = []
        for r in samples:
            values = [
                r["repeat"],
                r["values"]["vanilla"],
                r["values"]["astra_tools_paired"],
                r["values"]["jev_selection_stage"],
                r["values"]["full_harness"],
                r["selected_id"],
                r["review_status"],
            ]
            trial_rows.append(
                "<tr>"
                + "".join(f"<td>{esc(v if v is not None else 'missing')}</td>" for v in values)
                + "</tr>"
            )
            local = RUNS / f"repeat-{r['repeat']}" / item["id"]
            links.append(
                f'<p>Repeat {r["repeat"]}: <a href="../../{local}/routing/trajectory.json">routing trace</a> · <a href="../../{local}/vanilla/trajectory.json">vanilla trace</a> · <a href="../../{local}/astra-tools/trajectory.json">Astra-tools trace</a></p>'
            )
        mask_cards = []
        first = samples[0]
        for pid in [
            "stardist-default",
            "stardist-sensitive",
            "stardist-conservative",
            "cellpose-sam",
        ]:
            source = RUNS / "repeat-1" / item["id"] / "routing/artifacts" / f"{pid}-overlay.png"
            if not source.exists():
                mask_cards.append(
                    f"<article><h3>{esc(pid)}</h3><p>Missing specialist output.</p></article>"
                )
                continue
            overlay = cv2.imread(str(source))
            cv2.imwrite(
                str(directory / f"{pid}.png"),
                cv2.resize(overlay, size, interpolation=cv2.INTER_AREA),
            )
            seg = first["segmentation"][pid]
            counts = [r["values"][pid] for r in samples]
            mask_cards.append(
                f'<article><h3>{esc(pid)}</h3><p>Repeated counts: {esc(counts)}. Repeat-1 F1: {seg["f1"]:.3f}.</p><a href="../../{source}"><img loading="lazy" src="previews/{item["id"]}/{pid}.png" alt="{esc(pid)} predicted instance overlay"></a></article>'
            )
        pages.append(f"""<section class="task" id="task-{index}" {"hidden" if index > 1 else ""}>
<p class="eyebrow">Image {index}/37 · {esc(first["class"])}</p><h2>{esc(item["source_filename"])}</h2>
<p>Reference: <b>{first["expected"]} nuclei</b>. Native dimensions: {item["width"]} × {item["height"]}. All inference used the full-size image; these previews are scaled for display.</p>
<div class="grid"><article><h3>Original image</h3><a href="../../{item["image"]}"><img src="previews/{item["id"]}/original.png" alt="Original fluorescence image"></a></article><article><h3>Expert reference outlines</h3><p>Shown only for evaluation; never supplied to the models.</p><a href="../../{truth_path}"><img loading="lazy" src="previews/{item["id"]}/reference.png" alt="Expert reference nucleus outlines"></a></article></div>
<div class="scroll"><table><thead><tr><th>Repeat</th><th>Vanilla</th><th>Astra-tools</th><th>Selection stage</th><th>Full</th><th>Selected</th><th>Review</th></tr></thead><tbody>{"".join(trial_rows)}</tbody></table></div>
<details><summary>Inspect all scores, outcomes and repeat-level records</summary><pre>{esc(json.dumps(samples, indent=2))}</pre>{"".join(links)}</details>
<h3>All fixed procedures, first repetition</h3><div class="grid">{"".join(mask_cards)}</div></section>""")
    options = "".join(
        f'<option value="{i}">{i}. {esc(x["source_filename"])}</option>'
        for i, x in enumerate(inputs, 1)
    )
    findings = (
        (REPORT / "findings.md").read_text()
        if (REPORT / "findings.md").exists()
        else "See the measured tables below. All three repetitions and missing outcomes are retained."
    )
    text = (
        """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Repeated hard microscopy benchmark</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f5f7f6;color:#1c3038;font:16px/1.6 system-ui,sans-serif}main{max-width:1280px;margin:auto;padding:35px 22px}h1{font-size:clamp(2rem,5vw,3.5rem);line-height:1.1}h2{line-height:1.25;overflow-wrap:anywhere}.eyebrow{text-transform:uppercase;letter-spacing:.09em;font-weight:700;color:#3e626c}a{color:#076976}figure{margin:22px 0}figcaption{font-size:14px;color:#49626b}p,td{overflow-wrap:anywhere}.notice{background:#fff2d7;border-left:4px solid #b3751a;padding:16px 20px}.scroll{overflow:auto;margin:20px 0}table{border-collapse:collapse;width:100%;background:white}th,td{padding:11px;border-bottom:1px solid #d7e1df;text-align:left}th{background:#e6eeee;font-size:14px;white-space:normal}td{font-size:14px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}article{padding:17px;background:white;border:1px solid #d3dfdd;border-radius:10px;min-width:0}img{width:100%;height:auto;border-radius:6px}.original{max-width:696px}nav{position:sticky;top:0;z-index:1;display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:14px 0;background:#f5f7f6}select{max-width:100%;min-width:0;flex:1;padding:10px;border:1px solid #709296;border-radius:6px;font:inherit}button{padding:10px 14px;background:#086876;color:white;border:0;border-radius:6px;font:inherit;cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;background:#eaf0ee;padding:18px}summary{padding:14px 0;cursor:pointer}.task{margin-bottom:40px}[hidden]{display:none!important}footer{border-top:1px solid #d0dcda;margin-top:40px;padding-top:20px}@media(max-width:700px){main{padding:25px 12px}.grid{grid-template-columns:1fr}th,td{padding:8px}nav select{flex-basis:100%}}</style>
<main><p class="eyebrow">Real external images · fresh repeated trials</p><h1>37 harder microscopy images.<br>Three repetitions each.</h1>
<p>The full official Kromp test split spans ten published preparation/imaging groups, including low-signal fields and clustered nuclei. Models, parameters, prompts and review policy were frozen before inference.</p>
<div class="notice"><b>Completion is not approval.</b> The current full harness may return a grounded estimate with a Jev caution flag. API errors, abstentions and unsupported inputs remain missing answers. The strict-support row is a diagnostic filter, not a rerun of the historical replanning loop.</div>
<p><b>The current harness does not establish a counting advantage.</b> Vanilla returns 107/111 counts and is within 10% of reference on 70.3% of attempts. Full harness returns 101/111 and is within 10% on 55.9%. Fixed Cellpose ties vanilla's all-attempt success rate. Read coverage alongside error.</p>
<details><summary>Read the complete findings, failure examples and interpretation</summary><div class="findings">"""
        + MarkdownIt("commonmark", {"html": False}).render(findings)
        + """</div></details>
<h2>Counting results</h2><figure><img src="count-success.png" alt="Counts within ten percent across all scheduled attempts, with image bootstrap confidence intervals"><figcaption>Missing answers count as failures. <a href="count-success.svg">Download vector figure</a>.</figcaption></figure><p>Lower MAPE is better. Conditional error uses returned answers only; read it beside coverage. Within-10% success uses every scheduled attempt, treating missing answers as failures. Run SD measures variation across the three full-cohort runs; a dash means a complete-cohort statistic is unavailable.</p><div class="scroll"><table><thead><tr><th>Arm</th><th>Counts returned</th><th>Full MAPE ↓</th><th>Conditional MAPE ↓</th><th>Run SD</th><th>Within 10% ↑</th><th>95% image-bootstrap interval, complete images</th></tr></thead><tbody>"""
        + "".join(rows)
        + """</tbody></table></div>
<p>Astra-tools shares the initial proposal with the full route but makes a separate answer call using only Astra's preferred mask. The Jev selection row is the saved pre-review answer. These are paired stage ablations, not independently replanned pipelines.</p>
<h2>All three repetitions</h2><p>Each entry shows conditional count MAPE and returned/scheduled counts. The final column averages the three conditional run MAPEs and gives their sample standard deviation. Different completion patterns can affect this variability; consult all-attempt success above.</p><div class="scroll"><table><thead><tr><th>Arm</th><th>Repeat 1</th><th>Repeat 2</th><th>Repeat 3</th><th>Conditional mean ± run SD</th></tr></thead><tbody>"""
        + "".join(repeated_rows)
        + """</tbody></table></div><h2>Paired comparison with vanilla</h2><p>Error differences below zero favor the named arm. Success differences above zero favor it. Intervals average repetitions within each image, then resample images 10,000 times. Images can share biological origins; these are not patient-level confidence intervals.</p><div class="scroll"><table><thead><tr><th>Arm</th><th>Error difference: complete paired images</th><th>Within-10% success difference: all attempts</th></tr></thead><tbody>"""
        + "".join(paired_rows)
        + """</tbody></table></div>
<h2>Mask quality and repeatability</h2><p>Higher F1 and matching scores are better. Instances are matched one-to-one at IoU ≥0.5. Matching score is TP/(TP+FP+FN), not COCO average precision. Vanilla provides no instance masks, so it has no segmentation score.</p><div class="scroll"><table><thead><tr><th>Procedure</th><th>Masks</th><th>Mean F1</th><th>Matching score</th><th>Images with 3 identical maps /37</th></tr></thead><tbody>"""
        + "".join(seg_rows)
        + """</tbody></table></div>
<h2>Published difficulty groups</h2><figure><img src="group-errors.png" alt="Conditional count errors and coverage across ten official test groups"><figcaption>Read each error with its completed/scheduled counts. <a href="group-errors.svg">Download vector figure</a>.</figcaption></figure><p>Each cell shows conditional count MAPE and returned/scheduled counts. GNB: ganglioneuroblastoma; NB: neuroblastoma; NC: normal cells; TS: tissue sections. The official metadata describes the ten subgroups.</p><div class="scroll"><table><thead><tr><th>Class</th><th>Images</th><th>Vanilla</th><th>Astra-tools</th><th>Selection stage</th><th>Full</th><th>Cellpose</th><th>StarDist sensitive</th></tr></thead><tbody>"""
        + "".join(class_rows)
        + """</tbody></table></div>
<h2>Inspect all 37 fields</h2><nav aria-label="Benchmark image pagination"><button id="prev">Previous</button><select id="page" aria-label="Image">"""
        + options
        + """</select><button id="next">Next</button><span id="position" aria-live="polite">1 / 37</span></nav>"""
        + "".join(pages)
        + """
<footer><p><a href="protocol.json">Frozen protocol</a> · <a href="results.json">All results</a> · <a href="final-score.md">Score table</a> · <a href="findings.md">Findings</a> · <a href="audit.json">Trace and evidence audit</a> · <a href="diagnostics.json">Descriptive diagnostics</a> · <a href="../../docs/repeated-benchmark.md">Method and file map</a> · <a href="https://www.ebi.ac.uk/biostudies/BioImages/studies/S-BIAD634">Official dataset</a> · <a href="https://www.nature.com/articles/s41597-020-00608-w">Paper</a></p><p>Native specialist workers and hosted Astra/Jev APIs; Harbor ATIF traces, not Harbor Docker jobs. Three repeats quantify runtime variation, not three new independent cohorts. Public training exposure is unknown. Reference masks were decoded after inference; annotation uncertainty and transfer across acquisition conditions remain limitations.</p></footer></main>
<script>const select=document.getElementById('page');function show(n){n=Math.max(1,Math.min(37,n));select.value=n;document.querySelectorAll('.task').forEach(s=>s.hidden=s.id!=='task-'+n);document.getElementById('position').textContent=n+' / 37';document.getElementById('prev').disabled=n===1;document.getElementById('next').disabled=n===37;}select.addEventListener('change',()=>show(+select.value));document.getElementById('prev').onclick=()=>show(+select.value-1);document.getElementById('next').onclick=()=>show(+select.value+1);show(1);</script></html>"""
    )
    (REPORT / "index.html").write_text(text)
    write_json(
        REPORT / "render-summary.json",
        {
            "pages": 37,
            "repeats_per_page": 3,
            "mask_previews": "first repetition; links to full-size native outputs",
            "image_inference_resolution": "original",
        },
    )
    print(REPORT / "index.html")
