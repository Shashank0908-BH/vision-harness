"""Manage this project's one reusable workspace; never touches other projects."""

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
    ListSandboxesQuery,
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


def recorded(name):
    path = STATE / name
    return json.loads(path.read_text()) if path.exists() else None


def require_registered(name, resource):
    entry = recorded(name)
    if not entry or entry.get("id") != resource.id or entry.get("name") != resource.name:
        raise ValueError("Resource does not match this workspace's recorded ID and name; refusing to operate")


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
    require_registered("sandbox.json", box)
    return box


def info(box):
    return {k: getattr(box, k, None) for k in (
        "id", "name", "state", "target", "cpu", "memory", "disk", "gpu",
        "gpu_type", "auto_stop_interval", "auto_delete_interval", "auto_archive_interval", "labels",
    )}


def resources(cfg):
    values = dict(cpu=cfg["cpu"], memory=cfg["memory_gib"], disk=cfg["disk_gib"])
    if cfg.get("gpu_count", 0):
        values.update(gpu=cfg["gpu_count"], gpu_type=GpuType(cfg["gpu_type"]))
    return Resources(**values)


def build(daytona):
    cfg = config()
    try:
        snapshot = daytona.snapshot.get(cfg["snapshot"])
        require_registered("snapshot.json", snapshot)
        if str(snapshot.state) not in ("active", "SnapshotState.ACTIVE"):
            raise RuntimeError(f"Existing snapshot is {snapshot.state}; inspect before using it")
        print(json.dumps({"snapshot": snapshot.name, "state": snapshot.state}, default=str))
        return
    except DaytonaNotFoundError:
        pass
    previous = recorded("snapshot.json")
    if previous:
        try:
            daytona.snapshot.get(previous["id"])
        except DaytonaNotFoundError:
            pass
        else:
            raise RuntimeError("Project snapshot limit reached; reuse the recorded snapshot instead of creating another")
    STATE.mkdir(parents=True, exist_ok=True)

    def build_log(line):
        with (STATE / "build.log").open("a") as handle:
            handle.write(line + "\n")
        if any(word in line.lower() for word in ("step ", "error", "success", "done", "snapshot")):
            print(line[-400:], flush=True)

    snapshot = daytona.snapshot.create(CreateSnapshotParams(
        name=cfg["snapshot"], image=Image.from_dockerfile(HERE / "Dockerfile", strict_context=True),
        resources=resources(cfg),
    ), timeout=1800, on_logs=build_log)
    write("snapshot.json", {"name": snapshot.name, "id": snapshot.id, "state": snapshot.state})
    print(json.dumps({"snapshot": snapshot.name, "state": snapshot.state}, default=str))


