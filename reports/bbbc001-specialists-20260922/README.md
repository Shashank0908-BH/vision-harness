# BBBC001: standalone microscopy specialists

Six previously inspected development images; one fixed configuration per specialist. Counts are computed from instance masks. No Astra or Jev in the new runs. Historical Astra comparisons are reused from the explicitly linked earlier run, not new inference. This is native local execution, not a Harbor harness evaluation. BBBC001 has count labels but no instance masks here; segmentation precision/recall is not measured. StarDist had one metadata-only startup failure before inference; the preserved recovery record documents the fix. No prediction or threshold was changed.

| New specialist | Counts | Mean counting error ↓ | Mean inference time |
|---|---:|---:|---:|
| cellpose | 6/6 | 14.09% | 2.42 s |
| stardist | 6/6 | 6.67% | 0.14 s |

Inference time excludes dependency imports, model loading/downloads and artifact generation. Cold-start and total worker times are in each model.json. CPU and MPS differ; historical API runtimes are not directly comparable.

## Historical context

Source: [earlier three-mode run](../bbbc001-no-review-20260922/index.html).

- vanilla: 17.34% counting error
- tools: 16.16% counting error
- select: 14.27% counting error

## Per-image counts

| Image | Human mean | Historical vanilla | Cellpose-SAM | StarDist |
|---|---:|---:|---:|---:|
| BBBC001 field 1 | 356.0 | 395 | 387 | 375 |
| BBBC001 field 2 | 339.0 | 330 | 376 | 354 |
| BBBC001 field 3 | 421.5 | 495 | 497 | 456 |
| BBBC001 field 4 | 330.5 | 460 | 373 | 349 |
| BBBC001 field 5 | 465.5 | 565 | 572 | 529 |
| BBBC001 field 6 | 249.0 | 280 | 277 | 256 |

[Visual report](index.html) · [Protocol](protocol.json) · [Exact scores](scores.json)

Images: BBBC001v1, David Root and Anne Carpenter, CC BY-NC-SA 3.0. No settings were tuned against these counts.
