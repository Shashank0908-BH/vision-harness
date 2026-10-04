"""Prepare an input-free Codex/scientific image. Never sends API credentials."""

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "evals/datasets/generated/research-execution-toolchain"
IMAGE = "vision-research-execution:20260922"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["build", "inspect", "health"])
    args = parser.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)
    if args.action == "health":
        from dotenv import load_dotenv

        from vision_harness.tracing import redact

        load_dotenv(ROOT / ".env", override=True)
        environment = os.environ.copy()
        environment["CODEX_API_KEY"] = environment["OPENAI_API_KEY"]
        result = subprocess.run(["docker", "run", "--rm", "-i", "-e", "CODEX_API_KEY", IMAGE,
            "codex", "exec", "--ignore-user-config", "--ephemeral", "--json",
            "--skip-git-repo-check", "--sandbox", "danger-full-access", "-m", "gpt-6-astra",
            "-c", 'model_reasoning_effort="low"', "-"],
            input="Run python -c 'print(40+2)' using the shell tool. Then answer only the observed number. Do not inspect environment variables or files.",
            env=environment, text=True, capture_output=True, timeout=150)
        (BUILD / "live-health.jsonl").write_text(redact(result.stdout))
        print(redact(result.stdout))
        print(redact(result.stderr)[-1500:])
        result.check_returncode()
        return
    if args.action == "build":
        shutil.copy2(Path(__file__).with_name("Dockerfile"), BUILD / "Dockerfile")
        shutil.copytree(ROOT / "models/stardist", BUILD / "models/stardist", dirs_exist_ok=True)
        started = time.monotonic()
        subprocess.run(["docker", "build", "-t", IMAGE, str(BUILD)], check=True)
        info = subprocess.check_output(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"], text=True).strip()
        (BUILD / "build.json").write_text(json.dumps({"image": IMAGE, "digest": info,
            "seconds": time.monotonic()-started, "inputs_or_labels_in_build": False}, indent=2)+"\n")
    command = ["docker", "run", "--rm", "--network", "none", IMAGE, "sh", "-c",
               "codex --version && python -c 'import stardist,tifffile,cv2; print(stardist.__version__)' && test ! -e /app && test ! -e /data"]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
