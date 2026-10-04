"""Report the complete BBBC001 benchmark using its published percentage-error metric.

Usage: python -m evals.benchmark_report REPORT_DIRECTORY JOBS_DIRECTORY
No model calls or reruns. Refuses duplicate attempts and incomplete cohorts.
"""

import base64
import html
import json
import os
import statistics
import sys
from pathlib import Path

from dotenv import load_dotenv

from vision_harness.tracing import write_json

from .cohort_report import LABELS, load_json
from .scoring import score


def summarize(group):
    valid = [t for t in group if t["metrics"]["valid_prediction"] and not t["infrastructure_error"]]
    errors = [t["metrics"]["percentage_error"] for t in valid]
    elapsed = [t["elapsed_seconds"] for t in group if t["elapsed_seconds"] is not None]
    return {
        "mode": group[0]["mode"],
        "coverage": len(valid),
        "total": len(group),
        "benchmark_percentage_error": statistics.mean(errors) if len(valid) == len(group) else None,
        "answered_subset_percentage_error": statistics.mean(errors) if errors else None,
        "abstentions": sum(t["answer"].get("status") == "abstained" for t in group),
        "errors": sum(
            bool(t["infrastructure_error"]) or t["answer"].get("status") == "error" for t in group
        ),
        "mean_seconds": statistics.mean(elapsed) if elapsed else None,
        "tokens": {
            p: {
                k: sum(t["tokens"][p][k] for t in group)
                for k in ("input", "output", "started_calls", "calls")
            }
            for p in ("astra", "jev")
        },
    }


