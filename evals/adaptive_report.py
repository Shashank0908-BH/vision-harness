"""Report adaptive specialist experiments from frozen outputs; makes no model calls.

Usage: python -m evals.adaptive_report REPORT_DIRECTORY JOBS_DIRECTORY
"""

import html
import json
import os
import shutil
import statistics
import sys
from pathlib import Path

from vision_harness.tracing import write_json

from .benchmark_report import summarize
from .scoring import score


def read(path):
    return json.loads(path.read_text())


def metrics_summary(rows, total):
    valid = [r for r in rows if r["metrics"].get("valid_prediction")]
    values = [r["metrics"]["percentage_error"] for r in valid]
    return {
        "coverage": len(valid),
        "total": total,
        "mean_percentage_error": statistics.mean(values) if len(valid) == total else None,
        "answered_subset_percentage_error": statistics.mean(values) if values else None,
    }


def source_measurements(answer, evidence):
    return [
        {
            "evidence_id": e["evidence_id"],
            "profile": e["parameters"]["segmentation_profile"],
            "count": e["measurements"]["instance_count"],
            "full_original_coverage": e["measurements"]["full_original_coverage"],
        }
        for e in evidence
        if e["tool"] == "stardist" and e["evidence_id"] in answer.get("evidence_ids", [])
    ]


