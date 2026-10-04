"""Apply TensorFlow's documented pip CUDA-library links inside its own venv.

https://www.tensorflow.org/install/pip#6_gpu_only_virtual_environment_configuration
Run with /opt/venvs/science/bin/python, never the host/project interpreter.
"""

import os
import shlex
import sys
import sysconfig
from pathlib import Path

if Path(sys.prefix) != Path("/opt/venvs/science"):
    raise SystemExit("This helper is restricted to the remote scientific environment")

site = Path(sysconfig.get_paths()["purelib"])
target = site / "tensorflow"
assert target.is_dir()
linked = 0
for source in sorted((site / "nvidia").glob("*/lib/*.so*")):
    destination = target / source.name
    if destination.is_symlink():
        destination.unlink()
    elif destination.exists():
        continue
    destination.symlink_to(os.path.relpath(source, target))
    linked += 1
ptxas = next(iter((site / "nvidia").glob("*/bin/ptxas")), None)
if ptxas:
    destination = Path(sys.prefix) / "bin/ptxas"
    if destination.is_symlink():
        destination.unlink()
    if not destination.exists():
        destination.symlink_to(ptxas)
print(f"Configured {linked} TensorFlow CUDA library links; ptxas present: {bool(ptxas)}")
libraries = ":".join(str(p) for p in sorted((site / "nvidia").glob("*/lib")))
wrapper = Path(sys.prefix) / "bin/python-gpu"
wrapper.write_text(
    "#!/bin/sh\n"
    f"export LD_LIBRARY_PATH={shlex.quote(libraries)}\"${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}\"\n"
    f"export PATH={shlex.quote(str(Path(sys.prefix) / 'bin'))}:\"$PATH\"\n"
    f"exec {shlex.quote(str(Path(sys.prefix) / 'bin/python'))} \"$@\"\n"
)
wrapper.chmod(0o755)
print(f"GPU-aware Python entry point: {wrapper}")
