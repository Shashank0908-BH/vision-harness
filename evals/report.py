"""Report task outcomes, coverage and resource usage without conflating failures."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path


def summarize(jobs: Path) -> dict:
    groups = defaultdict(list)
    infrastructure_errors = []
    for result_path in sorted(jobs.glob("*/*/result.json")):
        result = json.loads(result_path.read_text())
        trial = result_path.parent
        manifest_path = trial / "agent/run/manifest.json"
        if not manifest_path.exists():
            infrastructure_errors.append(
                {"trial": str(trial), "exception": result.get("exception_info")}
            )
            continue
        manifest = json.loads(manifest_path.read_text())
        rewards = (result.get("verifier_result") or {}).get("rewards")
        events = [
            json.loads(line) for line in (trial / "agent/run/events.jsonl").read_text().splitlines()
        ]
        usage = [e["data"].get("usage") or {} for e in events if e["kind"] == "call_finished"]
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "config": manifest["config"],
                    "resources": manifest.get("resource_sha256"),
                    "versions": manifest.get("versions"),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:12]
        groups[(manifest["offline"], manifest["mode"], fingerprint)].append(
            {
                "trial": str(trial),
                "task": result.get("task_name"),
                "rewards": rewards,
                "elapsed_seconds": manifest["elapsed_seconds"],
                "status": manifest["status"],
                "input_tokens": sum(u.get("input_tokens", 0) for u in usage),
                "output_tokens": sum(u.get("output_tokens", 0) for u in usage),
                "provider_calls": len(usage),
                "cost_usd": None,
            }
        )
    rows = []
    for (offline, mode, fingerprint), trials in groups.items():
        n = len(trials)
        correct = sum((t["rewards"] or {}).get("accuracy", 0) for t in trials)
        answered = sum(t["status"] == "answered" for t in trials)
        rows.append(
            {
                "offline": offline,
                "mode": mode,
                "configuration_fingerprint": fingerprint,
                "trials": n,
                "accuracy_all_trials": correct / n,
                "coverage": answered / n,
                "accuracy_when_answered": correct / answered if answered else None,
                "mean_elapsed_seconds": sum(t["elapsed_seconds"] for t in trials) / n,
                "details": trials,
            }
        )
    return {
        "groups": rows,
        "infrastructure_errors": infrastructure_errors,
        "notes": [
            "Offline results validate plumbing only, never model performance.",
            "Cost is unknown until explicit versioned pricing is supplied; token usage is recorded.",
            "Small synthetic samples do not establish general visual ability.",
        ],
    }