def collect(root, jobs):
    protocol, cohort = read(root / "protocol.json"), read(root / "cohort.json")
    by_id = {r["id"]: r for r in cohort}
    controls = read(root / "standalone/results.json")
    assert {r["id"] for r in controls} == set(by_id) and len(controls) == len(cohort)
    control_by_id = {}
    for row in controls:
        assert row["input_sha256"] == by_id[row["id"]]["sha256"]
        row["metrics"] = score({"status": row["status"], "value": row["count"]}, by_id[row["id"]])
        control_by_id[row["id"]] = row
    trials = {}
    for path in sorted(jobs.glob("*/*/result.json")):
        result = read(path)
        tid = result["task_name"]
        assert tid in by_id
        directory = path.parent / "agent/run"
        manifest = read(directory / "manifest.json")
        mode = manifest["mode"]
        assert mode in protocol["modes"] and (tid, mode) not in trials
        assert manifest["input_sha256"] == by_id[tid]["sha256"] and not manifest["offline"]
        assert manifest["config"] == protocol["effective_settings"]
        answer = read(directory / "answer.json")
        metrics = score(answer, by_id[tid])
        rewards = (result.get("verifier_result") or {}).get("rewards")
        if rewards is not None:
            assert rewards == metrics, path
        events = [
            json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()
        ]
        evidence = [e["data"] for e in events if e["kind"] == "evidence"]
        tokens = {p: dict(input=0, output=0, started_calls=0, calls=0) for p in ("astra", "jev")}
        providers, candidates, round_id = {}, [], 0
        for event in events:
            d = event["data"]
            if event["kind"] == "call_started":
                providers[d["call_id"]] = d["provider"]
                tokens[d["provider"]]["started_calls"] += 1
            elif event["kind"] == "call_finished":
                usage = d.get("usage") or {}
                p = tokens[providers[d["call_id"]]]
                p["calls"] += 1
                p["input"] += usage.get("input_tokens", 0)
                p["output"] += usage.get("output_tokens", 0)
            elif event["kind"] == "plans":
                round_id += 1
            elif event["kind"] == "candidate_answer":
                cm = score(d, by_id[tid])
                if cm["valid_prediction"]:
                    candidates.append(
                        {
                            "round": round_id,
                            "sequence": event["sequence"],
                            "answer": d,
                            "metrics": cm,
                            "sources": source_measurements(d, evidence),
                        }
                    )
            elif event["kind"] == "answer_review" and candidates:
                assert "review" not in candidates[-1]
                candidates[-1]["review"] = d
        trial = {
            "task_id": tid,
            "mode": mode,
            "answer": answer,
            "metrics": metrics,
            "harbor_rewards": rewards,
            "infrastructure_error": result.get("exception_info"),
            "elapsed_seconds": manifest.get("elapsed_seconds"),
            "tokens": tokens,
            "final_sources": source_measurements(answer, evidence),
            "numerical_candidates": candidates,
            "planning_rounds": round_id,
            "evidence": evidence,
            "decisions": [
                e
                for e in events
                if e["kind"]
                in {
                    "plans",
                    "selection",
                    "assessments",
                    "candidate_answer",
                    "answer_review",
                    "review_feedback",
                    "loop_stopped",
                    "error",
                    "format_retry",
                    "tool_reused",
                }
            ],
            "trace": os.path.relpath(path.parent / "agent/trajectory.json", root),
            "events": os.path.relpath(directory / "events.jsonl", root),
            "artifact_directory": os.path.relpath(directory / "artifacts", root),
        }
        # Persist the last numerical full-chain measurement overlay for visual review,
        # even if final review rejected the answer; clearly label it a proposal.
        selected_answer = candidates[-1]["answer"] if mode == "full" and candidates else answer
        cited = source_measurements(selected_answer, evidence)
        match = next(
            (
                s
                for s in cited
                if s["count"] == selected_answer.get("value") and s["full_original_coverage"]
            ),
            None,
        )
        if match:
            source = directory / "artifacts" / (match["evidence_id"] + "-overlay.png")
            target = root / "overlays" / f"{tid}-{mode}.png"
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(source, target)
            trial["selected_overlay"] = str(target.relative_to(root))
        trials[tid, mode] = trial
    missing = [
        (t["id"], m) for t in cohort for m in protocol["modes"] if (t["id"], m) not in trials
    ]
    if missing:
        raise ValueError(f"Primary experiment incomplete: {missing}")
    summaries = [summarize([trials[t["id"], mode] for t in cohort]) for mode in protocol["modes"]]
    comparisons = []
    for mode in protocol["modes"]:
        available = [
            trials[t["id"], mode]
            for t in cohort
            if trials[t["id"], mode]["metrics"]["valid_prediction"]
            and not trials[t["id"], mode]["infrastructure_error"]
        ]
        differences = [
            t["metrics"]["percentage_error"]
            - control_by_id[t["task_id"]]["metrics"]["percentage_error"]
            for t in available
        ]
        comparisons.append(
            {
                "mode": mode,
                "matched_images": len(available),
                "total": len(cohort),
                "mean_error_change_percentage_points": statistics.mean(differences)
                if len(available) == len(cohort)
                else None,
                "matched_subset_error_change": statistics.mean(differences)
                if differences
                else None,
                "closer_than_fixed": sum(d < 0 for d in differences),
                "worse_than_fixed": sum(d > 0 for d in differences),
                "tied_with_fixed": sum(d == 0 for d in differences),
                "different_counts": sum(
                    t["answer"]["value"] != control_by_id[t["task_id"]]["count"] for t in available
                ),
            }
        )
    proposals = []
    for index, name in ((0, "first numerical candidate"), (-1, "last numerical candidate")):
        rows = [
            dict(trials[t["id"], "full"]["numerical_candidates"][index], task_id=t["id"])
            for t in cohort
            if trials[t["id"], "full"]["numerical_candidates"]
        ]
        proposals.append({"policy": name, **metrics_summary(rows, len(cohort)), "rows": rows})
    return {
        "protocol": protocol,
        "cohort": cohort,
        "standalone": controls,
        "standalone_summary": metrics_summary(controls, len(cohort)),
        "summary": summaries,
        "paired_comparisons": comparisons,
        "candidate_summary": proposals,
        "trials": list(trials.values()),
        "fixed_sensitive_diagnostic": read(root / "fixed-sensitive-diagnostic.json")
        if (root / "fixed-sensitive-diagnostic.json").exists()
        else None,
    }


def pct(value):
    return "Incomplete" if value is None else f"{value:.2f}%"


