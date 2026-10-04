"""Fixed pretrained StarDist control, with native uint16 input and no tuning."""

import argparse
import hashlib
import json
import time
import uuid
from pathlib import Path

import cv2
import numpy as np
import tensorflow as tf
from csbdeep.utils import normalize
from stardist.models import StarDist2D

from vision_harness.tracing import Trace, write_json


def run(output, query):
    if output.exists():
        raise ValueError("Fresh output directory required")
    output.mkdir(parents=True)
    (output / "artifacts").mkdir()
    (output / "artifacts/original.png").write_bytes(Path("/data/input.png").read_bytes())
    trace = Trace(output)
    started = time.monotonic()
    manifest = {"run_id": uuid.uuid4().hex, "mode": "stardist", "offline": False,
                "config": {"models": {"astra": "StarDist-2D_versatile_fluo"}},
                "elapsed_seconds": 0}
    trace.emit("input", {"question": query, "mode": "stardist"})
    answer = {"mode": "stardist", "status": "error", "count": None,
              "review_status": "not_applicable"}
    try:
        devices = tf.config.list_physical_devices("GPU")
        if not devices:
            raise RuntimeError("GPU unavailable; do not silently switch this control to CPU")
        for device in devices:
            tf.config.experimental.set_memory_growth(device, True)
        tf.keras.utils.set_random_seed(0)
        image = cv2.imread("/data/input.tif", cv2.IMREAD_UNCHANGED)
        if image.ndim != 2 or image.dtype != np.uint16:
            raise ValueError("Expected original 2D uint16 image")
        checkpoint = Path("/opt/checkpoints/stardist/weights_best.h5")
        checksum = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if checksum != "42202bd269c8106782316f1a2c75afb3f5ffa65e525c2e155ee0ced3a95da349":
            raise ValueError("Unexpected checkpoint")
        model = StarDist2D(config=None, name="stardist", basedir="/opt/checkpoints")
        normalized = normalize(image, 1, 99.8, axis=(0, 1))
        labels, _ = model.predict_instances(normalized, axes="YX", n_tiles=(1, 1),
                                           prob_thresh=0.479071463157368, nms_thresh=0.3)
        if labels.shape != image.shape:
            raise ValueError("Prediction changed input geometry")
        np.savez_compressed(output / "labels.npz", labels=labels)
        count = int(np.count_nonzero(np.unique(labels) > 0))
        trace.emit("fixed_inference", {"weights_sha256": checksum, "count": count,
            "normalization": "csbdeep.normalize raw uint16, p1/p99.8, axes YX, no clipping",
            "probability_threshold": 0.479071463157368, "nms_threshold": 0.3,
            "scaling": "native geometry", "tiling": [1, 1], "border_policy": "include",
            "variable_device": str(model.keras_model.weights[0].handle.device),
            "label_array_sha256": hashlib.sha256(labels.tobytes()).hexdigest()})
        answer.update(status="answered", count=count)
    except Exception as error:
        answer["error"] = f"{type(error).__name__}: {error}"
        trace.emit("error", {"message": answer["error"]})
    finally:
        manifest["elapsed_seconds"] = time.monotonic() - started
        write_json(output / "manifest.json", manifest)
        write_json(output / "answer.json", answer)
        trace.emit("answer", answer)
    return answer


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--query", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.query)))
