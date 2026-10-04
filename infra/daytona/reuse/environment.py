"""Harbor environments inside ONE existing GPU workspace, with private mounts.

No Daytona API calls occur here. Every exec has its own PID/mount/IPC namespace;
only this trial's files and read-only software/checkpoints are exposed.
"""

import asyncio
import json
import os
import shutil
import signal
import tempfile
from pathlib import Path

from harbor.environments.base import BaseEnvironment, ExecResult
from harbor.environments.capabilities import EnvironmentCapabilities


class WorkspaceEnvironment(BaseEnvironment):
    @staticmethod
    def type():
        return "vision-existing-workspace"

    @property
    def capabilities(self):
        return EnvironmentCapabilities(gpus=True, disable_internet=True)

    def _validate_definition(self):
        if not self.environment_dir.is_dir():
            raise ValueError("Missing frozen task directory")

    async def start(self, force_build=False):
        if os.getuid() != 0 or not Path("/opt/venvs/science/bin/python-gpu").exists():
            raise RuntimeError("This adapter runs only inside the registered GPU workspace")
        self.root = Path(tempfile.mkdtemp(prefix="vision-trial-", dir="/tmp"))
        self.processes = set()
        self.trial_paths.agent_dir.mkdir(parents=True, exist_ok=True)
        if self.environment_dir.name != "tests":
            (self.trial_paths.agent_dir / "workspace-location.json").write_text(json.dumps({"private_root": str(self.root)}))
        for name in ("data", "logs/agent", "logs/verifier", "logs/setup", "logs/artifacts", "output", "tests", "home/researcher", "tmp"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        for name in ("input.tif", "input.png"):
            source = self.environment_dir / name
            if source.exists():
                shutil.copyfile(source, self.root / "data" / name)
        if self.environment_dir.name == "tests":
            shutil.copytree(self.environment_dir, self.root / "tests", dirs_exist_ok=True)
        self.source = Path(os.environ["VISION_FROZEN_SOURCE"]).resolve()
        if (self.source / ".env").exists():
            raise RuntimeError("Credentials must never be included in frozen source")

    def local_path(self, path):
        path = Path(path)
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError("Transfers require an absolute path without traversal")
        if path.parts[1:2] not in [("data",), ("logs",), ("output",), ("tests",), ("home",), ("tmp",)]:
            raise ValueError(f"Transfer outside trial storage: {path}")
        result = self.root / str(path).lstrip("/")
        if not result.resolve().is_relative_to(self.root):
            raise ValueError("Transfer symlink escapes trial storage")
        return result

    async def upload_file(self, source_path, target_path):
        target = self.local_path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)

    async def upload_dir(self, source_dir, target_dir):
        shutil.copytree(source_dir, self.local_path(target_dir), dirs_exist_ok=True, symlinks=True)

    async def download_file(self, source_path, target_path):
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.local_path(source_path), target)

    async def download_dir(self, source_dir, target_dir):
        shutil.copytree(self.local_path(source_dir), target_dir, dirs_exist_ok=True, symlinks=True)

    def command(self, command, cwd):
        args = ["bwrap", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
                "--new-session", "--die-with-parent", "--cap-drop", "ALL"]
        if self._network_policy.network_mode.value == "no-network":
            args.append("--unshare-net")
        for name in ("usr", "etc", "opt", "sys"):
            args += ["--ro-bind", f"/{name}", f"/{name}"]
        for name in ("bin", "sbin", "lib", "lib64"):
            source = Path("/") / name
            if source.is_symlink():
                args += ["--symlink", os.readlink(source), f"/{name}"]
            elif source.exists():
                args += ["--ro-bind", str(source), str(source)]
        args += ["--proc", "/proc", "--dev", "/dev"]
        for device in Path("/dev").glob("nvidia*"):
            args += ["--dev-bind", str(device), str(device)]
        args += ["--ro-bind", "/.dockerenv", "/.dockerenv",
                 "--ro-bind", str(self.source), "/app"]
        for name in ("data", "logs", "output", "tests", "home", "tmp"):
            args += ["--bind", str(self.root / name), f"/{name}"]
        args += ["--chdir", cwd or "/app", "/bin/bash", "-c", command]
        return args

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        # Start from a clean environment: no Daytona key or coordinator secrets.
        environment = {"PATH": "/opt/venvs/science/bin:/usr/local/bin:/usr/bin:/bin",
                       "HOME": "/home/researcher", "TMPDIR": "/tmp",
                       "PYTHONPATH": "/home/researcher/packages:/app/src:/app",
                       "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1",
                       "PIP_TARGET": "/home/researcher/packages",
                       "UV_CACHE_DIR": "/home/researcher/.cache/uv",
                       "MPLCONFIGDIR": "/home/researcher/.cache/matplotlib"}
        environment.update(self._merge_env(env) or {})
        if any(name.startswith("DAYTONA_") for name in environment):
            raise ValueError("Daytona credentials may not enter a trial")
        process = await asyncio.create_subprocess_exec(*self.command(command, cwd), env=environment,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, start_new_session=True)
        self.processes.add(process)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
        finally:
            if process.returncode is None:
                os.killpg(process.pid, signal.SIGKILL)
                await process.wait()
            self.processes.discard(process)
        return ExecResult(stdout=stdout.decode(errors="replace"), stderr=stderr.decode(errors="replace"),
                          return_code=process.returncode)

    async def stop(self, delete=True):
        for process in list(getattr(self, "processes", [])):
            if process.returncode is None:
                os.killpg(process.pid, signal.SIGKILL)
                await process.wait()
        if delete and getattr(self, "root", None):
            shutil.rmtree(self.root)