def render(root, jobs):
    result = collect(root, jobs)
    write_json(root / "results.json", result)
    protocol, cohort = result["protocol"], result["cohort"]
    labels = protocol["mode_labels"]
    total = len(cohort)
    control = {r["id"]: r for r in result["standalone"]}
    trials = {(t["task_id"], t["mode"]): t for t in result["trials"]}
    esc = lambda v: html.escape(str(v))  # noqa: E731
    base = result["standalone_summary"]
    lines = [
        "# Adaptive StarDist and Jev condition review",
        "",
        "New project cohort: six preselected images from the official BBBC039 test split. This is a derived nucleus-count task, not the published instance-segmentation benchmark metric. Lower count error is better; coverage is not exact-match accuracy.",
        "",
        "| Configuration | Final counts | Full-cohort error | Answered-subset error | Abstained | Errors | Mean time |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| Fixed default StarDist | {base['coverage']}/{total} | {pct(base['mean_percentage_error'])} | {pct(base['answered_subset_percentage_error'])} | 0 | 0 | {statistics.mean(r['elapsed_seconds'] for r in result['standalone']):.1f} s |",
    ]
    table = [
        [
            "Fixed default StarDist",
            f"{base['coverage']}/{total}",
            pct(base["mean_percentage_error"]),
            pct(base["answered_subset_percentage_error"]),
            0,
            0,
            f"{statistics.mean(r['elapsed_seconds'] for r in result['standalone']):.1f} s",
        ]
    ]
    for s in result["summary"]:
        values = [
            labels[s["mode"]],
            f"{s['coverage']}/{total}",
            pct(s["benchmark_percentage_error"]),
            pct(s["answered_subset_percentage_error"]),
            s["abstentions"],
            s["errors"],
            f"{s['mean_seconds']:.1f} s",
        ]
        table.append(values)
        lines.append("| " + " | ".join(map(str, values)) + " |")
    diagnostic_note = ""
    if result["fixed_sensitive_diagnostic"]:
        diagnostic = result["fixed_sensitive_diagnostic"]
        diagnostic_note = (
            f"Using the sensitive profile uniformly on all six images yields {pct(diagnostic['mean_percentage_error'])} mean error. "
            "This is a post-hoc calculation from measurements already saved in the selection arm, "
            "not a preregistered arm or a new inference run. It applies one fixed rule to every image, "
            "without choosing the best profile separately for each annotation. "
            "Compare adaptive choices with this simpler explanation before attributing a gain to orchestration."
        )
        lines += [
            "",
            "## Post-hoc fixed-profile diagnostic",
            "",
            diagnostic_note,
            "",
            "[Exact diagnostic and source traces](fixed-sensitive-diagnostic.json) · [When and why it was added](fixed-profile-diagnostic-policy.json)",
        ]
    lines += [
        "",
        "Incomplete arms have no full-cohort error. Subset errors use only answered images and cannot establish a win over complete arms. Runtime excludes container setup; standalone includes adapter execution and its first model load. Interrupted request usage may be unknown.",
        "",
        "## Did orchestration improve fixed StarDist?",
        "",
        "| Arm | Matched images | Different counts | Closer | Worse | Tied | Full-cohort error change (negative helps) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for c in result["paired_comparisons"]:
        change = c["mean_error_change_percentage_points"]
        lines.append(
            f"| {labels[c['mode']]} | {c['matched_images']}/{total} | {c['different_counts']} | {c['closer_than_fixed']} | {c['worse_than_fixed']} | {c['tied_with_fixed']} | {change:+.2f} pp |"
            if change is not None
            else f"| {labels[c['mode']]} | {c['matched_images']}/{total} | {c['different_counts']} | {c['closer_than_fixed']} | {c['worse_than_fixed']} | {c['tied_with_fixed']} | Incomplete |"
        )
    lines += [
        "",
        "## Counts on each image",
        "",
        "| Image | Annotation count | Fixed StarDist | "
        + " | ".join(labels[m] for m in protocol["modes"])
        + " |",
        "|---|---:|---:|" + "---:|" * len(protocol["modes"]),
    ]
    for task in cohort:
        values = [task["title"], task["expected"], control[task["id"]]["count"]]
        for mode in protocol["modes"]:
            a = trials[task["id"], mode]["answer"]
            values.append(a["value"] if a["status"] == "answered" else a["status"])
        lines.append("| " + " | ".join(map(str, values)) + " |")
    lines += ["", "## Full-chain proposals, before acceptance", ""]
    for s in result["candidate_summary"]:
        lines.append(
            f"- {s['policy']}: {s['coverage']}/{total}, {pct(s['mean_percentage_error'])} full-cohort error; {pct(s['answered_subset_percentage_error'])} answered-subset error."
        )
    lines += [
        "",
        "First/last policies are fixed and include rejected proposals. No best-of-N selection; these do not replace accepted-output scores.",
        "",
        "## Method and limits",
        "",
        *["- " + item for item in protocol["limitations"]],
        "",
        f"{protocol['attribution']}. [{protocol['license']}]({protocol['license_url']}). [Dataset and annotation documentation]({protocol['source_page']}).",
        "",
        "[Visual report](index.html) · [Frozen protocol](protocol.json) · [All results and trace links](results.json) · [Implementation file map](../../docs/adaptive-stardist.md)",
    ]
    (root / "final-score.md").write_text("\n".join(lines) + "\n")
    cards = []
    for task in cohort:
        tid = task["id"]
        disclosures = []
        for mode in protocol["modes"]:
            trial = trials[tid, mode]
            a = trial["answer"]
            value = a.get("value") if a["status"] == "answered" else a["status"]
            detail = {
                k: trial[k]
                for k in (
                    "final_sources",
                    "numerical_candidates",
                    "decisions",
                    "tokens",
                    "infrastructure_error",
                )
            }
            disclosures.append(
                f"<details><summary>{esc(labels[mode])}: {esc(value)} · {pct(trial['metrics'].get('percentage_error'))}</summary><p>{esc(a['explanation'])}</p><p>Limitations: {esc('; '.join(a.get('limitations', [])))}</p><p><a href='{esc(trial['trace'])}'>Harbor trajectory</a> · <a href='{esc(trial['events'])}'>Events</a> · <a href='{esc(trial['artifact_directory'])}'>All tool artifacts</a></p><pre>{esc(json.dumps(detail, indent=2))}</pre></details>"
            )
        gallery = f"<figure><img src='standalone/{tid}/artifacts/original.png' alt='{esc(task['title'])}: original'><figcaption>Original · <a href='annotations/{tid}.npz'>annotation count {task['expected']}</a></figcaption></figure><figure><img src='standalone/{tid}/artifacts/default-overlay.png' alt='Fixed StarDist instances'><figcaption>Fixed default · {control[tid]['count']} nuclei</figcaption></figure>"
        full = trials[tid, "full"]
        if full.get("selected_overlay"):
            gallery += f"<figure><img src='{esc(full['selected_overlay'])}' alt='Full-chain last numerical proposal segmentation'><figcaption>Full-chain last numerical proposal · {full['numerical_candidates'][-1]['answer']['value']:g} nuclei · final status {esc(full['answer']['status'])}</figcaption></figure>"
        review_rows = []
        for candidate in full["numerical_candidates"]:
            review = candidate.get("review", {})
            checks = {c["check_id"]: c["support_probability"] for c in review.get("checks", [])}
            probability = review.get("support_probability")
            values = [
                probability,
                *[
                    checks.get(k)
                    for k in (
                        "input_suitability",
                        "parameter_justification",
                        "coverage",
                        "count_grounding",
                    )
                ],
            ]
            decision = (
                "Unreviewed"
                if any(v is None for v in values)
                else "Accepted"
                if all(v >= 0.75 for v in values)
                else "Rejected"
            )
            profiles = (
                ", ".join(
                    s["profile"]
                    for s in candidate["sources"]
                    if s["count"] == candidate["answer"]["value"] and s["full_original_coverage"]
                )
                or "See derivation"
            )
            cells = [
                candidate["round"],
                candidate["answer"]["value"],
                profiles,
                *["—" if v is None else f"{v:.2f}" for v in values],
                decision,
            ]
            review_rows.append("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in cells) + "</tr>")
        rounds = (
            "<h3>Full-chain proposals and condition scores</h3><div class='scroll'><table><thead><tr><th>Round</th><th>Count</th><th>Profile backing count</th><th>Overall</th><th>Input</th><th>Parameters</th><th>Coverage</th><th>Grounding</th><th>Review</th></tr></thead><tbody>"
            + "".join(review_rows)
            + "</tbody></table></div><p>Each score must reach 0.75. Scores indicate Jev's assessment of the supplied evidence, not calibrated count accuracy.</p>"
        )
        cards.append(
            f"<section><h2>{esc(task['title'])}</h2><p>{esc(task['question'])}</p><div class='gallery'>{gallery}</div>{rounds}{''.join(disclosures)}</section>"
        )
    html_rows = "".join(
        "<tr>" + "".join(f"<td>{esc(v)}</td>" for v in row) + "</tr>" for row in table
    )
    paired_rows = "".join(
        f"<tr><td>{esc(labels[c['mode']])}</td><td>{c['matched_images']}/{total}</td><td>{c['different_counts']}</td><td>{c['closer_than_fixed']}</td><td>{c['worse_than_fixed']}</td><td>{c['tied_with_fixed']}</td></tr>"
        for c in result["paired_comparisons"]
    )
    css = "body{margin:0;background:#f3f5f8;color:#17243a;font:16px/1.6 system-ui}main{max-width:1240px;margin:auto;padding:24px}h1{font-size:clamp(28px,5vw,44px);line-height:1.2}section{background:white;border:1px solid #dce3ed;border-radius:12px;padding:24px;margin:22px 0}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:10px;text-align:left;border-bottom:1px solid #dce3ed;white-space:nowrap}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}figure{margin:0;min-width:0}img{width:100%;height:auto}details{border-top:1px solid #dce3ed;padding:12px 0}summary{cursor:pointer;font-weight:600}pre{font:12px/1.5 monospace;white-space:pre-wrap;overflow-wrap:anywhere;max-height:400px;overflow:auto;background:#f3f5f8;padding:12px}a{color:#2459a9}p,li{overflow-wrap:anywhere}@media(max-width:740px){main{padding:12px}section{padding:16px}.gallery{grid-template-columns:1fr}}"
    document = f"<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Adaptive StarDist · BBBC039</title><style>{css}</style><main><p>ASTRA · STARDIST · JEV · HARBOR</p><h1>Can choosing how to use a specialist improve its result?</h1><section><h2>Six new images. Frozen choices. Every outcome retained.</h2><p>Astra chooses a whole-image profile or crop audit without a default-first instruction. Jev checks input suitability, parameter justification, coverage and grounded count derivation. All review requirements retain the 0.75 threshold. This assesses support for an estimate, not independently validated biological truth.</p><p><a href='findings.md'>Findings and interpretation</a> · <a href='final-score.md'>Count table</a> · <a href='protocol.json'>Frozen protocol</a> · <a href='results.json'>All results</a> · <a href='selection.json'>Cohort selection before downloads</a> · <a href='../../docs/adaptive-stardist.md'>File map and design</a></p></section><section><h2>Final answers: error and coverage</h2><div class='scroll'><table><thead><tr><th>Configuration</th><th>Counts</th><th>Full-cohort error ↓</th><th>Subset error</th><th>Abstained</th><th>Errors</th><th>Mean time</th></tr></thead><tbody>{html_rows}</tbody></table></div><p>Percentage error is absolute count error divided by the annotation count, averaged across all six images. Incomplete arms have no full-cohort score. Coverage means a numerical estimate was returned, not that it was exact. This is a local derived counting task on BBBC039, not its official instance-segmentation metric.</p></section><section><h2>Against fixed default StarDist</h2><div class='scroll'><table><thead><tr><th>Arm</th><th>Matched images</th><th>Changed counts</th><th>Closer</th><th>Worse</th><th>Tied</th></tr></thead><tbody>{paired_rows}</tbody></table></div><p>Changing a profile is not automatically an improvement. Partial-arm comparisons apply only to the matched images; no missing answer is treated as zero error.</p><h3>Full-chain proposals before acceptance</h3><ul>{''.join(f'<li>{esc(s["policy"])}: {s["coverage"]}/{total}, {pct(s["mean_percentage_error"])} full-cohort error.</li>' for s in result['candidate_summary'])}</ul><p>First/last numerical proposals are diagnostics. Rejected proposals never replace final accepted answers, and no best-of-N result is selected.</p></section>{''.join(cards)}<section><h2>Limits and provenance</h2><ul>{''.join('<li>' + esc(s) + '</li>' for s in protocol['limitations'])}</ul><p>{esc(protocol['preprocessing'])}</p><p>Runtime excludes container setup. Standalone includes adapter execution and first model load. Raw jobs and traces remain local and Git-ignored; copied originals, control masks and selected overlays accompany this report.</p><p>{esc(protocol['attribution'])}. <a href='{protocol['source_page']}'>Dataset documentation</a> · <a href='{protocol['license_url']}'>{esc(protocol['license'])}</a>.</p><pre>.venv/bin/harbor view {esc(jobs)}</pre></section></main></html>"
    if diagnostic_note:
        section = f"<section><h2>Post-hoc check: is adaptation necessary?</h2><p><strong>{esc(diagnostic_note)}</strong></p><p><a href='fixed-sensitive-diagnostic.json'>Exact fixed-profile calculation</a> · <a href='fixed-profile-diagnostic-policy.json'>Post-hoc analysis policy</a></p></section>"
        document = document.replace(
            "<section><h2>Against fixed", section + "<section><h2>Against fixed", 1
        )
    (root / "index.html").write_text(document)
    print(
        json.dumps(
            {
                "standalone": base,
                "summary": result["summary"],
                "paired": result["paired_comparisons"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    render(Path(sys.argv[1]), Path(sys.argv[2]))