def render(report_dir: Path, jobs_dir: Path):
    load_dotenv(".env", override=True)
    protocol = load_json(report_dir / "protocol.json")
    labels = {**LABELS, **protocol.get("mode_labels", {})}
    cohort = load_json(report_dir / "cohort.json")
    by_id = {t["id"]: t for t in cohort}
    modes = protocol["modes"]
    trials = {}
    for path in sorted(jobs_dir.glob("*/*/result.json")):
        result = load_json(path)
        task_id = result.get("task_name")
        if task_id not in by_id:
            continue
        directory = path.parent / "agent/run"
        manifest = load_json(directory / "manifest.json", {})
        config = load_json(path.parent / "config.json", {})
        mode = manifest.get("mode") or config.get("agent", {}).get("kwargs", {}).get("mode")
        if mode not in modes or (task_id, mode) in trials:
            raise ValueError(f"Unknown mode or duplicate attempt: {path}")
        answer = load_json(
            directory / "answer.json",
            {"status": "error", "value": None, "explanation": "No saved answer"},
        )
        metrics = score(answer, by_id[task_id])
        rewards = (result.get("verifier_result") or {}).get("rewards")
        if rewards is not None and rewards != metrics:
            raise ValueError(f"Independent re-scoring differs from Harbor verifier: {path}")
        events_path = directory / "events.jsonl"
        events = (
            [json.loads(line) for line in events_path.read_text().splitlines()]
            if events_path.exists()
            else []
        )
        providers = {}
        tokens = {p: dict(input=0, output=0, started_calls=0, calls=0) for p in ("astra", "jev")}
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
        trials[task_id, mode] = {
            "task_id": task_id,
            "mode": mode,
            "answer": answer,
            "metrics": metrics,
            "harbor_rewards": rewards,
            "infrastructure_error": result.get("exception_info"),
            "elapsed_seconds": manifest.get("elapsed_seconds"),
            "tokens": tokens,
            "tool_calls": sum(e["kind"] == "tool_started" for e in events),
            "perception_outputs": [
                {
                    "evidence_id": e["data"]["evidence_id"],
                    "tool": e["data"]["tool"],
                    "parameters": e["data"].get("parameters"),
                    "measurements": {
                        k: v
                        for k, v in e["data"].get("measurements", {}).items()
                        if k != "components"
                    },
                    "quality_flags": e["data"].get("quality_flags", []),
                }
                for e in events
                if e["kind"] == "evidence"
                and e["data"].get("tool")
                in ("components", "watershed", "crop", "measure", "stardist")
            ],
            "decisions": [
                e
                for e in events
                if e["kind"]
                in (
                    "selection",
                    "assessments",
                    "candidate_answer",
                    "answer_review",
                    "format_retry",
                    "evidence_compacted",
                    "review_feedback",
                    "loop_stopped",
                    "tool_reused",
                    "error",
                )
            ],
            "trace": os.path.relpath(path.parent / "agent/trajectory.json", report_dir),
            "events": os.path.relpath(events_path, report_dir),
            "artifacts": os.path.relpath(directory / "artifacts", report_dir),
        }
    missing = [(t["id"], m) for t in cohort for m in modes if (t["id"], m) not in trials]
    if missing:
        raise ValueError(f"Incomplete cohort: {missing}")
    summary = [summarize([trials[t["id"], m] for t in cohort]) for m in modes]
    complete = [s for s in summary if s["benchmark_percentage_error"] is not None]
    if complete:
        best = min(s["benchmark_percentage_error"] for s in complete)
        winners = [labels[s["mode"]] for s in complete if s["benchmark_percentage_error"] == best]
        conclusion = f"Lowest error among modes answering all six images: {', '.join(winners)} ({best:.2f}%)."
    else:
        conclusion = (
            "No mode answered all six images; no complete-benchmark winner can be declared."
        )
    result = {
        "protocol": protocol,
        "cohort": cohort,
        "conclusion": conclusion,
        "summary": summary,
        "trials": list(trials.values()),
    }
    write_json(report_dir / "results.json", result)

    def percent(value):
        return f"{value:.2f}%" if value is not None else "Incomplete"

    def seconds(value):
        return f"{value:.1f}s" if value is not None else "Unavailable"

    esc = lambda value: html.escape(str(value))  # noqa: E731
    lines = [
        "# BBBC001v1: real microscopy benchmark",
        "",
        conclusion,
        "",
        f"Complete published six-image cell-counting dataset; {len(modes)} modes, one attempt each. Lower percentage error is better. No invented images or labels.",
        "",
        "| Mode | Valid counts | Published metric | Answered-subset error | Abstained | Errors | Mean time |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    table = []
    for s in summary:
        values = [
            labels[s["mode"]],
            f"{s['coverage']}/6",
            percent(s["benchmark_percentage_error"]),
            percent(s["answered_subset_percentage_error"]),
            s["abstentions"],
            s["errors"],
            seconds(s["mean_seconds"]),
        ]
        lines.append("| " + " | ".join(map(str, values)) + " |")
        table.append("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in values) + "</tr>")
    lines += [
        "",
        "An incomplete run has no official full-dataset metric. Answered-subset errors use different image subsets and must not be ranked against complete scores.",
        "",
        "## Predictions",
        "",
        "| Image | Human counts | Reference mean | " + " | ".join(labels[m] for m in modes) + " |",
        "|---|---|---|" + "---|" * len(modes),
    ]
    cards = []
    for task in cohort:
        cells, details = [], []
        for mode in modes:
            t = trials[task["id"], mode]
            answer = t["answer"]
            error = t["metrics"].get("percentage_error")
            label = (
                f"{answer.get('value')} ({error:.2f}% error)"
                if error is not None
                else answer.get("status", "error")
            )
            cells.append(label)
            diagnostic = {
                key: t[key]
                for key in ("perception_outputs", "decisions", "tokens", "infrastructure_error")
            }
            details.append(
                f"<details><summary>{esc(labels[mode])}: {esc(label)}</summary><p>{esc(answer.get('explanation', ''))}</p><p>Limitations: {esc('; '.join(answer.get('limitations', [])))}</p><p>Status: {esc(answer.get('status'))}. Tool calls: {t['tool_calls']}. Time: {seconds(t['elapsed_seconds'])}.</p><p><a href='{esc(t['trace'])}'>Harbor trajectory</a> · <a href='{esc(t['events'])}'>Event log</a> · <a href='{esc(t['artifacts'])}'>Masks and crops</a></p><pre>{esc(json.dumps(diagnostic, indent=2))}</pre></details>"
            )
        lines.append(
            f"| {task['title']} | {task['human_counts']} | {task['expected']} | "
            + " | ".join(cells)
            + " |"
        )
        image = base64.b64encode(
            (Path(protocol["dataset_directory"]) / task["image"]).read_bytes()
        ).decode()
        cards.append(
            f"<section><h2>{esc(task['title'])}</h2><p>{esc(task['question'])}</p><div class='task'><div><img src='data:image/png;base64,{image}' alt='{esc(task['title'])}: original fluorescence image'><p>Human counts: {esc(task['human_counts'])}. Reference mean: <strong>{task['expected']}</strong>.</p><small>{esc(task['source_filename'])}</small></div><div>{''.join(details)}</div></div></section>"
        )
    lines += [
        "",
        "## Method and limits",
        "",
        protocol["primary_metric"],
        "",
        protocol["preprocessing"],
        "",
        protocol["split_note"],
        "",
        *[f"- {s}" for s in protocol["limitations"]],
        "",
        f"Source: [{protocol['name']}]({protocol['source_page']}). {protocol['attribution']}",
        "",
        f"[{protocol['license']}]({protocol['license_url']})",
        "",
        "Token totals include only recorded usage. An interrupted/failed parse may leave an unrecorded call; compare started_calls and calls in results.json. Runtime excludes container setup.",
        "",
        f"View traces: `uv run harbor view {jobs_dir}`",
    ]
    (report_dir / "README.md").write_text("\n".join(lines) + "\n")
    css = "body{margin:0;background:#f3f5f8;color:#17243a;font:16px/1.6 system-ui}main{max-width:1200px;margin:auto;padding:24px}h1{font-size:clamp(28px,5vw,44px);line-height:1.2}section{background:white;border:1px solid #dce3ed;border-radius:12px;padding:24px;margin:22px 0}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:12px;text-align:left;border-bottom:1px solid #dce3ed;white-space:nowrap}.task{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.4fr);gap:24px}img{width:100%;height:auto}details{border-top:1px solid #dce3ed;padding:12px 0}summary{cursor:pointer;font-weight:600}pre{font:12px/1.5 monospace;white-space:pre-wrap;overflow-wrap:anywhere;max-height:350px;overflow:auto;background:#f3f5f8;padding:12px}a{color:#2459a9}small{overflow-wrap:anywhere}p{overflow-wrap:anywhere}@media(max-width:740px){.task{grid-template-columns:1fr}main{padding:12px}section{padding:16px}}"
    document = f"<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>BBBC001 · Real microscopy results</title><style>{css}</style><main><p>{esc(protocol.get('stack_label', 'ASTRA · OPENCV · JEV · HARBOR'))}</p><h1>Real microscopy.<br>Six published images. {len(modes)} modes.</h1><section><h2>{esc(conclusion)}</h2><p>The complete BBBC001v1 counting benchmark, not a synthetic task set. Every prediction and failure is retained.</p><p>Percentage error compares each prediction with the mean of two published human counts, then averages the six errors. Lower is better. Human annotators disagree, so exact-match accuracy would be misleading.</p><p><a href='{protocol['source_page']}'>Original benchmark and evaluation instructions</a> · <a href='protocol.json'>Frozen protocol</a> · <a href='results.json'>All results</a> · <a href='README.md'>Readable comparison</a> · <a href='findings.md'>Failure analysis</a></p></section><section><h2>Error and coverage</h2><div class='scroll'><table><thead><tr><th>Mode</th><th>Valid counts</th><th>Full benchmark error ↓</th><th>Answered-subset error</th><th>Abstained</th><th>Errors</th><th>Mean time</th></tr></thead><tbody>{''.join(table)}</tbody></table></div><p>An incomplete mode has no official full-benchmark score. Its subset error describes only the images answered; it cannot establish a win over a complete run.</p></section>{''.join(cards)}<section><h2>What this experiment can tell us</h2><ul>{''.join('<li>' + esc(s) + '</li>' for s in protocol['limitations'])}</ul><p>{esc(protocol['preprocessing'])}</p><p>{esc(protocol['split_note'])}</p><p>Runtime excludes container setup. Recorded token usage and incomplete call counts appear inside each trial. No price estimate is inferred.</p><pre>uv run harbor view {esc(jobs_dir)}</pre><p>{esc(protocol['attribution'])}</p><p><a href='{protocol['license_url']}'>{esc(protocol['license'])}</a> TIFF to PNG is the only image conversion.</p></section></main></html>"
    candidate_results = load_json(report_dir / "candidate-counts.json")
    if candidate_results:
        candidate_note = "<section><h2>Counts before acceptance</h2><p>Numerical proposals are scored separately from final accepted answers. All rounds and rejections remain visible; no best-of-N selection.</p><p><a href='candidate-counts.md'>Per-round count comparison</a> · <a href='candidate-counts.json'>Exact candidate scores and review checks</a></p></section>"
        candidate_summary = candidate_results.get("summary", [])
        if candidate_summary and all("policy" in s for s in candidate_summary):
            candidate_rows = "".join(
                f"<tr><td>{esc(s['policy'])}</td><td>{s['coverage']}/{s['total']}</td><td>{percent(s['mean_percentage_error'])}</td></tr>"
                for s in candidate_summary
            )
            candidate_table = f"<div class='scroll'><table><thead><tr><th>Proposal policy</th><th>Available counts</th><th>Full-dataset candidate error ↓</th></tr></thead><tbody>{candidate_rows}</tbody></table></div><p>These include proposals from trials that later abstained or failed. Last means last numerical proposal available, not a guarantee that every trial completed the same number of rounds.</p>"
            candidate_note = candidate_note.replace("</section>", candidate_table + "</section>")
        document = document.replace("</section>", "</section>" + candidate_note, 1)
    recovery = load_json(report_dir / "jev-recovery-field4/result.json")
    if recovery:
        support = recovery["answers"]["support"]["noul"]
        note = f"The user-requested Jev retry succeeded after bounding the evidence payload. It returned support {support}, compared with the unchanged {recovery['acceptance_threshold']} acceptance threshold. The original frozen benchmark remains below; the repaired retry is separate."
        recovery_runs = load_json(report_dir / "recovery-results.json")
        if recovery_runs:
            latest = recovery_runs["harbor_attempts"][-1]
            clean = latest["infrastructure_error"] is None and latest["answer"]["status"] != "error"
            note += f" The latest Harbor recovery finished with status {latest['answer']['status']} and {'no API/parsing exception' if clean else 'an execution failure'}."
        section = f"<section><h2>Jev retry: API failure resolved</h2><p>{esc(note)}</p><p><a href='jev-recovery-field4/result.json'>Successful review retry</a> · <a href='jev-recovery-field4/events.jsonl'>Payload reduction trace</a> · <a href='retry-protocol.json'>Harbor recovery protocol</a> · <a href='findings.md'>Repair and failure analysis</a></p></section>"
        if recovery_runs:
            section = section.replace(
                "</section>",
                "<p><a href='recovery-results.json'>Both Harbor recovery attempts and trace links</a> · <a href='recovery-v2-protocol.json'>Latest recovery protocol</a></p></section>",
            )
        document = document.replace(
            "<section><h2>Error and coverage", section + "<section><h2>Error and coverage"
        )
        with (report_dir / "README.md").open("a") as handle:
            handle.write(
                "\n## User-requested Jev retry\n\n"
                + note
                + "\n\nSee [recovery evidence](jev-recovery-field4/result.json) and [failure analysis](findings.md).\n"
            )
    (report_dir / "index.html").write_text(document)
    print(conclusion)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    render(Path(sys.argv[1]), Path(sys.argv[2]))
