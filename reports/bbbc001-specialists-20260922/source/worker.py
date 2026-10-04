"""Image-only specialist worker. No reference counts or LLM credentials are read."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import resource
import time
import traceback
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def artifacts(gray, labels, output):
    if labels.shape != gray.shape or not np.issubdtype(labels.dtype, np.integer):
        raise ValueError("Expected an integer instance map in original image coordinates")
    if np.any(labels < 0):
        raise ValueError("Negative instance label")
    labels = labels.astype(np.int32)
    np.savez_compressed(output / "labels.npz", labels=labels)
    ids = np.unique(labels)
    ids = ids[ids > 0]
    overlay = np.repeat(gray[..., None], 3, axis=2).copy()
    objects = []
    for label in ids:
        ys, xs = np.where(labels == label)
        color = np.random.default_rng(int(label)).integers(64, 256, 3)
        mask = labels == label
        overlay[mask] = (0.55 * overlay[mask] + 0.45 * color).astype(np.uint8)
        objects.append(
            {
                "id": int(label),
                "area_pixels": int(len(xs)),
                "centroid_xy": [float(xs.mean()), float(ys.mean())],
                "box_xywh": [
                    int(xs.min()),
                    int(ys.min()),
                    int(xs.max() - xs.min() + 1),
                    int(ys.max() - ys.min() + 1),
                ],
                "touches_border": bool(
                    xs.min() == 0
                    or ys.min() == 0
                    or xs.max() == gray.shape[1] - 1
                    or ys.max() == gray.shape[0] - 1
                ),
            }
        )
    Image.fromarray(overlay).save(output / "overlay.png")
    numbered = Image.fromarray(overlay).resize((gray.shape[1] * 3, gray.shape[0] * 3))
    draw = ImageDraw.Draw(numbered)
    for obj in objects:
        x, y = obj["centroid_xy"]
        draw.text(
            (3 * x, 3 * y),
            str(obj["id"]),
            fill="white",
            stroke_width=1,
            stroke_fill="black",
            anchor="mm",
            font_size=16,
        )
    numbered.save(output / "numbered.png")
    areas = [obj["area_pixels"] for obj in objects]
    write(output / "instances.json", objects)
    return {
        "count": len(objects),
        "foreground_fraction": float(np.mean(labels > 0)),
        "median_area_pixels": float(np.median(areas)) if areas else None,
        "border_instances": sum(obj["touches_border"] for obj in objects),
        "largest_instance_fraction": max(areas, default=0) / labels.size,
        "labels_sha256": digest(output / "labels.npz"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["cellpose", "stardist"], required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[2]
    os.environ.setdefault("CELLPOSE_LOCAL_MODELS_PATH", str(root / ".model-cache/cellpose"))
    os.environ.setdefault("KERAS_HOME", str(root / ".model-cache/keras"))
    started = time.perf_counter()
    metadata = {
        "model": args.model,
        "worker_sha256": digest(__file__),
        "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        "target": "nuclei",
        "calibrated_count_confidence": None,
    }
    results = []
    try:
        if args.model == "cellpose":
            import torch
            from cellpose import models

            torch.set_num_threads(6)
            device = "mps" if torch.backends.mps.is_available() else "cpu"
            model = models.CellposeModel(
                pretrained_model="cpsam_v2", device=torch.device(device), use_bfloat16=False
            )
            parameters = {
                "batch_size": 1,
                "channel_axis": -1,
                "normalize": True,
                "diameter": None,
                "flow_threshold": 0.4,
                "cellprob_threshold": 0.0,
                "min_size": 15,
                "do_3D": False,
                "augment": False,
            }
            metadata.update(
                checkpoint="cpsam_v2",
                device=device,
                dtype="float32",
                parameters=parameters,
                weight_hashes={str(model.pretrained_model): digest(model.pretrained_model)},
            )

            def predict(gray):
                rgb = np.repeat(gray[..., None], 3, axis=-1)
                masks, flows, _ = model.eval(rgb, **parameters)
                if device == "mps":
                    torch.mps.synchronize()
                return masks, {"cell_score": np.asarray(flows[2])}
        else:
            import tensorflow as tf
            from csbdeep.utils import normalize
            from stardist.models import StarDist2D

            tf.config.set_visible_devices([], "GPU")
            tf.config.threading.set_intra_op_parallelism_threads(6)
            tf.config.threading.set_inter_op_parallelism_threads(2)
            model = StarDist2D.from_pretrained("2D_versatile_fluo")
            weights = Path(model.basedir) / model.name
            metadata.update(
                checkpoint="2D_versatile_fluo",
                device="cpu",
                dtype="float32",
                parameters={
                    "normalize_percentiles": [1, 99.8],
                    "thresholds": dict(model.thresholds._asdict()),
                    "axes": "YX",
                    "scale": None,
                },
                weight_hashes={str(p): digest(p) for p in weights.glob("*.h5")},
            )

            def predict(gray):
                masks, details = model.predict_instances(normalize(gray, 1, 99.8), axes="YX")
                return masks, {"object_scores": details["prob"], "points": details["points"]}

        metadata["initialization_seconds"] = time.perf_counter() - started
        write(args.output / "model.json", metadata)
        print(
            json.dumps({"event": "model_ready", "model": args.model, "device": metadata["device"]}),
            flush=True,
        )
        for item in json.loads(args.inputs.read_text()):
            output = args.output / item["id"]
            output.mkdir()
            result = {"id": item["id"], "input_sha256": item["sha256"]}
            try:
                path = Path(item["path"])
                if digest(path) != item["sha256"]:
                    raise ValueError("Input hash changed")
                rgb = np.asarray(Image.open(path).convert("RGB"))
                if not np.array_equal(rgb[..., 0], rgb[..., 1]) or not np.array_equal(
                    rgb[..., 0], rgb[..., 2]
                ):
                    raise ValueError("Expected replicated grayscale input")
                gray = rgb[..., 0]
                before = time.perf_counter()
                masks, scores = predict(gray)
                result["inference_seconds"] = time.perf_counter() - before
                np.savez_compressed(output / "native-scores.npz", **scores)
                result.update(artifacts(gray, masks, output))
                result["status"] = "answered"
                result["peak_process_rss_bytes"] = resource.getrusage(
                    resource.RUSAGE_SELF
                ).ru_maxrss
            except Exception:
                result.update(status="error", exception=traceback.format_exc())
            write(output / "result.json", result)
            results.append(result)
            write(args.output / "results.json", results)
            print(json.dumps(result), flush=True)
    except Exception:
        write(args.output / "failure.json", {"exception": traceback.format_exc()})
        raise
    metadata["worker_total_seconds"] = time.perf_counter() - started
    metadata["peak_process_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    write(args.output / "model.json", metadata)
    if any(row["status"] != "answered" for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
