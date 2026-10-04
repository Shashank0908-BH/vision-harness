# StarDist integration, scale and reference audit

This is a post-benchmark audit, not a new held-out harness evaluation. It makes
no Astra or Jev API calls. Original predictions and reference TIFFs are preserved.
The [report](../../reports/stardist-audit-20260922/index.html) contains corrected
scores for every original arm and explicitly labeled scale diagnostics.

| File | Purpose |
|---|---|
| `native.py` | Check official weights and raw/converted pixel equality, then execute five native StarDist profiles on all 37 images, three times each. Does not open annotations. |
| `svg_audit.py` | Approximately rasterize the published SVG to check duplicate contours and one-to-one correspondence with TIFF regions. Does not use predictions. |
| `native_metrics.py` | Independently verify original TP/FP/FN using StarDist's own matcher and score the fresh masks with the reviewed reference. |
| `score.py` | Check reference integrity, repair only the fingerprinted disputed TIFF, rescore all saved arms and calculate exclusion/SVG sensitivities. |
| `report.py` | Render figures, all-image tables, three-repeat averages and the HTML report. |
| `../../evals/annotation_integrity.py` | Flag disconnected instance IDs for review without automatically turning every fragment into a nucleus. |

The original repeated-benchmark scripts remain frozen. Run commands from the
repository root. `native.py` refuses to reuse an existing output directory, so
use a separately named run/report root when deliberately repeating the audit.
Do not delete the current audit to rerun it. The original inference script hash
is recorded in `reports/stardist-audit-20260922/protocol.json`.

```sh
# Requires the existing .venv-stardist and already cached official checkpoint.
.venv-stardist/bin/python experiments/stardist_audit/native.py

# Published source vector annotation, also preserved in the report directory:
curl --fail --location --max-time 60 \
  https://ftp.ebi.ac.uk/biostudies/fire/S-BIAD/634/S-BIAD634/Files/dataset/groundtruth_svgs/otherspecimen_3.svg \
  --output /tmp/kromp-otherspecimen-3.svg

# System Python currently supplies fontTools, OpenCV, Pillow, NumPy, Matplotlib.
python3 experiments/stardist_audit/svg_audit.py
.venv-stardist/bin/python experiments/stardist_audit/native_metrics.py
.venv/bin/python -m experiments.stardist_audit.score
python3 experiments/stardist_audit/report.py
.venv/bin/pytest -q tests/test_annotation_integrity.py
```

Only `otherspecimen_3.tif` is repaired: 55 reused positive IDs represent 102
source-verified regions. Its foreground pixels are unchanged. The SVG contains
110 elements, six redundant elements and two contours absent from the TIFF;
the other 102 distinct contours map one-to-one to those TIFF regions. The paper
also reports 102 nuclei for the sole Wilms image. A separate sensitivity analysis
excludes the image, and another uses 104 as the count. The two tiny fragments in
`Ganglioneuroblastoma_8.tif` retain their original instance ID and do not become
extra nuclei. No disconnected-component heuristic is applied globally.

Half/quarter scales were proposed after viewing the original failures. They must
not be presented as predeclared test candidates. Calibrate a deployable scale
policy on development data, freeze it, then evaluate on new test data.
