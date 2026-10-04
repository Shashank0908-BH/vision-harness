"""Score first/last numerical proposals without replacing accepted-output metrics.

Usage: python -m evals.candidate_report REPORT_DIRECTORY
Requires benchmark_report's results.json. Reads existing traces only; no inference.
"""

import hashlib
import json
import statistics
import sys
from pathlib import Path

from vision_harness.tracing import write_json

from .scoring import score


def aggregate(rows, index):
    matched = [r for r in rows if r["numerical_candidates"]]
    errors = [r["numerical_candidates"][index]["percentage_error"] for r in matched]
    baseline = [r["vanilla_percentage_error"] for r in matched]
    return {
        "policy": "first numerical candidate" if index == 0 else "last numerical candidate",
        "coverage": len(matched),
        "total": len(rows),
        "mean_percentage_error": statistics.mean(errors) if len(matched) == len(rows) else None,
        "answered_subset_percentage_error": statistics.mean(errors) if errors else None,
        "matched_vanilla_subset_error": statistics.mean(baseline)
        if baseline and all(x is not None for x in baseline)
        else None,
        "closer_than_vanilla": sum(
            a < b for a, b in zip(errors, baseline, strict=True) if b is not None
        ),
        "worse_than_vanilla": sum(
            a > b for a, b in zip(errors, baseline, strict=True) if b is not None
        ),
        "tied_with_vanilla": sum(
            a == b for a, b in zip(errors, baseline, strict=True) if b is not None
        ),
    }


def render(root: Path):
    report = json.loads((root / "results.json").read_text())
    trials = {(t["task_id"], t["mode"]): t for t in report["trials"]}
    rows = []
    for task in report["cohort"]:
        trial = trials[task["id"], "full"]
        vanilla = trials[task["id"], "vanilla"]
        path = root / trial["events"]
        raw = path.read_bytes()
        events = [json.loads(line) for line in raw.decode().splitlines()]
        candidates, proposals, round_id = [], [], 0
        for e in events:
            if e["kind"] == "plans":
                round_id += 1
            elif e["kind"] == "candidate_answer":
                answer = e["data"]
                metrics = score(answer, task)
                entry = {
                    "round": round_id,
                    "event_sequence": e["sequence"],
                    "answer": answer,
                    "metrics": metrics,
                }
                proposals.append(entry)
                if metrics["valid_prediction"]:
                    candidates.append(
                        {
                            "round": round_id,
                            "event_sequence": e["sequence"],
                            "count": answer["value"],
                            "percentage_error": metrics["percentage_error"],
                            "absolute_count_error": metrics["absolute_count_error"],
                        }
                    )
            elif e["kind"] == "answer_review":
                if not proposals or "review" in proposals[-1]:
                    raise ValueError("Review is not paired with exactly one preceding candidate")
                proposals[-1]["review"] = e["data"]
                if (
                    candidates
                    and candidates[-1]["event_sequence"] == proposals[-1]["event_sequence"]
                ):
                    candidates[-1]["review"] = e["data"]
        rows.append(
            {
                "task_id": task["id"],
                "image": task["title"],
                "reference_mean": task["expected"],
                "human_counts": task["human_counts"],
                "vanilla_count": vanilla["answer"].get("value"),
                "vanilla_percentage_error": vanilla["metrics"].get("percentage_error"),
                "numerical_candidates": candidates,
                "all_proposals": proposals,
                "planning_rounds": round_id,
                "actual_final_answer": trial["answer"],
                "stop_events": [
                    e["data"] for e in events if e["kind"] in ("loop_stopped", "error")
                ],
                "source_events": trial["events"],
                "source_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    baseline_errors = [r["vanilla_percentage_error"] for r in rows]
    baseline = (
        statistics.mean(baseline_errors) if all(v is not None for v in baseline_errors) else None
    )
    summaries = [aggregate(rows, i) for i in (0, -1)]
    output = {
        "analysis": "Diagnostic candidate counts before final acceptance; no new inference",
        "candidate_policy": "First and last numerical candidate per image, regardless of error or review score. No best-of-N selection. An unreviewed candidate is explicitly marked by the absence of a review.",
        "metric": report["protocol"]["primary_metric"],
        "vanilla_mean_percentage_error": baseline,
        "summary": summaries,
        "rows": rows,
        "limitations": "Candidate scores do not replace actual final outputs. Later proposals depend on previous review feedback, so this is not a run with Jev disabled. Missing candidates have no full-dataset error; matched-subset metrics are separately labeled.",
    }
    write_json(root / "candidate-counts.json", output)

    def pct(v):
        return f"{v:.2f}%" if v is not None else "Undefined"

    lines = [
        "# Proposed counts before final review",
        "",
        output["candidate_policy"],
        "",
        output["metric"],
        "",
        "| Output | Numerical counts | Full-dataset error ↓ | Candidate-subset error | Vanilla on that subset |",
        "|---|---:|---:|---:|---:|",
        f"| Vanilla final answers | {sum(v is not None for v in baseline_errors)}/{len(rows)} | {pct(baseline)} | — | — |",
    ]
    for s in summaries:
        lines.append(
            f"| {s['policy']} | {s['coverage']}/{s['total']} | {pct(s['mean_percentage_error'])} | {pct(s['answered_subset_percentage_error'])} | {pct(s['matched_vanilla_subset_error'])} |"
        )
    lines += [
        "",
        "| Image | Reference | Vanilla | Proposed numerical counts by round | Actual final status |",
        "|---|---:|---:|---|---|",
    ]
    for row in rows:
        sequence = (
            "; ".join(
                f"r{c['round']}: {c['count']:g} ({c['percentage_error']:.2f}% error)"
                for c in row["numerical_candidates"]
            )
            or "None"
        )
        lines.append(
            f"| {row['image']} | {row['reference_mean']:g} | {row['vanilla_count']} | {sequence} | {row['actual_final_answer']['status']} |"
        )
    lines += [
        "",
        output["limitations"],
        "",
        "Exact checks, event sequence numbers, trace hashes, and stopping reasons are in [candidate-counts.json](candidate-counts.json).",
        "",
        "## Source traces",
        "",
    ]
    lines += [f"- [{r['image']}]({r['source_events']})" for r in rows]
    lines += ["", "[Accepted-output report](index.html) · [Findings](findings.md)"]
    (root / "candidate-counts.md").write_text("\n".join(lines) + "\n")
    return output


if __name__ == "__main__":
    output = render(Path(sys.argv[1]))
    print(json.dumps(output["summary"], indent=2))
