"""No-provider isolation/inference plumbing check on an official validation input."""

import json
import os
import subprocess
from pathlib import Path

import numpy as np
import tensorflow as tf
import tifffile

for hidden in ("/root", "/persist", "/workspace", "/tests/reference.npz"):
    assert not Path(hidden).exists(), hidden
assert not any(k.startswith("DAYTONA_") or k in ("OPENAI_API_KEY", "JEV_API_KEY") for k in os.environ)
assert not any(int(p.name) > 100 for p in Path("/proc").iterdir() if p.name.isdigit()), "Parent processes visible"
readonly = Path("/opt/checkpoints/stardist/weights_best.h5")
with readonly.open("rb") as handle:
    assert handle.read(8), "Weights must be readable"
try:
    with readonly.open("r+b"):
        raise AssertionError("Shared weights are writable")
except OSError as exc:
    assert exc.errno in (13, 30), exc
assert tf.config.list_physical_devices("GPU")
with tf.device("/GPU:0"):
    result = tf.linalg.matmul(tf.ones((8, 8)), tf.ones((8, 8)))
assert "GPU" in result.device
torch_check = subprocess.check_output(["/opt/venvs/torch/bin/python", "-c",
    "import torch; assert torch.cuda.is_available(); x=torch.ones(8,device='cuda'); "
    "assert x.sum().item()==8; print(torch.cuda.get_device_name())"],
    env={k: v for k, v in os.environ.items() if k != "LD_LIBRARY_PATH"}, text=True)
raw = tifffile.imread("/data/input.tif")
np.savez_compressed("/output/labels.npz", labels=np.zeros(raw.shape, dtype=np.uint32))
Path("/output/answer.json").write_text(json.dumps({"mode": "full", "status": "answered", "count": 0}))
Path("/logs/agent/plumbing.json").write_text(json.dumps({"isolated": True, "tensorflow_gpu": result.device,
    "pytorch_gpu": torch_check.strip(), "shared_weights_readonly": True, "dummy_count": 0}, indent=2))
