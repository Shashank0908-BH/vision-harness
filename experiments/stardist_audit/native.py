"""Independent native StarDist audit on original TIFFs; no harness or LLM calls.

Run with .venv-stardist/bin/python. No annotation arrays are read by this script.
The three uniform spatial scales are post-benchmark diagnostics, not new test scores.
"""

import hashlib
import importlib.metadata
import json
import os
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/stardist-audit-20260922"
RUNS = ROOT / "runs/stardist-audit-native-20260922"
DATA = ROOT / "evals/datasets/generated/kromp-repeated-20260922"
OLD = ROOT / "runs/kromp-repeated-20260922"
VARIANTS = {
    "native-default": {"prob_thresh": None, "scale": None, "prior_id": "stardist-default"},
    "native-sensitive": {"prob_thresh": 0.35, "scale": None, "prior_id": "stardist-sensitive"},
    "native-conservative": {"prob_thresh": 0.6, "scale": None, "prior_id": "stardist-conservative"},
    "native-half": {"prob_thresh": None, "scale": 0.5, "prior_id": None},
    "native-quarter": {"prob_thresh": None, "scale": 0.25, "prior_id": None},
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    RUNS.mkdir(parents=True, exist_ok=False)
    REPORT.mkdir(parents=True, exist_ok=True)
    # Keep Keras writes in the already populated project cache.
    os.environ["KERAS_HOME"] = str(ROOT / ".model-cache/keras")
    os.environ["MPLCONFIGDIR"] = str(ROOT / ".model-cache/matplotlib")
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
    import tensorflow as tf
    from csbdeep.models.pretrained import get_model_details, get_model_folder
    from csbdeep.utils import normalize
    from stardist.models import StarDist2D

    tf.config.set_visible_devices([], "GPU")
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    rows = json.loads((DATA / "inputs.json").read_text())
    assert len(rows) == 37
    checkpoint = get_model_details(StarDist2D, "2D_versatile_fluo")[2]
    archive = ROOT / ".model-cache/keras/models/StarDist2D/2D_versatile_fluo/2D_versatile_fluo.zip"
    assert archive.exists(), (
        "Require existing official checkpoint archive; do not download silently"
    )
    actual_sha256 = digest(archive)
    assert actual_sha256 == checkpoint["hash"], "Archive differs from StarDist's registered SHA256"
    official_folder = get_model_folder(StarDist2D, "2D_versatile_fluo")
    files = {}
    for name in ["weights_best.h5", "config.json", "thresholds.json"]:
        official_hash = digest(official_folder / name)
        assert official_hash == digest(ROOT / "models/stardist" / name)
        files[name] = official_hash
    protocol = {
        "scope": "Post-benchmark integration/scale diagnostic, not independent capability evaluation",
        "cohort": "all 37 previously evaluated official Kromp test images",
        "repetitions": 3,
        "variants": VARIANTS,
        "total_fresh_inferences": 555,
        "normalization": {"pmin": 1, "pmax": 99.8, "axes": "YX", "clip": False},
        "scale_method": "StarDist predict_instances(scale=...) with original-coordinate output",
        "nms_threshold": "official checkpoint default; expect 0.3",
        "weights": files,
        "official_archive_sha256": actual_sha256,
        "registry": checkpoint,
        "input_manifest_sha256": digest(DATA / "inputs.json"),
        "audit_script_sha256": digest(__file__),
        "old_worker_sha256": digest(ROOT / "src/vision_harness/routing/worker.py"),
        "packages": {
            k: importlib.metadata.version(k)
            for k in ["stardist", "tensorflow", "csbdeep", "numpy", "pillow"]
        },
        "sources": [
            "https://github.com/stardist/stardist",
            "https://stardist.net/faq/",
            "https://www.ebi.ac.uk/biostudies/BioImages/studies/S-BIAD634",
        ],
        "annotations_available_to_inference": False,
        "fresh_inference_for_every_repetition": True,
    }
    write(REPORT / "protocol.json", protocol)
    records, inputs_audit = [], []
    start = time.monotonic()
    for repeat in range(1, 4):
        model = StarDist2D.from_pretrained("2D_versatile_fluo")
        assert model.thresholds.prob == 0.479071463157368 and model.thresholds.nms == 0.3
        for row in rows:
            original_path = DATA / "source/images" / row["source_filename"]
            assert digest(original_path) == row["source_sha256"]
            with Image.open(original_path) as im:
                assert im.n_frames == 1
                raw = np.asarray(im)
            if raw.ndim == 3:
                assert np.array_equal(raw[..., 0], raw[..., 1]) and np.array_equal(
                    raw[..., 0], raw[..., 2]
                )
                raw = raw[..., 0]
            assert raw.dtype == np.uint8 and raw.shape == (row["height"], row["width"])
            converted = np.asarray(Image.open(ROOT / row["image"]))
            assert converted.shape == (*raw.shape, 3)
            assert all(np.array_equal(raw, converted[..., c]) for c in range(3))
            assert digest(ROOT / row["image"]) == row["image_sha256"]
            normalized = normalize(raw, 1, 99.8)
            assert np.isfinite(normalized).all() and normalized.dtype == np.float32
            if repeat == 1:
                inputs_audit.append(
                    {
                        "id": row["id"],
                        "source_filename": row["source_filename"],
                        "raw_dtype": str(raw.dtype),
                        "shape": list(raw.shape),
                        "pixels_identical_to_harness": True,
                        "raw_percentiles_1_99p8": [float(x) for x in np.percentile(raw, [1, 99.8])],
                        "normalized_range": [float(normalized.min()), float(normalized.max())],
                    }
                )
            for name, parameters in VARIANTS.items():
                folder = RUNS / f"repeat-{repeat}" / row["id"] / name
                folder.mkdir(parents=True)
                before = time.monotonic()
                labels, details = model.predict_instances(
                    normalized,
                    axes="YX",
                    prob_thresh=parameters["prob_thresh"],
                    scale=parameters["scale"],
                )
                assert labels.shape == raw.shape
                np.savez_compressed(folder / "labels.npz", labels=labels)
                count = int(np.count_nonzero(np.unique(labels) > 0))
                result = {
                    "id": row["id"],
                    "source_filename": row["source_filename"],
                    "repeat": repeat,
                    "variant": name,
                    "count": count,
                    "details_object_count": len(details["prob"]),
                    "array_sha256": hashlib.sha256(labels.tobytes()).hexdigest(),
                    "elapsed_seconds": time.monotonic() - before,
                    "pixel_identical_to_prior": None,
                    "prior_count": None,
                }
                if parameters["prior_id"]:
                    prior_path = (
                        OLD
                        / f"repeat-{repeat}"
                        / row["id"]
                        / "routing/specialists"
                        / parameters["prior_id"]
                        / "labels.npz"
                    )
                    with np.load(prior_path, allow_pickle=False) as previous:
                        prior = previous["labels"]
                    result["pixel_identical_to_prior"] = bool(np.array_equal(labels, prior))
                    result["prior_count"] = int(np.count_nonzero(np.unique(prior) > 0))
                records.append(result)
                write(folder / "result.json", result)
            write(REPORT / "inference-progress.json", {"completed": len(records), "scheduled": 555})
            print(
                json.dumps(
                    {
                        "repeat": repeat,
                        "image": row["source_filename"],
                        "completed": len(records),
                        "elapsed_seconds": round(time.monotonic() - start, 1),
                    }
                ),
                flush=True,
            )
        del model
    write(REPORT / "input-audit.json", inputs_audit)
    write(REPORT / "native-results.json", records)
    write(
        RUNS / "inference-finished.json",
        {"executions": len(records), "elapsed_seconds": time.monotonic() - start},
    )
    print("Native audit inference complete.", flush=True)


if __name__ == "__main__":
    main()
