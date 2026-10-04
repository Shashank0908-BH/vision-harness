import numpy as np
import pytest

from evals.repeated.data import test_entries as select_entries
from evals.repeated.metrics import (
    bootstrap_mean,
    match_instances,
    numeric_answer,
    paired,
    summarize,
)


def test_same_count_can_hide_bad_segmentation():
    truth = np.array([[1, 1, 0, 2, 2], [1, 1, 0, 2, 2]], np.uint16)
    pred = np.array([[0, 3, 3, 3, 0], [0, 4, 4, 4, 0]], np.uint16)
    metric = match_instances(truth, pred)
    assert metric["truth_instances"] == metric["predicted_instances"] == 2
    assert metric["tp"] == 0 and metric["f1"] == 0


def test_instance_matching_ignores_label_numbers_and_matches_one_to_one():
    truth = np.array([[1, 1, 0, 9, 9]], np.uint16)
    pred = np.array([[7, 7, 0, 3, 3]], np.uint16)
    assert match_instances(truth, pred)["f1"] == 1
    merged = np.array([[2, 2, 0, 2, 2]], np.uint16)
    m = match_instances(truth, merged)
    assert m["tp"] == 1 and m["fn"] == 1 and m["fp"] == 0
    assert m["instance_matching_score"] == .5


def test_no_background_map_and_empty_predictions():
    truth = np.ones((3, 3), np.uint16)
    assert match_instances(truth, np.full_like(truth, 8))["tp"] == 1
    assert match_instances(truth, np.zeros_like(truth))["fn"] == 1
    with pytest.raises(ValueError):
        match_instances(truth, np.ones((2, 2), np.uint16))


def records():
    return [{"id": name, "repeat": n, "expected": 100, "values": {"a": val, "vanilla": 110}}
            for name, val in [("x", 100), ("y", 80)] for n in (1, 2, 3)]


def test_repeated_summaries_do_not_pretend_six_calls_are_six_images():
    summary = summarize(records(), "a")
    assert summary["mape_percent"] == 10
    assert summary["run_mape_sd"] == 0
    assert summary["image_cluster_mape_interval_complete_images_only"]["image_clusters"] == 2
    assert summary["all_attempt_success_at_10_percent"] == .5


def test_missing_answers_reduce_success_without_changing_denominator():
    rows = records()
    rows[0]["values"]["a"] = None
    summary = summarize(rows, "a")
    assert summary["mape_percent"] is None
    assert summary["completed"] == 5 and summary["attempts"] == 6
    assert summary["all_attempt_success_at_10_percent"] == 2/6
    assert summary["complete_images"] == 1
    comparison = paired(rows, "a")
    assert comparison["error_difference_pp_complete_paired_images"]["image_clusters"] == 1
    assert comparison["all_attempt_success_difference_pp"]["image_clusters"] == 2


def test_bootstrap_reproducible_and_numeric_answer_not_error_value():
    assert bootstrap_mean([1, 2, 3]) == bootstrap_mean([1, 2, 3])
    assert numeric_answer({"status": "error", "value": 10}) is None
    assert numeric_answer({"status": "answered", "value": "10"}) is None
    assert numeric_answer({"status": "answered", "value": float('nan')}) is None


def test_official_test_cohort_cannot_silently_change():
    rows=[{"path": str(i), "attributes": [{"name": "Train-/Testset split", "value": "test"}]} for i in range(37)]
    assert len(select_entries(rows)) == 37
    with pytest.raises(ValueError):
        select_entries(rows[:-1])


def test_fixed_completion_preserves_failed_harness_and_never_retries_attempted_tool(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    import cv2

    from evals.repeated.runner import complete_fixed
    from vision_harness.artifacts import ArtifactStore
    from vision_harness.tracing import Trace, write_json

    image = tmp_path / 'image.png'
    cv2.imwrite(str(image), np.arange(100, dtype=np.uint8).reshape(10, 10))
    directory = tmp_path / 'route'
    store = ArtifactStore(directory)
    store.import_image(image)
    trace = Trace(directory)
    trace.emit('error', {'stage': 'jev_selection'})
    original = {'status': 'error', 'value': None, 'stage': 'jev_selection'}
    write_json(directory / 'answer.json', original)
    (directory / 'specialists' / 'failed').mkdir(parents=True)
    called = []

    def execute(p, store, trace, directory):
        called.append(p.plan_id)
        return {'count': 4}

    monkeypatch.setattr('evals.repeated.runner.locked_execute', execute)
    catalog = SimpleNamespace(procedures=[SimpleNamespace(plan_id='failed'), SimpleNamespace(plan_id='unattempted')])
    complete_fixed(directory, catalog)
    assert called == ['unattempted']
    assert json.loads((directory / 'answer.json').read_text()) == original
    assert json.loads((directory / 'fixed-completion.json').read_text())['statuses']['failed'] == 'error_preserved_without_retry'
