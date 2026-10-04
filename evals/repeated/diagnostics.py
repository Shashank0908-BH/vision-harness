"""Post-scoring descriptive checks; never used to select the evaluation cohort."""

import json
import statistics
from collections import Counter

from vision_harness.tracing import write_json

from .data import REPORT


def main():
    result = json.loads((REPORT / "results.json").read_text())
    records = result["records"]
    arms = [
        "vanilla",
        "astra_tools_paired",
        "full_harness",
        "stardist-default",
        "stardist-sensitive",
        "stardist-conservative",
        "cellpose-sam",
    ]
    groups = {}
    for row in records:
        groups.setdefault(row["id"], []).append(row)
    shared = [
        row
        for rows in groups.values()
        if len(rows) == 3 and all(r["values"][a] is not None for r in rows for a in arms)
        for row in rows
    ]
    common = {
        "image_ids": sorted({r["id"] for r in shared}),
        "images": len(shared) // 3,
        "attempts": len(shared),
        "mape_percent": {
            a: statistics.mean(
                abs(r["values"][a] - r["expected"]) / r["expected"] * 100 for r in shared
            )
            for a in arms
        },
        "scope": "Post-scoring complete-case diagnostic: excludes any image with a missing answer in any compared arm/repetition; not the primary full-cohort result.",
    }
    review = []
    for status in sorted({r["review_status"] for r in records}):
        selected = [r for r in records if r["review_status"] == status]
        numerical = [r for r in selected if r["values"]["full_harness"] is not None]
        review.append(
            {
                "review_status": status,
                "attempts": len(selected),
                "numeric_answers": len(numerical),
                "abstentions": sum(r["statuses"]["full_harness"] == "abstained" for r in selected),
                "within_10_percent": sum(
                    abs(r["values"]["full_harness"] - r["expected"]) / r["expected"] <= 0.1
                    for r in numerical
                ),
                "conditional_mape_percent": statistics.mean(
                    abs(r["values"]["full_harness"] - r["expected"]) / r["expected"] * 100
                    for r in numerical
                )
                if numerical
                else None,
            }
        )
    output = {
        "scope": "Descriptive analysis added after scoring; no model runs or cohort changes.",
        "jev_choices": dict(Counter(r["selected_id"] for r in records)),
        "astra_preferences": dict(Counter(r["astra_preferred_id"] for r in records)),
        "common_complete_cases": common,
        "review": review,
        "selection_and_final_counts_identical": all(
            r["values"]["jev_selection_stage"] == r["values"]["full_harness"] for r in records
        ),
        "per_image_count_variation": {
            arm: {
                "all_three_numeric": sum(
                    all(r["values"][arm] is not None for r in rows) for rows in groups.values()
                ),
                "all_three_numeric_and_identical": sum(
                    all(r["values"][arm] is not None for r in rows)
                    and len({r["values"][arm] for r in rows}) == 1
                    for rows in groups.values()
                ),
            }
            for arm in arms
        },
    }
    write_json(REPORT / "diagnostics.json", output)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
