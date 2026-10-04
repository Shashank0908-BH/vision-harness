"""Launch frozen trials; credentials are read from .env only by the local process."""

import argparse
import json
import subprocess

from .prepare import REPORT, ROOT, TASKS, source_snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="test")
    parser.add_argument("--arms", nargs="+", choices=["vanilla", "full"], default=["vanilla", "full"])
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()
    report = REPORT if args.split == "test" else REPORT / args.split
    selection = json.loads((report / "selection.json").read_text())
    if args.split == "test" and source_snapshot() != selection["source_snapshot"]:
        raise ValueError("Source changed since test freeze; do not silently run a different implementation")
    toolchain = json.loads((report / "toolchain.json").read_text())
    actual = subprocess.check_output(["docker", "image", "inspect", toolchain["image"], "--format", "{{.Id}}"], text=True).strip()
    if actual != toolchain["digest"]:
        raise ValueError("Base image changed since freeze")
    for mode in args.arms:
        job = f"research-execution-{args.split}-{mode}"
        if (ROOT / "jobs" / job).exists():
            raise ValueError(f"Job already exists: {job}; inspect it instead of rerunning outcomes")
        command = [str(ROOT / ".venv/bin/harbor"), "run", "--path", str(TASKS / args.split),
            "--agent", "evals.research_execution.harbor_agent:ResearchExecutionAgent",
            "--agent-kwarg", f"mode={mode}", "--env-file", str(ROOT / ".env"),
            "--job-name", job, "--jobs-dir", str(ROOT / "jobs"),
            "--n-concurrent", str(args.concurrency), "--n-attempts", str(selection["repetitions"]),
            "--max-retries", "0", "--quiet"]
        if selection.get("development_prefix_replay"):
            if args.split == "test" or mode != "full":
                raise ValueError("Prefix replay is limited to full-arm development checks")
            command.extend(["--agent-kwarg", "development_replay=true"])
        print(json.dumps({"job": job, "mode": mode, "images": len(selection["filenames"]),
            "repetitions": selection["repetitions"], "concurrency": args.concurrency}), flush=True)
        with (report / f"{mode}-harbor.log").open("w") as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        print(json.dumps({"job": job, "status": "finished"}), flush=True)


if __name__ == "__main__":
    main()
