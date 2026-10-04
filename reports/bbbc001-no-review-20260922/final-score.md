# Requested comparison: tools and Jev selection

All 18 live trials returned numerical final counts. There were **no abstentions, timeouts or execution errors**. Jev answer review and the structured loop were disabled.

| Configuration | Counts returned | Mean counting error ↓ | Mean runtime |
|---|---:|---:|---:|
| Vanilla Astra | 6/6 | **17.34%** | 100.3 s |
| Astra + OpenCV | 6/6 | **16.16%** | 95.1 s |
| Astra + OpenCV + Jev selection | 6/6 | **14.27%** | 107.6 s |

**Jev selection has the lowest mean error in this run.** It reduces error by 3.07 percentage points versus vanilla and 1.89 points versus tools alone. These are percentage counting errors, not classification accuracy. “6/6” means six returned counts, not six correct answers.

Both tool modes are closer than vanilla on two images and worse on four. The average benefit is concentrated in field 4, where vanilla estimated 460 against reference 330.5, versus 370 with tools and 365 with selection. Selection beats tools alone on three images, loses on one, and ties on two.

All 12 tool-mode answers are visual estimates after segmentation produced one near-whole-image region. The scores therefore compare the complete workflows but do not establish a gain from measured cell segmentation. This is one attempt on six previously inspected images; earlier baseline scores are not substituted or pooled.

[Interactive report and all 18 traces](index.html) · [Per-image counts](README.md) · [Detailed findings](findings.md) · [Exact metrics](final-score.json)
