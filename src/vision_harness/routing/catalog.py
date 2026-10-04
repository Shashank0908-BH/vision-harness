"""A research proposal becomes executable only through this explicit registry."""

import hashlib
from pathlib import Path

from .contracts import Catalog, Intent, Procedure

ROOT = Path(__file__).resolve().parents[3]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_catalog(path: Path) -> Catalog:
    catalog = Catalog.model_validate_json(path.read_text())
    ids = [p.plan_id for p in catalog.procedures]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate catalog procedure IDs")
    for procedure in catalog.procedures:
        validate_parameters(procedure)
    return catalog


def local_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Registered paths must stay within the repository")
    return path


def validate_parameters(p: Procedure) -> None:
    expected = (
        {"prob_thresh", "nms_thresh", "normalize_percentiles", "threads"}
        if p.adapter == "stardist"
        else {"flow_threshold", "cellprob_threshold", "min_size", "batch_size", "device"}
    )
    if set(p.parameters) != expected:
        raise ValueError(f"Unexpected parameters for {p.adapter}")
    v = p.parameters
    if p.adapter == "stardist":
        if not 0 < v["prob_thresh"] < 1 or not 0 < v["nms_thresh"] < 1:
            raise ValueError("Invalid StarDist thresholds")
        if v["normalize_percentiles"] != [1, 99.8] or v["threads"] != 2:
            raise ValueError("Unvalidated StarDist preprocessing/threads")
        if len(p.files) != 3 or {Path(f.path).name for f in p.files} != {
            "weights_best.h5", "config.json", "thresholds.json"
        }:
            raise ValueError("StarDist requires exactly its three pinned model files")
        if len({Path(f.path).parent for f in p.files}) != 1:
            raise ValueError("StarDist files must share one model directory")
    else:
        if len(p.files) != 1 or v != {
            "flow_threshold": 0.4, "cellprob_threshold": 0, "min_size": 15,
            "batch_size": 1, "device": "mps",
        }:
            raise ValueError("Unvalidated Cellpose configuration")


def verify_procedure(p: Procedure) -> dict:
    python = local_path(str(Path(p.python).parent)) / Path(p.python).name
    # Resolve the venv's parent, not its Python symlink (which may point outside).
    if not (ROOT / p.python).is_file():
        raise ValueError(f"Missing interpreter for {p.plan_id}")
    verified = []
    for file in p.files:
        path = local_path(file.path)
        if not path.is_file() or sha256(path) != file.sha256:
            raise ValueError(f"Checkpoint missing or hash mismatch: {file.path}")
        verified.append(file.model_dump())
    return {"plan_id": p.plan_id, "python": str(python), "files": verified}


def eligible(catalog: Catalog, intent: Intent, probe: dict) -> tuple[list[Procedure], list[dict]]:
    accepted, rejected = [], []
    for p in catalog.procedures:
        reasons = []
        if intent.task != p.task:
            reasons.append("unsupported task")
        if intent.modality != p.modality:
            reasons.append("modality unconfirmed or incompatible")
        if not probe["replicated_grayscale"]:
            reasons.append("adapter only validated for replicated grayscale images")
        if not probe["usable_range"]:
            reasons.append("constant or near-binary image is outside validated input conditions")
        if reasons:
            rejected.append({"plan_id": p.plan_id, "reasons": reasons})
        else:
            accepted.append(p)
    return accepted, rejected


def rank(assessments, ids: list[str]) -> list[str]:
    if len(assessments) != len(ids) or {a.plan_id for a in assessments} != set(ids):
        raise ValueError("Every eligible procedure must receive exactly one Jev score")
    # Confidence is not an accuracy estimate and is deliberately not a tie-breaker.
    return [a.plan_id for a in sorted(assessments, key=lambda a: (-a.score, a.plan_id))]
