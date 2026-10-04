"""Standalone image-only process; uses only the selected specialist environment.

Invoked by absolute filename, not package import: the two heavy environments do
not need OpenAI, Jev, OpenCV, or the harness dependencies installed.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
import time
from pathlib import Path

import numpy as np
from PIL import Image


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    root = Path(request["root"])
    p = request["procedure"]
    output = Path(request["output"])
    for key in ("OPENAI_API_KEY", "JEV_API_KEY", "TYPESAFE_API_KEY"):
        if key in os.environ:
            raise ValueError("Worker must not inherit provider credentials")
    actual = {name: importlib.metadata.version(name) for name in p["packages"]}
    if actual != p["packages"]:
        raise ValueError(f"Specialist package versions changed: {actual}")
    for item in p["files"]:
        if digest(root / item["path"]) != item["sha256"]:
            raise ValueError("Pinned checkpoint changed")
    if digest(request["image"]) != request["image_sha256"]:
        raise ValueError("Input changed between planning and execution")
    rgb = np.asarray(Image.open(request["image"]).convert("RGB"))
    if not np.array_equal(rgb[..., 0], rgb[..., 1]) or not np.array_equal(rgb[..., 0], rgb[..., 2]):
        raise ValueError("Expected replicated grayscale")
    gray = rgb[..., 0]
    params = p["parameters"]
    start = time.monotonic()
    if p["adapter"] == "stardist":
        import tensorflow as tf
        from csbdeep.utils import normalize
        from stardist.models import StarDist2D

        tf.config.set_visible_devices([], "GPU")
        tf.config.threading.set_intra_op_parallelism_threads(params["threads"])
        tf.config.threading.set_inter_op_parallelism_threads(1)
        folder = (root / p["files"][0]["path"]).parent
        model = StarDist2D(config=None, name=folder.name, basedir=folder.parent)
        initialized = time.monotonic()
        labels, details = model.predict_instances(
            normalize(gray, *params["normalize_percentiles"]), axes="YX",
            prob_thresh=params["prob_thresh"], nms_thresh=params["nms_thresh"],
        )
        native = {"object_scores": details["prob"], "points": details["points"]}
        device = "cpu"
    elif p["adapter"] == "cellpose":
        import torch
        from cellpose import models

        if not torch.backends.mps.is_available():
            raise ValueError("This registered procedure requires MPS; no silent device substitution")
        torch.set_num_threads(6)
        model = models.CellposeModel(
            pretrained_model=str(root / p["files"][0]["path"]),
            device=torch.device("mps"), use_bfloat16=False,
        )
        initialized = time.monotonic()
        labels, flows, _ = model.eval(
            rgb, batch_size=params["batch_size"], channel_axis=-1, normalize=True,
            diameter=None, flow_threshold=params["flow_threshold"],
            cellprob_threshold=params["cellprob_threshold"], min_size=params["min_size"],
            do_3D=False, augment=False,
        )
        torch.mps.synchronize()
        native = {"cell_score": np.asarray(flows[2])}
        device = "mps"
    else:
        raise ValueError("Unregistered adapter")
    finished = time.monotonic()
    np.savez_compressed(output / "labels.npz", labels=labels)
    np.savez_compressed(output / "native-scores.npz", **native)
    result = {
        "packages": actual, "device": device,
        "initialization_seconds": initialized - start,
        "inference_seconds": finished - initialized,
        "image_sha256": request["image_sha256"],
        "labels_sha256": digest(output / "labels.npz"),
        "native_scores_sha256": digest(output / "native-scores.npz"),
    }
    (output / "worker-result.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
