"""Independent numeric/categorical verifier; no model judges or OpenCV imports."""

import json
import math
import sys
from pathlib import Path


def score(answer: dict, expected: dict) -> dict:
    status = answer.get("status", "error")
    value = answer.get("value")
    correct = False
    if status == "answered":
        target = expected["expected"]
        if isinstance(target, (float, int)) and not isinstance(target, bool):
            correct = (
                isinstance(value, (float, int))
                and not isinstance(value, bool)
                and math.isfinite(value)
                and abs(value - target) <= expected.get("tolerance", 0)
            )
        elif isinstance(target, str) and isinstance(value, str):
            correct = value.strip().lower() == target.strip().lower()
    result = {
        "accuracy": float(correct),
        "answered": float(status == "answered"),
        "abstained": float(status == "abstained"),
        "error": float(status not in ("answered", "abstained")),
    }
    if expected.get("metric") in {"bbbc001_percentage_error", "nuclei_count_percentage_error"}:
        # BBBC001 official count metric; also a separately labeled derived-count metric.
        # Missing/invalid predictions have no defined percentage error, never zero.
        valid = (
            status == "answered"
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        )
        result["valid_prediction"] = float(valid)
        if valid:
            result["absolute_count_error"] = abs(value - expected["expected"])
            result["percentage_error"] = (
                100 * abs(value - expected["expected"]) / expected["expected"]
            )
    return result


def main():
    answer_path, expected_path, output_path = map(Path, sys.argv[1:4])
    try:
        answer = json.loads(answer_path.read_text())
    except (OSError, ValueError):
        answer = {"status": "error"}
    result = score(answer, json.loads(expected_path.read_text()))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result) + "\n")


if __name__ == "__main__":
    main()
