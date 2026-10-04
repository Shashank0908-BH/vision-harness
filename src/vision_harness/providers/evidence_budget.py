"""Deterministic Jev evidence projection; full measurements remain in local traces."""

import copy
import json
import statistics


def encoded_size(value: dict) -> int:
    return len(json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode())


def bounded_request(request: dict, max_bytes: int) -> tuple[dict, dict | None]:
    before = encoded_size(request)
    if before <= max_bytes:
        return request, None
    projected = copy.deepcopy(request)
    summaries = []
    for evidence in projected["state"].get("evidence", []):
        measurements = evidence.get("measurements", {})
        components = measurements.get("components")
        if not isinstance(components, list) or not components:
            continue
        areas = [c["area_pixels"] for c in components]
        measurements.pop("components")
        measurements["components_summary"] = {
            "record_count": len(components),
            "area_pixels": {
                "total": sum(areas),
                "minimum": min(areas),
                "median": statistics.median(areas),
                "maximum": max(areas),
            },
            "border_touching_records": sum(bool(c.get("touches_border")) for c in components),
            "geometry_omitted": True,
            "limitation": "Aggregate pixel-region statistics, not verified cell identities. Individual boxes and centroids are retained in the local trace but are not visible in this request.",
        }
        summaries.append(
            {"evidence_id": evidence["evidence_id"], "component_records": len(components)}
        )
    after = encoded_size(projected)
    if after > max_bytes:
        raise ValueError(
            f"Jev request remains {after} bytes after component summarization; local budget is {max_bytes}. "
            "Question, answer, methods and quality flags were not truncated."
        )
    return projected, {
        "before_bytes": before,
        "after_bytes": after,
        "summarized_evidence": summaries,
    }
