import pytest

from vision_harness.artifacts import ArtifactStore
from vision_harness.contracts import Arguments, Step
from vision_harness.demo import demo_plans
from vision_harness.tools.opencv import execute, probe
from vision_harness.tools.registry import Registry


def args(**values):
    return Arguments(**{k: values.get(k) for k in Arguments.model_fields})


def test_counts_boxes_and_areas_are_actual_pixels(tmp_path, image_path):
    store = ArtifactStore(tmp_path / "run")
    store.import_image(image_path)
    evidence = execute(demo_plans().candidates[0].steps[0], "original", "count", store)
    assert evidence.measurements["component_count"] == 2
    assert [c["area_pixels"] for c in evidence.measurements["components"]] == [100, 400]
    assert evidence.measurements["components"][0]["box"] == [10, 20, 10, 10]
    assert len(evidence.artifact_ids) == 2


def test_nested_crop_preserves_original_coordinates(tmp_path, image_path):
    store = ArtifactStore(tmp_path / "run")
    store.import_image(image_path)
    first = execute(
        Step(step_id="a", tool="crop", input_ref="original", arguments=args(box=[5, 10, 90, 50])),
        "original",
        "a",
        store,
    )
    second = execute(
        Step(step_id="b", tool="crop", input_ref="a", arguments=args(box=[5, 5, 30, 30])),
        first.primary_artifact_id,
        "b",
        store,
    )
    assert store.coordinates(second.primary_artifact_id)["original_offset"] == [10, 15]
    with pytest.raises(ValueError, match="outside"):
        execute(
            Step(
                step_id="bad",
                tool="crop",
                input_ref="original",
                arguments=args(box=[-1, 0, 20, 20]),
            ),
            "original",
            "bad",
            store,
        )


def test_distance_and_fixed_probes(tmp_path, image_path):
    store = ArtifactStore(tmp_path / "run")
    store.import_image(image_path)
    evidence = execute(
        Step(
            step_id="m",
            tool="measure",
            input_ref="original",
            arguments=args(points=[[1, 1], [4, 5]]),
        ),
        "original",
        "m",
        store,
    )
    assert evidence.measurements["distance_pixels"] == 5
    assert (
        probe(store).measurements["color_coverage"]["red"]["fraction_at_saturation_80"]
        == 500 / 15000
    )


def test_registry_rejects_bad_references_and_unused_arguments(settings):
    from pathlib import Path

    registry = Registry(Path(settings.paths.capabilities))
    plan = demo_plans().candidates[0]
    plan.steps[0].input_ref = "future"
    with pytest.raises(ValueError, match="earlier"):
        registry.validate(plan, 3)
    plan.steps[0].input_ref = "original"
    plan.steps[0].arguments.points = [[1, 1], [2, 2]]
    with pytest.raises(ValueError, match="not used"):
        registry.validate(plan, 3)