def provision(daytona, *, base_image=False, without_volume=False):
    cfg = config()
    if without_volume and cfg.get("auto_stop_minutes") == 0:
        raise ValueError("The continuously running workspace requires its persistent volume")
    try:
        box = owned(daytona)
        print(json.dumps({"existing": info(box)}, default=str))
        return
    except DaytonaNotFoundError:
        pass
    current = list(daytona.list(ListSandboxesQuery(labels={"vision.owner": OWNER}), request_timeout=30))
    if len(current) >= cfg.get("max_project_sandboxes", 1):
        raise RuntimeError("Project sandbox limit reached. Reuse the existing worker or preserve its artifacts and clean it up first; no additional sandbox created.")
    mounts = []
    if not without_volume:
        try:
            volume = daytona.volume.get(cfg["volume"], create=False)
            require_registered("volume.json", volume)
        except DaytonaNotFoundError:
            volume = daytona.volume.create(cfg["volume"])
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
        public=False, auto_stop_interval=cfg["auto_stop_minutes"],
        auto_delete_interval=cfg.get("auto_delete_minutes", 0),
        auto_archive_interval=cfg.get("auto_archive_days", 7),
        ephemeral=cfg.get("ephemeral", True),
        spot=False,
        volumes=mounts,
    )
    if base_image:
        params = CreateSandboxFromImageParams(**common, image=cfg["base_image"],
            resources=resources(cfg))
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
        "mkdir -p /workspace/vision /persist/setup /persist/artifacts /persist/checkpoints /persist/scratch "
        "&& tar -xzf /tmp/vision-source.tar.gz -C /workspace/vision "
        "&& cp /tmp/vision-source.tar.gz /persist/setup/source.tar.gz "
        "&& cp /tmp/vision-source-manifest.json /persist/setup/source-manifest.json "
        "&& cp -rn /persist/checkpoints/. /opt/checkpoints/ "
        "&& cp -a /workspace/vision/models/stardist /opt/checkpoints/ "
        "&& cp -r /workspace/vision/models/stardist /persist/checkpoints/ "
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
    # Keep explicit `exit` inside a child shell so Daytona's session wrapper can
    # still observe completion and record the exit code.
    wrapped = "bash -lc " + shlex.quote(command)
    result = box.process.execute_session_command(name, SessionExecuteRequest(command=wrapped, run_async=True))
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
    parser.add_argument("action", choices=["build", "provision", "bootstrap", "status", "sync", "check", "exec", "run", "logs", "download", "idle", "start", "stop", "clean", "delete"])
    parser.add_argument("--command")
    parser.add_argument("--name", default="health")
    parser.add_argument("--remote")
    parser.add_argument("--local", type=Path)
    parser.add_argument("--minutes", type=int)
    parser.add_argument("--base-image", action="store_true", help="Create a bare worker; bootstrap packages separately")
    parser.add_argument("--without-volume", action="store_true", help="Temporary worker only: local disk is NOT durable")
    parser.add_argument("--apply", action="store_true", help="For clean: remove only the designated scratch contents")
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
        start_job(box, "bash /workspace/vision/infra/daytona/bootstrap.sh > /tmp/vision-bootstrap.log 2>&1; "
                  "vision_bootstrap_status=$?; cp /tmp/vision-bootstrap.log /persist/setup/bootstrap.log || exit 1; "
                  "exit $vision_bootstrap_status", "bootstrap")
    elif args.action == "sync":
        sync(box)
    elif args.action == "check":
        start_job(box, "( /opt/venvs/science/bin/python /workspace/vision/infra/daytona/smoke.py "
                  "&& cp -r /opt/checkpoints/. /persist/checkpoints/ ) > /tmp/vision-health.log 2>&1; "
                  "vision_health_status=$?; cp /tmp/vision-health.log /persist/setup/health.log || exit 1; "
                  "exit $vision_health_status", args.name)
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
    elif args.action == "start":
        if str(box.state).lower().split(".")[-1] != "started":
            box.start(timeout=120)
        print(json.dumps(info(box), default=str))
    elif args.action == "stop":
        if box.gpu:
            raise RuntimeError("GPU stop deletes its local filesystem; this command is for the persistent CPU workspace")
        box.stop(timeout=120)
        print("Stopped the CPU workspace; files and sandbox identity retained.")
    elif args.action == "clean":
        # One dedicated scratch directory only. No recursive cleanup of models,
        # source, logs, outputs, volumes or any parent directory.
        program = '''import json,pathlib,shutil
p=pathlib.Path('/persist/scratch')
assert not p.is_symlink(), 'Scratch root must not be a symlink'
p.mkdir(exist_ok=True)
items=list(p.iterdir())
print(json.dumps({'scratch_entries':[x.name for x in items], 'applied':APPLY}))
if APPLY:
    for x in items:
        if x.is_symlink() or x.is_file(): x.unlink()
        elif x.is_dir(): shutil.rmtree(x)
'''.replace("APPLY", str(args.apply))
        result = box.process.exec("python -c " + shlex.quote(program), timeout=30)
        print(result.result)
        if result.exit_code:
            raise RuntimeError("Scratch cleanup failed")
    elif args.action == "delete":
        daytona.delete(box, wait=True)
        print("Deleted this workspace; separately mounted persistent volume retained.")


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
