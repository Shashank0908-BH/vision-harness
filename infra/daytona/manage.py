"""Manage only this project's isolated GPU lab; never touches other sandboxes."""

import argparse
import hashlib
import json
import os
import shlex
import sys
import tarfile
import time
import tomllib
from pathlib import Path

from daytona import (
    CreateSandboxFromImageParams,
    CreateSandboxFromSnapshotParams,
    CreateSnapshotParams,
    Daytona,
    DaytonaConfig,
    GpuType,
    Image,
    Resources,
    SessionExecuteRequest,
    VolumeMount,
)
from daytona.common.errors import DaytonaNotFoundError
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
STATE = ROOT / "runs/daytona"
OWNER = "vision-lab-20260923"


def write(name, value):
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / name).write_text(json.dumps(value, indent=2, default=str) + "\n")


def config():
    return tomllib.loads((HERE / "config.toml").read_text())


def client():
    values = dotenv_values(ROOT / ".env")
    key = values.get("DAYTONA_API_KEY") or os.environ.get("DAYTONA_API_KEY")
    if not key:
        raise ValueError("DAYTONA_API_KEY is not set in .env")
    return Daytona(DaytonaConfig(api_key=key, api_url=values.get("DAYTONA_API_URL") or "https://app.daytona.io/api"))


def owned(daytona):
    box = daytona.get(config()["name"])
    if box.labels.get("vision.owner") != OWNER:
        raise ValueError("Sandbox ownership label mismatch; refusing to operate")
    return box


def info(box):
    return {k: getattr(box, k, None) for k in (
        "id", "name", "state", "target", "cpu", "memory", "disk", "gpu",
        "gpu_type", "auto_stop_interval", "auto_delete_interval", "labels",
    )}


def build(daytona):
    cfg = config()
    try:
        snapshot = daytona.snapshot.get(cfg["snapshot"])
        if str(snapshot.state) not in ("active", "SnapshotState.ACTIVE"):
            raise RuntimeError(f"Existing snapshot is {snapshot.state}; inspect before using it")
        print(json.dumps({"snapshot": snapshot.name, "state": snapshot.state}, default=str))
        return
    except DaytonaNotFoundError:
        pass
    STATE.mkdir(parents=True, exist_ok=True)

    def build_log(line):
        with (STATE / "build.log").open("a") as handle:
            handle.write(line + "\n")
        if any(word in line.lower() for word in ("step ", "error", "success", "done", "snapshot")):
            print(line[-400:], flush=True)

    snapshot = daytona.snapshot.create(CreateSnapshotParams(
        name=cfg["snapshot"], image=Image.from_dockerfile(HERE / "Dockerfile", strict_context=True),
        resources=Resources(cpu=cfg["cpu"], memory=cfg["memory_gib"], disk=cfg["disk_gib"],
                            gpu=cfg["gpu_count"], gpu_type=GpuType(cfg["gpu_type"])),
    ), timeout=1800, on_logs=build_log)
    write("snapshot.json", {"name": snapshot.name, "id": snapshot.id, "state": snapshot.state})
    print(json.dumps({"snapshot": snapshot.name, "state": snapshot.state}, default=str))


