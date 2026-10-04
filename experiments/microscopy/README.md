# Standalone microscopy experiment

This measures specialist perception before integrating it into the Astra/Jev harness. It runs locally in isolated environments, not inside Harbor. No API credentials are needed.

| File | Responsibility |
|---|---|
| `worker.py` | Loads one checkpoint, receives image-only inputs, saves integer instance maps, native scores, per-instance geometry, overlays, timings and model hashes. Never reads reference counts. |
| `evaluate.py` | Freezes the six existing BBBC001 inputs and source files, invokes workers sequentially, independently recounts saved masks, scores with the existing verifier, and creates HTML/Markdown reports. |
| `requirements-*.txt` | Direct pinned model dependencies for separate environments. |
| `lock-*.txt` | Exact installed dependency versions on this Apple Silicon machine. |

Run from the repository root:

```sh
uv venv --python 3.12 .venv-cellpose
uv pip install --python .venv-cellpose/bin/python -r experiments/microscopy/lock-cellpose.txt
uv venv --python 3.12 .venv-stardist
uv pip install --python .venv-stardist/bin/python -r experiments/microscopy/lock-stardist.txt
.venv/bin/python experiments/microscopy/evaluate.py reports/NEW_REPORT_DIRECTORY
```

The output directory must be new. Rebuild a report without repeating inference using `--report-only`.

Cellpose uses `cpsam_v2`, float32, batch size one, original geometry, built-in normalization and default segmentation thresholds. MPS is selected if available, otherwise CPU. StarDist uses `2D_versatile_fluo`, CPU, percentile normalization 1/99.8 and its pretrained thresholds. Count all distinct positive instance IDs, including border objects. No parameters are selected using reference counts.

Each report saves `protocol.json`, `cohort.json`, image-only `inputs.json`, source snapshots, subprocess logs, per-model metadata, per-image artifacts, independent `scores.json`, and the visual report. Local paths and model cache paths are provenance, not secrets. The worker is an image-only interface, not an operating-system sandbox: it runs under the same local user and can technically access the workspace.

The earlier Astra/OpenCV/Jev comparison is explicitly historical and hash-pinned. It is not rerun or pooled with older baselines. The six images are development data already inspected in this project; successful results require a larger held-out evaluation before claiming general improvement. Native mask scores are not calibrated count confidence. Process RSS on macOS is reported in bytes and does not fully describe accelerator memory. Timing excludes imports/loading and artifact creation unless labeled total worker time.
