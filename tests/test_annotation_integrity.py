import numpy as np
import pytest

from evals.annotation_integrity import audit_instance_labels


def test_reused_id_is_flagged_without_silently_changing_count():
    labels = np.zeros((12, 12), dtype=np.uint16)
    labels[1:4, 1:4] = 600
    labels[7:10, 7:10] = 600
    result = audit_instance_labels(labels)
    assert result["unique_positive_ids"] == 1
    assert result["per_id_connected_components"] == 2
    assert result["requires_reference_review"]
    assert result["multipart_labels"] == [{"label": 600, "component_areas": [9, 9]}]


def test_tiny_fragment_is_not_automatically_a_new_nucleus():
    labels = np.zeros((12, 12), dtype=np.uint16)
    labels[1:5, 1:5] = 1
    labels[9, 9] = 1
    result = audit_instance_labels(labels)
    assert result["unique_positive_ids"] == 1
    assert result["multipart_labels"][0]["component_areas"] == [16, 1]
    assert result["requires_reference_review"]


def test_touching_distinct_labels_are_two_instances():
    labels = np.array([[0, 0, 0], [0, 1, 2]], dtype=np.uint16)
    result = audit_instance_labels(labels)
    assert result["unique_positive_ids"] == result["per_id_connected_components"] == 2
    assert not result["requires_reference_review"]


@pytest.mark.parametrize("labels", [np.array([1, 2]), np.array([[1.5]]), np.array([[-1]])])
def test_invalid_reference_rejected(labels):
    with pytest.raises(ValueError):
        audit_instance_labels(labels)
