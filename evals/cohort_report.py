"""Build a reviewable paired task report from completed Harbor trials.

Read-only analysis: never calls models, reruns trials, or changes grading.
Usage: python -m evals.cohort_report REPORT_DIRECTORY JOBS_DIRECTORY
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

from .scoring import score

LABELS = {
    "vanilla": "Vanilla Astra",
    "tools": "Astra + OpenCV",
    "select": "Tools + Jev selection",
    "review": "Tools + Jev review",
    "full": "Full harness",
}
FAMILIES = {
    "count": "Separated-circle counting",
    "color_count": "Color-filtered counting",
    "position": "Left/right position",
    "distance": "Pixel distance",
    "touching_count": "Touching-circle counting",
}


def load_json(path: Path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def seconds(value):
    return f"{value:.1f}s" if value is not None else "unavailable"


def render(report_dir: Path, jobs_dir: Path):
    load_dotenv(".env", override=True)
    protocol = load_json(report_dir / "protocol.json")
    cohort = load_json(report_dir / "cohort.json")
    by_id = {row["id"]: row for row in cohort}
    modes = protocol["modes"]
    trials = {}
    for path in sorted(jobs_dir.glob("*/*/result.json")):
        result = load_json(path)
        task_id = result.get("task_name")
        if task_id not in by_id:
            continue
        run = path.parent / "agent/run"
        manifest = load_json(run / "manifest.json", {})
        # Failure before harness startup still counts in the intended experimental mode.
        config = load_json(path.parent / "config.json", {})
        mode = manifest.get("mode") or config.get("agent", {}).get("kwargs", {}).get("mode")
        if mode not in modes:
            raise ValueError(f"Cannot identify mode of {path}")
        key = (task_id, mode)
        if key in trials:
            raise ValueError(
                f"Duplicate trial for {key}; report requires explicit attempt selection"
            )
        answer = load_json(
            run / "answer.json",
            {"status": "error", "value": None, "explanation": "Harness did not produce an answer"},
        )
        rewards = (result.get("verifier_result") or {}).get("rewards")
        independently_scored = score(answer, by_id[task_id])
        if rewards and rewards.get("accuracy") != independently_scored["accuracy"]:
            raise ValueError(f"Verifier/recomputed score disagreement for {path}")
        event_file = run / "events.jsonl"
        events = (
            [json.loads(line) for line in event_file.read_text().splitlines()]
            if event_file.exists()
            else []
        )
        provider_by_call = {}
        tokens = {
            "astra": {"input": 0, "output": 0, "calls": 0, "started_calls": 0},
            "jev": {"input": 0, "output": 0, "calls": 0, "started_calls": 0},
        }
        for event in events:
            data = event["data"]
            if event["kind"] == "call_started":
                provider_by_call[data["call_id"]] = data["provider"]
                tokens[data["provider"]]["started_calls"] += 1
            elif event["kind"] == "call_finished":
                provider = provider_by_call[data["call_id"]]
                usage = data.get("usage") or {}
                tokens[provider]["input"] += usage.get("input_tokens", 0)
                tokens[provider]["output"] += usage.get("output_tokens", 0)
                tokens[provider]["calls"] += 1
        trials[key] = {
            "task_id": task_id,
            "mode": mode,
            "answer": answer,
            "rewards": rewards,
            "correct": bool(
                rewards and rewards.get("accuracy") == 1 and not result.get("exception_info")
            ),
            "infrastructure_error": result.get("exception_info"),
            "elapsed_seconds": manifest.get("elapsed_seconds"),
            "tokens": tokens,
            "tool_calls": sum(e["kind"] == "tool_started" for e in events),
            "selections": [e["data"] for e in events if e["kind"] == "selection"],
            "assessments": [e["data"] for e in events if e["kind"] == "assessments"],
            "reviews": [e["data"] for e in events if e["kind"] == "answer_review"],
            "candidate_answers": [e["data"] for e in events if e["kind"] == "candidate_answer"],
            "trace": os.path.relpath(path.parent / "agent/trajectory.json", report_dir),
            "events": os.path.relpath(event_file, report_dir),
            "artifacts": os.path.relpath(run / "artifacts", report_dir),
            "manifest": manifest,
        }
    missing = [(t["id"], m) for t in cohort for m in modes if (t["id"], m) not in trials]
    if missing:
        raise ValueError(f"Cohort not complete; missing {missing}")
    summaries = []
    for mode in modes:
        group = [trials[t["id"], mode] for t in cohort]
        elapsed = [t["elapsed_seconds"] for t in group if t["elapsed_seconds"] is not None]
        won = [
            FAMILIES[t["family"]]
            for t in cohort
            if trials[t["id"], mode]["correct"] and not trials[t["id"], "vanilla"]["correct"]
        ]
        lost = [
            FAMILIES[t["family"]]
            for t in cohort
            if not trials[t["id"], mode]["correct"] and trials[t["id"], "vanilla"]["correct"]
        ]
        summaries.append(
            {
                "mode": mode,
                "correct": sum(t["correct"] for t in group),
                "total": len(group),
                "abstentions": sum(t["answer"]["status"] == "abstained" for t in group),
                "errors": sum(
                    bool(t["infrastructure_error"]) or t["answer"]["status"] == "error"
                    for t in group
                ),
                "mean_seconds": statistics.mean(elapsed) if elapsed else None,
                "tokens": {
                    p: {
                        metric: sum(t["tokens"][p][metric] for t in group)
                        for metric in ("input", "output", "calls", "started_calls")
                    }
                    for p in ("astra", "jev")
                },
                "wins_vs_vanilla": won,
                "losses_vs_vanilla": lost,
            }
        )
    best = max(s["correct"] for s in summaries)
    winners = [LABELS[s["mode"]] for s in summaries if s["correct"] == best]
    conclusion = f"Highest observed accuracy: {', '.join(winners)} ({best}/{len(cohort)} correct)."
    fastest_best = min(
        (s for s in summaries if s["correct"] == best and s["mean_seconds"] is not None),
        key=lambda s: s["mean_seconds"],
    )
    practical = (
        f"Among the accuracy leaders, {LABELS[fastest_best['mode']]} had the lowest observed mean runtime ({seconds(fastest_best['mean_seconds'])}). This cohort shows no accuracy benefit from the added layers when vanilla already answers every task correctly."
        if trials and all(trials[t["id"], "vanilla"]["correct"] for t in cohort)
        else f"Among the accuracy leaders, {LABELS[fastest_best['mode']]} had the lowest observed mean runtime ({seconds(fastest_best['mean_seconds'])})."
    )
    data = {
        "protocol": protocol,
        "conclusion": conclusion,
        "practical_result": practical,
        "summary": summaries,
        "trials": list(trials.values()),
    }
    write_json(report_dir / "results.json", data)
    lines = [
        "# Five-task live comparison",
        "",
        conclusion,
        "",
        practical,
        "",
        "One attempt per preselected test-split task, five modes, 25 trials. This is an exploratory result; it does not establish general superiority.",
        "",
        "| Mode | Correct | Abstentions | Errors | Mean runtime | Astra tokens in/out | Jev tokens in/out |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s in summaries:
        a, j = s["tokens"]["astra"], s["tokens"]["jev"]
        lines.append(
            f"| {LABELS[s['mode']]} | {s['correct']}/{s['total']} | {s['abstentions']} | {s['errors']} | {seconds(s['mean_seconds'])} | {a['input']}/{a['output']} | {j['input']}/{j['output']} |"
        )
    lines += [
        "",
        "## Task-by-task answers",
        "",
        "| Task | Expected | " + " | ".join(LABELS[m] for m in modes) + " |",
        "|---|---|" + "---|" * len(modes),
    ]
    for task in cohort:
        cells = []
        for mode in modes:
            t = trials[task["id"], mode]
            cells.append(
                f"{'PASS' if t['correct'] else 'FAIL'}: {t['answer']['value']} ({t['answer']['status']})"
            )
        lines.append(
            f"| {FAMILIES[task['family']]} | {task['expected']} | " + " | ".join(cells) + " |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "Counts and position are exact; distance permits ±2 pixels. Both the initial verifier and this report's independent re-scoring agree. All failures and abstentions are retained.",
        "",
        "Plans are independently generated in each mode. Added model calls, competing methods, and review retries change compute. Compare accuracy and time together; do not attribute a difference solely to Jev's selector.",
        "",
        "Token counts are separated by provider and show recorded usage only. A failed response parse can leave a started call without recorded usage; totals are then lower bounds. Check started_calls versus calls in results.json. Dollar cost is not estimated because versioned pricing is not configured.",
        "",
        "## Traces",
        "",
        f"Run `uv run harbor view {jobs_dir}` for the full viewer. The HTML report links each trial's JSON trajectory, event log and artifact directory.",
    ]
    preflight_note = ""
    if protocol.get("preflight_failure"):
        preflight_note = "An initial five-trial baseline batch exposed a harness validator bug: it rejected citations to the image actually supplied. The failed batch is preserved separately. The validator was fixed for all modes and the complete comparison restarted; task selection, prompts, model settings and grading were unchanged. These test-split examples were therefore seen during infrastructure debugging."
        lines += ["", "## Preflight correction", "", preflight_note]
    (report_dir / "README.md").write_text("\n".join(lines) + "\n")

    def esc(value):
        return html.escape(str(value))

    table = "".join(
        f"<tr><th>{esc(LABELS[s['mode']])}</th><td><strong>{s['correct']}/{s['total']}</strong></td><td>{s['abstentions']}</td><td>{s['errors']}</td><td>{seconds(s['mean_seconds'])}</td><td>{s['tokens']['astra']['input']:,} / {s['tokens']['astra']['output']:,}</td><td>{s['tokens']['jev']['input']:,} / {s['tokens']['jev']['output']:,}</td></tr>"
        for s in summaries
    )
    cards = []
    for task in cohort:
        image_path = Path("evals/datasets/generated") / task["image"]
        image = base64.b64encode(image_path.read_bytes()).decode()
        sections = []
        for mode in modes:
            t = trials[task["id"], mode]
            diagnostic = {
                k: t[k]
                for k in (
                    "selections",
                    "assessments",
                    "candidate_answers",
                    "reviews",
                    "tokens",
                    "infrastructure_error",
                )
            }
            sections.append(
                f"<details><summary><span class={'pass' if t['correct'] else 'fail'}>{'PASS' if t['correct'] else 'FAIL'}</span> {esc(LABELS[mode])} — {esc(t['answer']['value'])}</summary><p>{esc(t['answer'].get('explanation', ''))}</p><p>Status: {esc(t['answer']['status'])}; tool calls: {t['tool_calls']}; runtime: {seconds(t['elapsed_seconds'])}</p><p><a href='{esc(t['trace'])}'>Trajectory JSON</a> · <a href='{esc(t['events'])}'>Event log</a> · <a href='{esc(t['artifacts'])}'>Images and masks</a></p><pre>{esc(json.dumps(diagnostic, indent=2))}</pre></details>"
            )
        cards.append(
            f"<section><h2>{esc(FAMILIES[task['family']])}</h2><p>{esc(task['question'])}</p><div class='task'><img alt='{esc(FAMILIES[task['family']])} input image' src='data:image/png;base64,{image}'><div><p><b>Expected:</b> {esc(task['expected'])}<br><b>Tolerance:</b> {task['tolerance']}<br><small>Task {task['id']}</small></p>{''.join(sections)}</div></div></section>"
        )
    document = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Vision harness · Five-task results</title><style>
body{margin:0;background:#f4f6fa;color:#17243a;font:16px/1.6 system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:32px 22px}h1{font-size:clamp(28px,5vw,42px);line-height:1.15}h2{margin-top:0}section,.intro{background:white;border:1px solid #dce3ed;border-radius:14px;padding:24px;margin:22px 0}.tag{font-size:12px;text-transform:uppercase;letter-spacing:.12em;color:#52677e}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:12px;border-bottom:1px solid #dce3ed;white-space:nowrap}thead{background:#edf2fa}.task{display:grid;grid-template-columns:minmax(240px,1fr) minmax(300px,1.4fr);gap:28px}img{width:100%;border:1px solid #dce3ed;border-radius:8px}details{border-top:1px solid #dce3ed;padding:12px 0}summary{cursor:pointer;font-weight:600}.pass{color:#13774f}.fail{color:#b23831}pre{font:12px/1.5 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f9;padding:12px;max-height:350px;overflow:auto}a{color:#2459a9}small{color:#53657b}@media(max-width:740px){.task{grid-template-columns:1fr}section,.intro{padding:16px}main{padding:18px 12px}}
</style><main><p class="tag">Astra · OpenCV · Jev · Harbor / 22 September 2026</p><h1>Five tasks. Five modes.<br>Every answer inspectable.</h1>"""
    document += (
        f"<div class='intro'><h2>{esc(conclusion)}</h2><p><strong>{esc(practical)}</strong></p><p>25 live trials: one preselected test-split example each for counting, color filtering, spatial position, distance and touching objects. One attempt per task. These are exploratory findings, not proof of general superiority.</p><p>Models, prompts and thresholds were frozen for this cohort. Plans were generated independently per mode. All errors and abstentions count against overall accuracy.</p></div><section><h2>Accuracy and execution time</h2><div class='scroll'><table><thead><tr><th>Mode</th><th>Correct</th><th>Abstained</th><th>Errors</th><th>Mean runtime</th><th>Astra tokens in/out</th><th>Jev tokens in/out</th></tr></thead><tbody>{table}</tbody></table></div><p><small>Runtime is harness wall time, excluding container build/setup. Tokens show recorded usage only; failed response parsing may leave unrecorded usage, so totals can be lower bounds. Expand a trial to compare started calls with recorded calls. Tokens from different providers are not directly equivalent costs. No dollar estimate is inferred.</small></p></section>"
        + "".join(cards)
        + f"<section><h2>Review the evidence</h2><p>Open each mode above for its answer, Jev scores, selection decisions and review result. Independent verification uses exact answers, with ±2 pixels allowed for distance.</p><p>{esc(preflight_note)}</p><p><a href='findings.md'>Findings and failure analysis</a> · <a href='results.json'>Complete results JSON</a> · <a href='protocol.json'>Frozen protocol</a> · <a href='README.md'>Markdown comparison</a></p><pre>uv run harbor view {esc(jobs_dir)}</pre></section></main></html>"
    )
    (report_dir / "index.html").write_text(document)
    print(conclusion)
    print(f"Report: {report_dir / 'index.html'}")


if __name__ == "__main__":
    render(Path(sys.argv[1]), Path(sys.argv[2]))
