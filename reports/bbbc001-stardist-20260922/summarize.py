"""Render primary, recovered and diagnostic results without making model calls."""

import html
import json
import os
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from evals.scoring import score

ROOT = Path("reports/bbbc001-stardist-20260922")


def read(path):
    return json.loads(path.read_text())


def pct(value):
    return "Incomplete" if value is None else f"{value:.2f}%"


def main():
    report = read(ROOT / "results.json")
    candidates = read(ROOT / "candidate-counts.json")
    cohort = report["cohort"]
    trials = {(t["task_id"], t["mode"]): t for t in report["trials"]}
    summaries = {s["mode"]: s for s in report["summary"]}
    recovery = []
    for path in Path("jobs/bbbc001-stardist-recovery-20260922").glob("*/*/result.json"):
        result = read(path)
        directory = path.parent / "agent/run"
        task = next(t for t in cohort if t["id"] == result["task_name"])
        answer = read(directory / "answer.json")
        metrics = score(answer, task)
        rewards = (result.get("verifier_result") or {}).get("rewards")
        if rewards is not None:
            assert rewards == metrics
        recovery.append(
            {
                "task_id": task["id"],
                "answer": answer,
                "metrics": metrics,
                "manifest": read(directory / "manifest.json"),
                "infrastructure_error": result.get("exception_info"),
                "events": os.path.relpath(directory / "events.jsonl", ROOT),
                "trajectory": os.path.relpath(path.parent / "agent/trajectory.json", ROOT),
            }
        )
    assert len(recovery) == 1
    recovered_by_id = {r["task_id"]: r for r in recovery}
    rows = []
    for task, candidate in zip(cohort, candidates["rows"], strict=True):
        vanilla = trials[task["id"], "vanilla"]
        tools = trials[task["id"], "tools"]
        recovered = recovered_by_id.get(task["id"])
        chosen = recovered if recovered is not None else vanilla
        numerical = candidate["numerical_candidates"]
        rows.append(
            {
                "task_id": task["id"],
                "image": task["title"],
                "reference": task["expected"],
                "human_counts": task["human_counts"],
                "primary_vanilla_count": vanilla["answer"].get("value"),
                "composite_vanilla_count": chosen["answer"].get("value"),
                "composite_vanilla_error": chosen["metrics"].get("percentage_error"),
                "uses_recovery": recovered is not None,
                "stardist_count": tools["answer"]["value"],
                "stardist_error": tools["metrics"]["percentage_error"],
                "full_first_candidate": numerical[0]["count"],
                "full_last_candidate": numerical[-1]["count"],
                "full_final_status": candidate["actual_final_answer"]["status"],
                "review": numerical[0]["review"],
            }
        )
    complete = all(r["composite_vanilla_error"] is not None for r in rows)
    baseline = statistics.mean(r["composite_vanilla_error"] for r in rows) if complete else None
    tool_error = summaries["tools"]["benchmark_percentage_error"]
    paired = [r for r in rows if r["composite_vanilla_error"] is not None]
    comparison = {
        "label": "Recovered/composite vanilla: five primary answers plus one separately retried timeout",
        "coverage": len(paired),
        "total": len(rows),
        "percentage_error": baseline,
        "stardist_error": tool_error,
        "closer_images": sum(r["stardist_error"] < r["composite_vanilla_error"] for r in paired),
        "worse_images": sum(r["stardist_error"] > r["composite_vanilla_error"] for r in paired),
        "relative_error_reduction_percent": 100 * (baseline - tool_error) / baseline
        if baseline
        else None,
    }
    final = {
        "experiment": report["protocol"]["name"],
        "primary_summary": report["summary"],
        "recovered_comparison": comparison,
        "recovery_trials": recovery,
        "rows": rows,
        "candidate_summary": candidates["summary"],
        "standalone_error": report["protocol"]["standalone_baseline"]["count_error_percentage"],
        "conclusion": "StarDist improves measured counts on this cohort. Astra + StarDist matches the standalone counts; full-chain Jev review rejects all six. No accepted-output improvement from the full chain is established.",
    }
    (ROOT / "final-score.json").write_text(json.dumps(final, indent=2) + "\n")
    lines = [
        "# StarDist inside the complete harness",
        "",
        final["conclusion"],
        "",
        "Mean absolute percentage count error against the mean of two published human counts; lower is better. Six real BBBC001 images, not invented problems. Coverage counts returned estimates, not exact answers.",
        "",
        "| Primary experiment | Final counts | Full-cohort error | Abstentions | Execution errors | Mean time |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for mode in report["protocol"]["modes"]:
        s = summaries[mode]
        lines.append(
            f"| {report['protocol']['mode_labels'][mode]} | {s['coverage']}/6 | {pct(s['benchmark_percentage_error'])} | {s['abstentions']} | {s['errors']} | {s['mean_seconds']:.1f} s |"
        )
    lines += [
        "",
        "Vanilla's primary answered-subset error is 17.64% on five images; it is not a full-cohort score. Its sixth request timed out at 120 seconds. This is an Astra execution error, not a Jev rejection.",
        "",
        "## Separately recorded timeout recovery",
        "",
        f"{comparison['label']}: **{len(paired)}/6 counts, {pct(baseline)} error**. The retry uses a 300-second per-call timeout; other inference settings and all input/source files are unchanged. The primary timeout remains in its original trial. See [policy](recovery-policy.json), [retry config](recovery-evaluation.toml) and [exact results](final-score.json).",
        "",
    ]
    if complete:
        lines += [
            f"Astra + StarDist has {comparison['relative_error_reduction_percent']:.1f}% lower error than this recovered/composite baseline, and is closer on {comparison['closer_images']} of six images. This comparison includes a recovery attempt and must not be presented as six successful first attempts.",
            "",
        ]
    lines += [
        "## Every count",
        "",
        "| Image | Humans | Reference | Primary vanilla | Vanilla incl. recovery | StarDist / Astra + StarDist | Full-chain first / last numerical candidate | Full final |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        primary = (
            r["primary_vanilla_count"] if r["primary_vanilla_count"] is not None else "Timeout"
        )
        composite = str(r["composite_vanilla_count"]) + (" (retry)" if r["uses_recovery"] else "")
        lines.append(
            f"| {r['image']} | {r['human_counts']} | {r['reference']} | {primary} | {composite} | {r['stardist_count']:g} | {r['full_first_candidate']:g} / {r['full_last_candidate']:g} | {r['full_final_status']} |"
        )
    lines += [
        "",
        "## Why full mode still abstains",
        "",
        "All six first and last numerical candidates have 6.67% mean error, identical to standalone StarDist and the tools-only arm. These are diagnostic proposals, not accepted outputs. Replanning produced no revised numerical estimate.",
        "",
        "Jev's overall answer-support scores were 0.80–0.87. Method-validity checks scored 0.19–0.32 and target-validity checks 0.33–0.46. Every requirement must reach 0.75; therefore all six candidates failed review. Overall support is not the acceptance rule and none of these scores is calibrated count accuracy.",
        "",
        "All six trials passed failed checks back into Astra planning and Jev selection. Five trials then returned an Astra abstention after additional auditing; one stopped because Jev selected no eligible new plan. No full-mode request timed out. Five cropped StarDist maps were added across four trials; additional views did not establish independent biological validation. The available specialist and crops cannot guarantee one instance per true cell.",
        "",
        "This points to a mismatch between an estimated-count task and a policy requiring independent validation before returning any estimate. It does not establish that Jev as a model is inherently harmful. A future policy experiment should distinguish 'measured estimate with unresolved caveats' from 'verified count', and calibrate acceptance on held-out data. Do not tune this run's threshold after looking at its answers.",
        "",
        "## What improved and what did not",
        "",
        "The perception layer now returns real nucleus instance masks and derives counts from distinct positive IDs. This is a substantive improvement over the previous OpenCV run's unusable whole-image components and visual fallback. The previous OpenCV scores are historical, not fresh paired controls: 16.16% tools-only and 14.27% selection-only, versus this run's 6.67% StarDist tools-only result.",
        "",
        "The harness did not improve on standalone StarDist's 6.67% error. It added orchestration, evidence provenance and inspectable traces. Its full review policy reduced final-answer coverage to zero. The next useful evaluation is on new annotated images with a predeclared policy and specialist selection; repeated measurements on these six development images cannot establish generalization.",
        "",
        "## Review files and limits",
        "",
        "- [Interactive report](index.html): primary outcomes, recovery summary, images and traces.",
        "- [Candidate counts](candidate-counts.md): proposals before review, without substituting them for final answers.",
        "- [Verification](verification.json): trajectory, source, input, checkpoint, geometry, feedback and credential checks.",
        "- [Preflight](preflight-verification.json): 42 tests plus exact native/container mask agreement for all six defaults.",
        "- [Integration file map](../../docs/stardist-harness.md): what each adapter/configuration file does.",
        "- [Frozen protocol](protocol.json): all settings, hashes, attribution and limitations.",
        "",
        "Six previously inspected images, one primary attempt per mode, uncertain pretraining overlap, disagreeing human annotations, and no instance-level ground truth limit conclusions. All three modes share the frozen Astra system instructions, including StarDist guidance. Vanilla receives only the original image and an empty evidence list; it has no specialist or Jev calls. This is an API ablation under the common harness prompt, not a measurement of the default ChatGPT product. Threshold variants are correlated predictions from one model. Runtime excludes container setup; token usage for the timed-out request is unknown. Local masks and Harbor jobs are retained on this machine; raw job traces are Git-ignored.",
        "",
        "Reproduce report-only calculations from the repository root:",
        "",
        "```bash",
        ".venv/bin/python -m evals.benchmark_report reports/bbbc001-stardist-20260922 jobs/bbbc001-stardist-20260922",
        ".venv/bin/python -m evals.candidate_report reports/bbbc001-stardist-20260922",
        ".venv/bin/python reports/bbbc001-stardist-20260922/summarize.py",
        ".venv/bin/python reports/bbbc001-stardist-20260922/audit.py",
        "```",
        "",
    ]
    (ROOT / "final-score.md").write_text("\n".join(lines))
    (ROOT / "findings.md").write_text("\n".join(lines))
    view = ROOT / "index.html"
    document = view.read_text()
    document = re.sub(
        r"<!-- stardist-summary:start -->.*?<!-- stardist-summary:end -->", "", document, flags=re.S
    )
    chart_rows = [("Standalone StarDist", tool_error), ("Astra + StarDist", tool_error)]
    if baseline is not None:
        chart_rows.insert(0, ("Vanilla (recovered/composite)", baseline))
    bars = "".join(
        f"<p><strong>{html.escape(label)}: {value:.2f}%</strong><span style='display:block;height:14px;border-radius:4px;background:#3b6cc5;width:{min(value * 4, 100):.2f}%'></span></p>"
        for label, value in chart_rows
    )
    review_rows = "".join(
        f"<tr><td>{r['image']}</td><td>{r['review']['support_probability']:.2f}</td>"
        + "".join(f"<td>{c['support_probability']:.2f}</td>" for c in r["review"]["checks"])
        + "<td>Rejected</td></tr>"
        for r in rows
    )
    gallery = "".join(
        f"<details><summary>{r['image']}: {r['stardist_count']:g} predicted nuclei</summary>"
        f"<div class='task segmentation-gallery'><figure style='margin:0'><img src='standalone-container/{r['task_id']}/artifacts/original.png' alt='{r['image']} original fluorescence image'><figcaption>Original</figcaption></figure>"
        f"<figure style='margin:0'><img src='standalone-container/{r['task_id']}/artifacts/default-overlay.png' alt='{r['image']} StarDist instance overlay'><figcaption>Colored predicted instances; colors do not indicate confidence.</figcaption></figure></div>"
        f"<p><a href='standalone-container/{r['task_id']}/evidence/default-labels.npz'>Raw instance labels</a> · <a href='standalone-container/{r['task_id']}/evidence/default-instances.json'>Per-instance geometry</a></p></details>"
        for r in rows
    )
    note = f"""<!-- stardist-summary:start --><section id='final-comparison'><style>.segmentation-gallery{{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}}@media(max-width:740px){{.segmentation-gallery{{grid-template-columns:1fr}}}}</style><h2>What changed with StarDist?</h2>
<p><strong>Measured counts improved. The complete review chain still returned no accepted counts.</strong> Astra + StarDist returned all six default specialist counts: 6.67% mean error. Standalone StarDist gets the same result, so orchestration did not improve its count accuracy.</p>
<h3>Count comparison — lower is better</h3>{bars}
<p>The vanilla line is explicitly <strong>recovered/composite</strong>: five primary answers plus one separately retried timeout. The primary experiment below retains its original 5/6 coverage. Recovery used a 300-second timeout; no rejected answers were retried.</p>
<p>Full-chain first/last numerical candidates: <strong>6/6 at 6.67% error</strong>. Full-chain final accepted answers: <strong>0/6</strong>, six abstentions, zero execution errors. Candidate accuracy is diagnostic and does not replace final-output scoring.</p>
<h3>Why high overall support did not approve an answer</h3><p>Every column must reach 0.75. Method and target checks failed on all images. These scores are not calibrated probabilities of count accuracy.</p>
<div class='scroll'><table><thead><tr><th>Image</th><th>Overall</th><th>Method</th><th>Coverage</th><th>Target</th><th>Grounding</th><th>Decision</th></tr></thead><tbody>{review_rows}</tbody></table></div>
<p>Feedback reached both planning and selection on all six trials. More crops and repeated segmentation did not supply the independent validation demanded by this policy. The acceptance threshold was unchanged throughout.</p>
<h3>Inspect the default segmentation</h3><p>These frozen container controls reproduce standalone StarDist's masks exactly. All tools-only final counts and full-chain first candidates matched these counts. Expand an image to compare the original with predicted instances.</p>{gallery}
<p><a href='final-score.md'>Complete interpretation and per-image counts</a> · <a href='final-score.json'>Machine-readable final comparison and recovery</a> · <a href='verification.json'>Verification</a> · <a href='../../docs/stardist-harness.md'>Integration file map</a></p></section><!-- stardist-summary:end -->"""
    document = document.replace("<section>", note + "<section>", 1)
    view.write_text(document)
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
