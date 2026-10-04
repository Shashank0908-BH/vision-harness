"""Development-only replay of a verified research/plan prefix; never a fresh trial."""

import hashlib
import json

from .contracts import Catalog, PlanSet, Task, UsageSet
from .planning import validate_plans

PREFIX_FILES = (
    "manifest.json", "task.json", "research-01/catalog.json", "research-01/retention.json",
    "research-01/candidate-scores.json", "research-01/documents/usage-contracts.json", "round-01/plans.json",
)


def load_prefix(directory, query, raw, settings, policy):
    identity = json.loads((directory / "identity.json").read_text())
    if hashlib.sha256(raw.read_bytes()).hexdigest() != identity["input_sha256"]:
        raise ValueError("Development prefix belongs to a different input image")
    for relative, expected in identity["artifact_hashes"].items():
        if relative not in PREFIX_FILES or hashlib.sha256((directory / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("Development prefix artifact changed")
    if set(identity["artifact_hashes"]) != set(PREFIX_FILES):
        raise ValueError("Incomplete development prefix")
    old = json.loads((directory / "manifest.json").read_text())
    if old["config"] != settings.model_dump() or old["policy"] != policy.model_dump():
        raise ValueError("Development prefix has different provider or investigation settings")
    task = Task.model_validate_json((directory / "task.json").read_text())
    if task.query != query:
        raise ValueError("Development prefix belongs to another query")
    catalog = Catalog.model_validate_json((directory / "research-01/catalog.json").read_text())
    assessment = json.loads((directory / "research-01/candidate-scores.json").read_text())
    expected = {f"{c.candidate_id}--{r}" for c in catalog.candidates for r in c.requirement_ids}
    if {a["plan_id"] for a in assessment["assessments"]} != expected:
        raise ValueError("Development prefix did not score every candidate-role pair")
    retention = json.loads((directory / "research-01/retention.json").read_text())
    selected = {c["candidate_id"] for c in retention["candidates"] if c["retained"]}
    candidates = [c for c in catalog.candidates if c.candidate_id in selected]
    usage = UsageSet.model_validate_json((directory / "research-01/documents/usage-contracts.json").read_text())
    plans = PlanSet.model_validate_json((directory / "round-01/plans.json").read_text())
    validate_plans(plans, task, candidates, usage)
    return task, candidates, usage, plans, identity
