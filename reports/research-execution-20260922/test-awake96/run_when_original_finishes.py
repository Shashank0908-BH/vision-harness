"""Run fresh controls now; start full trials after the original worker slots free."""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parents[2]
original = ROOT / "jobs/research-execution-test-full/result.json"

(REPORT / "started.json").write_text(json.dumps({
    "started_at_utc": datetime.now(timezone.utc).isoformat(),
    "started_at_local": datetime.now().astimezone().isoformat(),
    "concurrency": 4, "new_trials": 72,
    "schedule": "Fresh vanilla first; full waits for original full job to finish. Timing is observational under concurrent deployment load.",
}, indent=2) + "\n")
subprocess.run([sys.executable, "-m", "evals.research_execution.run",
                "--split", "test-awake96", "--arms", "vanilla", "--concurrency", "4"], cwd=ROOT, check=True)
while True:
    try:
        if json.loads(original.read_text()).get("finished_at"):
            break
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    time.sleep(20)

subprocess.run([sys.executable, "-m", "evals.research_execution.run",
                "--split", "test-awake96", "--arms", "full", "--concurrency", "4"], cwd=ROOT, check=True)
