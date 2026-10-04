# What this experiment establishes

**StarDist is the stronger next integration candidate on this development cohort.** It returned 375, 354, 456, 349, 529 and 256 nuclei, with 6.6662% mean counting error against the two-human mean. Cellpose-SAM returned 387, 376, 497, 373, 572 and 277, with 14.0862% error.

StarDist improves on Cellpose-SAM for all six images. Against the historical vanilla Astra counts from the immediately preceding comparison, StarDist improves five images and worsens one (field 2). Cellpose improves three and worsens three. The lower StarDist average is therefore not explained by a single favorable image, although six images remain too small for a broad claim.

Both specialists produce hundreds of distinct instances with small individual areas and foreground fractions of roughly 10–20%, rather than the single near-whole-image component from the original OpenCV adapter. The count is mechanically reproducible from the saved mask. This establishes useful structured output; it does not establish that every mask is biologically correct. Qualitative inspection of field 1 shows masks following many visible nuclei, with different treatment of touching and border objects. Mask precision, recall and split/merge rates require instance ground truth.

All counts from both specialists exceed the corresponding human mean. Possible contributors include false splits, small fragments, border handling and differences in annotation conventions. These are hypotheses, not measured diagnoses. No objects were removed and no thresholds were adjusted after seeing the labels. In field 5, the two human counts are 398 and 533; the reference mean is not a unanimous exact count.

## Runtime and recovery

StarDist ran on CPU: mean inference 0.1387 s/image, successful worker total 6.3961 s. Cellpose used MPS: mean inference 2.4175 s/image, worker total 54.4054 s including the first checkpoint download. The successful StarDist worker used its downloaded cache; its initial startup attempt failed in our metadata path lookup, before any predictions. That failure and the metadata-only repair are preserved in `stardist-startup-1.log`, `stardist-startup-1/failure.json` and `recovery.json`. These are not standardized cold-start benchmarks or direct latency comparisons with the historical API workflow.

## What remains untested

- Astra using StarDist measurements and whether it preserves or improves them.
- Jev selecting between specialist methods or improving final results through review.
- A larger held-out benchmark with instance masks and audited pretraining overlap.
- Calibration of native model scores or Jev judgments as confidence in count correctness.

The next controlled comparison should retain a standalone StarDist baseline alongside vanilla Astra, Astra plus StarDist, and Astra plus specialists with Jev selection. Reintroduce answer review as a separate condition and report both accuracy-related error and answer coverage. These native specialist trials do not replace the requested Harbor evaluation of the integrated harness.
