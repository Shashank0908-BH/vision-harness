"""Infrastructure validation only. Synthetic tensors are NOT benchmark tasks."""

import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

OUT = Path("/persist/setup")


def emit(name, result):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"check": name, **result}), flush=True)


def stardist_check():
    import numpy as np
    import tensorflow as tf
    from stardist.models import StarDist2D

    devices = tf.config.list_physical_devices("GPU")
    assert devices, "TensorFlow has no GPU; CPU fallback is not a passing test"
    for device in devices:
        tf.config.experimental.set_memory_growth(device, True)
    with tf.device("/GPU:0"):
        matrix = tf.matmul(tf.ones((256, 256)), tf.ones((256, 256)))
    assert "GPU" in matrix.device and float(matrix[0, 0]) == 256.0
    model = StarDist2D(config=None, name="stardist", basedir="/opt/checkpoints")
    labels, _ = model.predict_instances(np.zeros((128, 128), dtype=np.float32), axes="YX")
    assert labels.shape == (128, 128) and labels.dtype.kind in "ui"
    checkpoint = Path("/opt/checkpoints/stardist/weights_best.h5")
    checksum = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    assert checksum == "42202bd269c8106782316f1a2c75afb3f5ffa65e525c2e155ee0ced3a95da349"
    emit("tensorflow-stardist", {"passed": True, "tensorflow": tf.__version__,
        "stardist": importlib.metadata.version("stardist"), "matmul_device": matrix.device,
        "model_variable_device": str(model.keras_model.weights[0].handle.device),
        "weights_sha256": checksum, "test": "128x128 zero-image forward pass; no accuracy claim"})


def torch_check():
    os.environ["CELLPOSE_LOCAL_MODELS_PATH"] = "/opt/checkpoints/cellpose"
    import numpy as np
    import torch
    from cellpose import models

    assert torch.cuda.is_available(), "PyTorch has no CUDA; CPU fallback is not a passing test"
    x = torch.ones((256, 256), device="cuda")
    y = x @ x
    torch.cuda.synchronize()
    assert y.is_cuda and y[0, 0].item() == 256.0
    model = models.CellposeModel(pretrained_model="cpsam_v2", device=torch.device("cuda"), use_bfloat16=False)
    assert next(model.net.parameters()).is_cuda
    labels, _, _ = model.eval(np.zeros((128, 128, 3), dtype=np.float32),
                             channel_axis=-1, batch_size=1, do_3D=False)
    assert labels.shape == (128, 128)
    checkpoint = Path(model.pretrained_model)
    emit("torch-cellpose", {"passed": True, "torch": torch.__version__,
        "cellpose": importlib.metadata.version("cellpose"), "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0), "vram_bytes": torch.cuda.get_device_properties(0).total_memory,
        "model_device": str(next(model.net.parameters()).device),
        "weights_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "test": "128x128 zero-image forward pass; no accuracy claim"})


def main():
    if len(sys.argv) > 1:
        {"stardist": stardist_check, "torch": torch_check}[sys.argv[1]]()
        return
    started = time.monotonic()
    OUT.mkdir(parents=True, exist_ok=True)
    nvidia = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], text=True).strip()
    cpu = Path("/sys/fs/cgroup/cpu.max").read_text().strip()
    memory = Path("/sys/fs/cgroup/memory.max").read_text().strip()
    assert cpu.split()[0] != "max" and int(cpu.split()[0]) / int(cpu.split()[1]) >= 8
    assert memory != "max" and int(memory) >= 32 * 1024**3
    emit("hardware", {"passed": True, "gpu": nvidia, "cpu_max": cpu, "memory_max": memory,
        "platform": platform.platform(), "disk_free_bytes": shutil.disk_usage("/").free,
        "persist_is_mount": os.path.ismount("/persist"), "dockerenv_present": Path("/.dockerenv").exists()})
    env = dict(os.environ, TF_CPP_MIN_LOG_LEVEL="2", TF_FORCE_GPU_ALLOW_GROWTH="true",
               OMP_NUM_THREADS="8", OPENBLAS_NUM_THREADS="8", MPLCONFIGDIR="/tmp/matplotlib")
    for kind, python in (("stardist", "/opt/venvs/science/bin/python-gpu"), ("torch", "/opt/venvs/torch/bin/python")):
        isolated_env = dict(env)
        isolated_env.pop("LD_LIBRARY_PATH", None)
        subprocess.run([python, __file__, kind], env=isolated_env, check=True, timeout=900)
    for name in ("science", "torch"):
        result = subprocess.check_output(["uv", "pip", "freeze", "--python", f"/opt/venvs/{name}/bin/python"], text=True)
        (OUT / f"{name}-installed.txt").write_text(result)
    emit("health", {"passed": True, "elapsed_seconds": round(time.monotonic()-started, 2),
        "benchmark_started": False, "provider_keys_required": False,
        "durable_storage_ready": os.path.ismount("/persist"),
        "cloud_harness_benchmark_ready": False})


if __name__ == "__main__":
    main()