def provision(daytona, *, base_image=False, without_volume=False):
    cfg = config()
    try:
        box = owned(daytona)
        print(json.dumps({"existing": info(box)}, default=str))
        return
    except DaytonaNotFoundError:
        pass
    mounts = []
    if not without_volume:
        volume = daytona.volume.get(cfg["volume"], create=True)
        deadline = time.monotonic() + 120
        while str(volume.state) not in ("ready", "VolumeState.READY"):
            if time.monotonic() > deadline:
                raise TimeoutError("Persistent volume did not become ready")
            time.sleep(2)
            volume = daytona.volume.get(cfg["volume"])
        write("volume.json", {"id": volume.id, "name": cfg["volume"]})
        mounts = [VolumeMount(volume_id=volume.id, mount_path="/persist", subpath="lab")]
    print(json.dumps({"stage": "build_and_provision", "resources": cfg}), flush=True)

    common = dict(name=cfg["name"],
        labels={"vision.owner": OWNER, "vision.role": "experimentation-lab"},
        public=False, auto_stop_interval=cfg["auto_stop_minutes"], auto_delete_interval=0,
        volumes=mounts,
    )
    if base_image:
        params = CreateSandboxFromImageParams(**common, image=cfg["base_image"],
            resources=Resources(cpu=cfg["cpu"], memory=cfg["memory_gib"], disk=cfg["disk_gib"],
                                gpu=cfg["gpu_count"], gpu_type=GpuType(cfg["gpu_type"])))
    else:
        params = CreateSandboxFromSnapshotParams(**common, snapshot=cfg["snapshot"])
    box = daytona.create(params, timeout=600)
    write("sandbox.json", info(box))
    print(json.dumps(info(box), default=str), flush=True)


