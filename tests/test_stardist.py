import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from vision_harness.artifacts import ArtifactStore
from vision_harness.contracts import Arguments, CandidatePlan, Step
from vision_harness.review_loop import operation_keys
from vision_harness.tools import stardist
from vision_harness.tools.registry import Registry


def step(profile="default", **kwargs):
    fields = {k: None for k in Arguments.model_fields}
    fields.update(segmentation_profile=profile, **kwargs)
    return Step(
        step_id="segment", tool="stardist", input_ref="original", arguments=Arguments(**fields)
    )


def plan(item):
    return CandidatePlan(
        plan_id="nuclei",
        description="segment nuclei",
        assumptions=[],
        intended_output="count",
        steps=[item],
    )


def test_specialist_registry_and_operation_identity():
    registry = Registry(Path("configs/capabilities-stardist.toml"))
    registry.validate(plan(step()), 3)
    with pytest.raises(ValueError, match="not used"):
        registry.validate(plan(step(color="any")), 3)
    with pytest.raises(ValueError, match="requires"):
        registry.validate(plan(step(None)), 3)
    assert operation_keys(plan(step())) != operation_keys(plan(step("sensitive")))
    renamed = plan(step())
    renamed.steps[0].step_id = "renamed"
    assert set(operation_keys(renamed).values()) == set(operation_keys(plan(step())).values())


def test_mask_derived_count_and_profile_thresholds(tmp_path, monkeypatch):
    utils = ModuleType("csbdeep.utils")
    utils.normalize = lambda image, *args: image
    monkeypatch.setitem(sys.modules, "csbdeep.utils", utils)
    labels = np.zeros((12, 16), np.int32)
    labels[:2, :2] = 7
    labels[4:7, 5:8] = 91
    observed = []

    def predict(image, **kwargs):
        observed.append(kwargs)
        return labels, {"prob": np.array([0.7, 0.8])}

    monkeypatch.setattr(
        stardist,
        "load_model",
        lambda: SimpleNamespace(
            thresholds=SimpleNamespace(prob=0.479071463157368), predict_instances=predict
        ),
    )
    monkeypatch.setattr(stardist.importlib.metadata, "version", lambda _: "test")
    store = ArtifactStore(tmp_path)
    store.save(np.full((12, 16, 3), 60, np.uint8), "original")
    result = stardist.execute(step(), "original", "n", store)
    assert result.measurements["instance_count"] == 2
    assert result.measurements["border_instance_count"] == 1
    assert result.measurements["full_original_coverage"] is True
    objects = json.loads((tmp_path / result.measurements["instances_path"]).read_text())
    assert {o["id"] for o in objects} == {7, 91}
    assert [o["area_pixels"] for o in objects] == [4, 9]
    assert np.array_equal(
        np.load(tmp_path / result.measurements["raw_labels_path"])["labels"], labels
    )
    assert observed[0]["prob_thresh"] == pytest.approx(0.479071463157368)
    stardist.execute(step("sensitive"), "original", "s", store)
    assert observed[1]["prob_thresh"] == 0.35
    store.save(np.full((12, 16, 3), 60, np.uint8), "cropped", (5, 9))
    cropped = stardist.execute(step("conservative"), "cropped", "c", store)
    assert observed[2]["prob_thresh"] == 0.60
    assert cropped.measurements["full_original_coverage"] is False
    assert cropped.coordinate_system["original_offset"] == [5, 9]
    assert store.records[cropped.primary_artifact_id]["origin"] == [5, 9]
    with pytest.raises(ValueError, match="not a mask"):
        stardist.execute(step(), result.primary_artifact_id, "bad", store)


def test_specialist_rejects_rgb(tmp_path):
    store = ArtifactStore(tmp_path)
    rgb = np.zeros((8, 8, 3), np.uint8)
    rgb[..., 0] = 80
    store.save(rgb, "original")
    with pytest.raises(ValueError, match="single-channel"):
        stardist.execute(step(), "original", "bad", store)
    assert stardist.probe(store).measurements["replicated_grayscale"] is False
