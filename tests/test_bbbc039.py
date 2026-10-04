import numpy as np
import pytest

from evals.import_bbbc039 import decode_labels, to_display
from evals.scoring import score


def test_annotation_decoder_separates_equal_value_components_and_touching_values():
    rgb = np.zeros((8, 10, 3), np.uint8)
    rgb[1:3, 1:3, 0] = 100
    rgb[1:3, 3:5, 0] = 200  # touching but distinct annotation value
    rgb[5:7, 1:3, 0] = 100  # reused color, distinct component
    rgb[..., 1] = 50  # the official decoder uses the red channel only
    labels = decode_labels(rgb)
    assert len(np.unique(labels[labels > 0])) == 3
    assert labels[1, 2] != labels[1, 3]
    assert labels[1, 1] != labels[5, 1]
    assert np.count_nonzero(labels) == 12


def test_fixed_display_mapping_and_derived_count_scoring():
    image = np.arange(10000, dtype=np.uint16).reshape(100, 100)
    display, bounds = to_display(image)
    assert display.dtype == np.uint8 and display.shape == image.shape
    assert bounds == pytest.approx(np.percentile(image, [1, 99.8]))
    assert display[0, 0] == 0 and display[-1, -1] == 255
    assert np.all(np.diff(display.ravel().astype(int)) >= 0)
    target = {"expected": 100, "metric": "nuclei_count_percentage_error"}
    assert score({"status": "answered", "value": 110}, target)["percentage_error"] == 10
    assert "percentage_error" not in score({"status": "abstained", "value": 110}, target)
