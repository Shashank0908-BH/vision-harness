"""Render the audit as a self-contained, linked local report (system Python)."""

import html
import json
import os
import statistics
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/stardist-audit-20260922"
os.environ["MPLCONFIGDIR"] = str(ROOT / ".model-cache/matplotlib")
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

NAMES = {
    "vanilla": "Vanilla Astra",
    "astra_tools_paired": "Astra + preferred specialist",
    "jev_selection_stage": "Astra + Jev selection stage",
    "full_harness": "Full v1 harness",
    "strict_support_diagnostic": "Strict-support diagnostic",
    "stardist-default": "Original StarDist default",
    "stardist-sensitive": "Original StarDist sensitive",
    "stardist-conservative": "Original StarDist conservative",
    "cellpose-sam": "Original Cellpose-SAM",
    "astra_preferred_measurement": "Astra-preferred measurement only",
    "jev_selected_measurement": "Jev-selected measurement only",
    "native-default": "Native StarDist, original size",
    "native-half": "Native StarDist, half size (diagnostic)",
    "native-quarter": "Native StarDist, quarter size (diagnostic)",
    "native-sensitive": "Native StarDist sensitive",
    "native-conservative": "Native StarDist conservative",
}


def overlay(raw, labels):
    if raw.ndim == 2:
        raw = np.repeat(raw[..., None], 3, axis=-1)
    canvas = raw.copy()
    for label in np.unique(labels)[1:]:
        contours, _ = cv2.findContours((labels == label).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(canvas, contours, -1, (70, 255, 130), 2)
    return canvas


def main():
    data = json.loads((REPORT / "corrected-results.json").read_text())
    inputs = json.loads((ROOT / "evals/datasets/generated/kromp-repeated-20260922/inputs.json").read_text())
    rows = {r["id"]: r for r in data["records_repaired"] if r["repeat"] == 1}
    by_name = {r["source_filename"]: r for r in inputs}
    # Examples deliberately show a gain, a loss, and the reference repair.
    examples = ["normal_28.tif", "otherspecimen_6.tif", "otherspecimen_3.tif"]
    fig, axes = plt.subplots(3, 3, figsize=(15, 11), layout="constrained")
    for index, name in enumerate(examples):
        item = by_name[name]
        record = rows[item["id"]]
        raw = np.asarray(Image.open(ROOT / item["image"]))
        truth = np.asarray(Image.open(ROOT / "evals/datasets/generated/kromp-repeated-20260922/source/labels" / name))
        if name == "otherspecimen_3.tif":
            truth = np.load(REPORT / "otherspecimen_3-components-diagnostic.npz")["labels"]
        axes[index, 0].imshow(overlay(raw, truth))
        axes[index, 0].set_title(f'{name}\nReference: {record["expected"]} nuclei', fontsize=11)
        for col, variant in [(1, "native-default"), (2, "native-half")]:
            labels = np.load(ROOT / "runs/stardist-audit-native-20260922/repeat-1" / item["id"] / variant / "labels.npz")["labels"]
            axes[index, col].imshow(overlay(raw, labels))
            count = record["values"][variant]
            error = abs(count-record["expected"])/record["expected"]*100
            f1 = record["segmentation"][variant]["f1"]
            axes[index, col].set_title(f'{"Original size" if col == 1 else "Half size"}: {count} nuclei\nCount error {error:.1f}%; segmentation F1 {f1:.3f}', fontsize=11)
        for ax in axes[index]:
            ax.axis("off")
    fig.suptitle("Same weights, different input scale — improvement is image dependent", fontsize=17)
    fig.savefig(REPORT / "scale-comparison.png", dpi=160)
    plt.close(fig)

    def table(scenario):
        content = "<div class='scroll'><table><thead><tr><th>Arm</th><th>Counts</th><th>Mean count error ↓</th><th>Within 10% ↑</th><th>Mean segmentation F1 ↑</th></tr></thead><tbody>"
        for arm, metric in data["metrics"][scenario].items():
            segment = data["segmentation"].get(scenario, {}).get(arm, {})
            f1 = segment.get("mean_image_f1")
            content += f'<tr><td>{NAMES[arm]}</td><td>{metric["completed"]}/{metric["attempts"]}</td><td>{metric["conditional_mape_percent"]:.2f}%</td><td>{metric["within_10_percent"]}/{metric["attempts"]} ({100*metric["all_attempt_success_at_10_percent"]:.1f}%)</td><td>{f"{f1:.3f}" if f1 is not None else "—"}</td></tr>'
        return content + "</tbody></table></div>"

    per_image = "<div class='scroll'><table><thead><tr><th>Image</th><th>Reference</th><th>Default</th><th>Half</th><th>Quarter</th><th>Vanilla, three counts</th><th>Full v1, three counts</th></tr></thead><tbody>"
    for item in inputs:
        record = rows[item["id"]]
        repetitions = [r for r in data["records_repaired"] if r["id"] == item["id"]]
        values = [item["source_filename"], str(record["expected"])]
        values += [str(record["values"][v]) for v in ["native-default", "native-half", "native-quarter"]]
        values += [", ".join("missing" if r["values"][a] is None else str(int(r["values"][a])) for r in repetitions) for a in ["vanilla", "full_harness"]]
        per_image += "<tr>" + "".join(f"<td>{html.escape(v)}</td>" for v in values) + "</tr>"
    per_image += "</tbody></table></div>"
    per_runs = "| Arm | Run 1 | Run 2 | Run 3 | Mean ± sample SD |\n|---|---:|---:|---:|---:|\n"
    for arm, metric in data["metrics"]["repaired_37"].items():
        values = [r["conditional_mape"] for r in metric["repetitions"]]
        texts = [f'{v:.2f}% ({r["answered"]}/{r["total"]})' if v is not None else "—" for r in metric["repetitions"] for v in [r["conditional_mape"]]]
        summary = f"{statistics.mean(values):.2f}% ± {statistics.stdev(values):.2f} pp" if all(v is not None for v in values) else "—"
        per_runs += f'| {NAMES[arm]} | ' + " | ".join(texts) + f" | {summary} |\n"
    (REPORT / "three-run-averages.md").write_text("# Corrected reference: three-run averages\n\nConditional errors use returned answers only; coverage differs by arm and run. Fixed-profile repeat SD is not uncertainty over new images.\n\n" + per_runs)
    content = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>StarDist audit: reference labels and image scale</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#f4f6f8;color:#172b3a;font:17px/1.6 system-ui,sans-serif}}main{{max-width:1250px;margin:auto;padding:32px 20px}}h1{{font-size:clamp(2rem,5vw,3.2rem);line-height:1.15}}h2{{margin-top:2.5rem;line-height:1.2}}a{{color:#006c79}}.notice{{padding:20px;background:#fff1cd;border-left:5px solid #b27116}}.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:14px;background:white}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #d1dce1}}th{{background:#dde9ee}}img{{width:100%;height:auto}}code{{overflow-wrap:anywhere}}p,li{{max-width:1000px}}nav{{display:flex;gap:20px;flex-wrap:wrap}}small,figcaption{{color:#4a6573}}figure{{margin:24px 0}}details{{margin:20px 0}}summary{{cursor:pointer;font-weight:700}}</style></head><body><main>
<p>22 September 2026 · 37 official Kromp test images · three fresh repeats</p>
<h1>StarDist was running correctly.<br>Our scoring and scale assumptions needed correction.</h1>
<div class="notice"><b>This audit supersedes the original count and segmentation scores.</b> Original predictions, traces and protocol remain unchanged. The revised reference applies to every arm. Scale variants are post-hoc diagnostics, not a new held-out result or an improved harness score.</div>
<nav><a href="#checks">Integration checks</a><a href="#reference">Reference repair</a><a href="#results">Results</a><a href="#visuals">Visual evidence</a><a href="#images">Every image</a></nav>
<h2 id="checks">What we checked</h2>
<ul><li>Official model archive SHA256, pinned weights, configuration and thresholds all match. The original TIFF pixels exactly equal every channel of the PNG supplied to the worker, for all 37 images.</li>
<li>{data['native_fresh_inferences']} fresh native StarDist executions: original-size default/sensitive/conservative, half-size default and quarter-size default; three complete repetitions each. No reference labels were read by inference, and no Astra/Jev API calls were made in this audit.</li>
<li><b>{data['pixel_identical_native_vs_worker']}/{data['native_comparisons']} native unscaled masks exactly match the saved worker masks, pixel for pixel.</b> There is no evidence of a model-loading, channel-conversion or worker-inference defect in those checks.</li>
<li>StarDist's own instance matcher reproduces all {data['official_matching_checks']} previous TP/FP/FN calculations using the original labels. That verifies the matching implementation, not the validity of those labels.</li>
<li>All five native variants produce identical masks across their three repeats on all 37 images. This establishes repeatability here; it does not establish accuracy or general determinism across hardware/software.</li></ul>
<h2 id="reference">The actual scoring bug: 55 IDs represented 102 nuclei</h2>
<p>In <code>otherspecimen_3.tif</code>, 47 of 55 positive IDs each label two disconnected regions. The TIFF has 102 per-ID connected regions, with no tiny fragments. We previously equated unique IDs with nuclei. Repeating that assumption through a second TIFF reader did not validate it.</p>
<p>The <a href="https://www.nature.com/articles/s41597-020-00608-w">dataset paper</a> reports 102 nuclei for the sole Wilms image. The <a href="otherspecimen_3.svg">published SVG</a> contains 110 elements: six duplicate contours reduce this to 104 distinct shapes; 102 map one-to-one onto the TIFF regions, while two additional SVG contours are absent from the TIFF. We use the released TIFF's 102 regions, supported by this correspondence and the paper. The corrected instance map preserves every foreground pixel.</p>
<p>StarDist's prediction of 111 on this image therefore has <b>8.82% count error, not 101.82%</b>. This is a reference repair, not an inference improvement. We also report a 36-image analysis excluding this field and a 104-count SVG sensitivity analysis below.</p>
<p>We audited all 37 masks. One other mask, <code>Ganglioneuroblastoma_8.tif</code>, has two fragments smaller than five pixels belonging to an existing instance; its 183-ID count is preserved. Splitting every disconnected region blindly would introduce another error. <a href="svg-component-correspondence.json">Vector correspondence</a> · <a href="label-connectivity-audit.json">Original connectivity audit</a>.</p>
<h2 id="results">Corrected results: same 37 images, same saved predictions</h2>
<p>Mean count error is MAPE: calculate absolute percentage error per image/attempt, then average. For arms with missing answers it is conditional on returned counts. “Within 10%” uses all scheduled attempts and counts missing answers as failures. Segmentation F1 measures one-to-one object matches at mask overlap IoU ≥ 0.5; higher is better. No LLM segmentation score is invented.</p>
{table('repaired_37')}
<p><b>Scale matters, but routing is still unproven.</b> Half-size input improves default StarDist's mean count error from 23.29% to 10.57%. The original full v1 harness scores 65/111 within 10% (58.6%), not the previously quoted 62/111 (55.9%). Vanilla remains 78/111 (70.3%). These scale variants were not available to the original router. The new v2 router has not been evaluated on a new cohort.</p>
<p>Three repeats do not create 111 independent images. Fixed-model masks and errors are identical across repetitions. <a href="three-run-averages.md">All three run averages and SD</a> · <a href="corrected-results.json">Complete corrected metrics, image-cluster intervals and records</a>.</p>
<details><summary>Sensitivity: exclude the repaired image (36 images × three repeats)</summary>{table('exclude_ambiguous_36')}</details>
<details><summary>Sensitivity: use all 104 distinct SVG contours as the disputed count</summary><p>This does not change the other 36 references. Only count metrics are presented because the two additional vector shapes are absent from the released TIFF.</p>{table('svg_104_count_sensitivity_37')}</details>
<h2 id="visuals">See where scale helps—and where it hurts</h2>
<p>Green boundaries show the reference or predicted instances. The same complete image is shown in each row. Half-size inference maps predictions back to original coordinates. These three illustrative fields were chosen after scoring; the complete cohort is listed below.</p>
<figure><a href="scale-comparison.png"><img src="scale-comparison.png" alt="Reference versus original-size and half-size StarDist. Large nuclei improve, the dense 969-nucleus field loses small objects, and the repaired reference has 102 nuclei."></a><figcaption>Open the figure for a larger view. Count agreement alone can hide segmentation mistakes.</figcaption></figure>
<p>The <a href="https://stardist.net/faq/#do-i-need-to-rescale-my-images-how-do-i-know-which-pixel-resolution-is-required">StarDist authors recommend checking image scale</a> when large nuclei are split. Our original candidates varied only the detection threshold and all used the original size. That omitted a meaningful condition of use. Uniform quarter-size input is worse overall than half-size input; the correct policy cannot simply be “always shrink more.”</p>
<h2 id="images">All 37 images, including failures</h2><p>The three StarDist counts shown are identical in all three fresh repeats. Vanilla and full v1 show each saved repetition separately.</p>{per_image}
<h2>What changes next</h2><p>Keep the original experiment frozen. Use reviewed references, add scale as an explicit specialist parameter, and select or calibrate scale on separate development images. Then freeze that policy and compare vanilla, the fixed specialist and the complete router on new test images over multiple runs. Do not choose a per-image winner using reference counts or present this post-hoc half-size result as held-out validation.</p>
<h2>Audit files and reproduction</h2><ul><li><a href="protocol.json">Native inference protocol and package versions</a> · <a href="input-audit.json">Pixel/normalization audit</a> · <a href="native-results.json">All 555 fresh inferences</a></li><li><a href="independent-matching.json">Independent matching checks</a> · <a href="svg-audit.json">SVG duplicate analysis</a> · <a href="corrected-results.json">Corrected outcomes</a></li><li><a href="../../experiments/stardist_audit/README.md">Scripts and reproduction commands</a> · <a href="../kromp-repeated-20260922/index.html">Preserved original report (superseded scores)</a></li></ul>
<p><small>No new hosted inference was requested. Source TIFFs, original result JSON and saved predictions are unchanged. No repository was pushed or published.</small></p>
</main></body></html>"""
    (REPORT / "index.html").write_text(content)


if __name__ == "__main__":
    main()