def sync(box):
    # Explicit allowlist: no .env, histories, jobs, datasets, labels, or .git.
    paths = []
    for name in ("src", "evals", "prompts", "configs", "infra/daytona"):
        for path in (ROOT / name).rglob("*"):
            relative = path.relative_to(ROOT)
            if (path.is_file() and not path.is_symlink()
                    and path.suffix in (".py", ".toml", ".md", ".json", ".in", ".lock", ".sh")
                    and not any(part in ("generated", "__pycache__", "datasets", "tasks") for part in relative.parts)):
                paths.append(path)
    paths.extend([ROOT / "pyproject.toml", ROOT / "README.md"])
    paths.extend(p for p in (ROOT / "models/stardist").iterdir() if p.is_file())
    manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    write("source-manifest.json", manifest)
    archive = STATE / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for path in paths:
            bundle.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    box.fs.upload_file(str(archive), "/tmp/vision-source.tar.gz")
    box.fs.upload_file((STATE / "source-manifest.json").read_bytes(), "/tmp/vision-source-manifest.json")
    result = box.process.exec(
        "mkdir -p /workspace/vision /persist/setup /persist/artifacts /persist/checkpoints "
        "&& tar -xzf /tmp/vision-source.tar.gz -C /workspace/vision "
        "&& cp /tmp/vision-source.tar.gz /persist/setup/source.tar.gz "
        "&& cp /tmp/vision-source-manifest.json /persist/setup/source-manifest.json "
        "&& cp -a /workspace/vision/models/stardist /opt/checkpoints/ "
        "&& cp -a /workspace/vision/models/stardist /persist/checkpoints/ "
        "&& uv pip install --python /opt/venvs/science/bin/python --no-deps -e /workspace/vision "
        "&& /opt/venvs/science/bin/python -m vision_harness.research_execution.cli --help "
        "&& codex --version && /opt/venvs/science/bin/harbor --version", timeout=180)
    print(result.result)
    if result.exit_code:
        raise RuntimeError(f"Sync validation exited {result.exit_code}")
    manifest_check = box.process.exec(
        "/opt/venvs/science/bin/python -c " + shlex.quote(
            "import hashlib,json,pathlib; r=pathlib.Path('/workspace/vision'); "
            "m=json.load(open('/persist/setup/source-manifest.json')); "
            "assert all(hashlib.sha256((r/p).read_bytes()).hexdigest()==h for p,h in m.items()); "
            "assert not (r/'.env').exists(); print('Source hashes match; no .env uploaded')"
        ), timeout=30)
    if manifest_check.exit_code:
        raise RuntimeError(manifest_check.result)
    print(manifest_check.result)
    write("sync.json", {"files": len(paths), "source_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "exit_code": result.exit_code})


def start_job(box, command, name):
    if not name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Job names must contain only letters, numbers, hyphens or underscores")
    box.process.create_session(name)
    result = box.process.execute_session_command(name, SessionExecuteRequest(command=command, run_async=True))
    job = {"sandbox_id": box.id, "session_id": name, "command_id": result.cmd_id, "command": command}
    write(f"job-{name}.json", job)
    print(json.dumps(job), flush=True)


def job_status(box, name):
    job = json.loads((STATE / f"job-{name}.json").read_text())
    if job["sandbox_id"] != box.id:
        raise ValueError("Job belongs to a different sandbox")
    command = box.process.get_session_command(name, job["command_id"])
    logs = box.process.get_session_command_logs(name, job["command_id"])
    text = (logs.stdout or "") + (logs.stderr or "")
    (STATE / f"job-{name}.log").write_text(text)
    print(json.dumps({"exit_code": command.exit_code, "session": name}))
    print(text[-9000:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "provision", "bootstrap", "status", "sync", "check", "exec", "run", "logs", "download", "idle", "delete"])
    parser.add_argument("--command")
    parser.add_argument("--name", default="health")
    parser.add_argument("--remote")
    parser.add_argument("--local", type=Path)
    parser.add_argument("--minutes", type=int)
    parser.add_argument("--base-image", action="store_true", help="Create a bare worker; bootstrap packages separately")
    parser.add_argument("--without-volume", action="store_true", help="Temporary worker only: local disk is NOT durable")
    args = parser.parse_args()
    daytona = client()
    if args.action == "build":
        build(daytona)
        return
    if args.action == "provision":
        provision(daytona, base_image=args.base_image, without_volume=args.without_volume)
        return
    box = owned(daytona)
    if args.action == "status":
        print(json.dumps(info(box), indent=2, default=str))
    elif args.action == "bootstrap":
        result = box.process.exec("mkdir -p /workspace/vision/infra/daytona /persist/setup", timeout=30)
        if result.exit_code:
            raise RuntimeError(result.result)
        for name in ("science.lock", "torch.lock", "bootstrap.sh", "configure_cuda.py"):
            box.fs.upload_file(str(HERE / name), f"/workspace/vision/infra/daytona/{name}")
        start_job(box, "bash /workspace/vision/infra/daytona/bootstrap.sh > /persist/setup/bootstrap.log 2>&1", "bootstrap")
    elif args.action == "sync":
        sync(box)
    elif args.action == "check":
        start_job(box, "/opt/venvs/science/bin/python /workspace/vision/infra/daytona/smoke.py > /persist/setup/health.log 2>&1", args.name)
    elif args.action == "exec":
        if not args.command:
            parser.error("--command is required")
        result = box.process.exec(args.command, timeout=55)
        print(result.result)
        raise SystemExit(result.exit_code)
    elif args.action == "run":
        if not args.command:
            parser.error("--command is required")
        durable = box.process.exec("mountpoint -q /persist", timeout=15)
        if durable.exit_code:
            raise RuntimeError("Long jobs require the persistent /persist volume; current worker is temporary")
        start_job(box, "bash -lc " + shlex.quote(args.command), args.name)
    elif args.action == "logs":
        job_status(box, args.name)
    elif args.action == "download":
        if not args.remote or not args.local:
            parser.error("--remote and --local are required")
        args.local.parent.mkdir(parents=True, exist_ok=True)
        box.fs.download_file(args.remote, str(args.local))
        print(str(args.local))
    elif args.action == "idle":
        if args.minutes is None or args.minutes < 0:
            parser.error("--minutes must be nonnegative; 0 disables idle shutdown")
        box.set_autostop_interval(args.minutes)
        print(json.dumps({"auto_stop_minutes": args.minutes}))
    elif args.action == "delete":
        daytona.delete(box, wait=True)
        print("Deleted this GPU worker; persistent volume retained.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        message = str(error)
        for key, value in dotenv_values(ROOT / ".env").items():
            if value and any(word in key.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
                message = message.replace(value, "[REDACTED]")
        print(f"{type(error).__name__}: {message}", file=sys.stderr)
        raise SystemExit(1) from None
