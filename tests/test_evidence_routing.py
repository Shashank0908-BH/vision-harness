import json
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest

from evals.atif import export
from vision_harness.artifacts import ArtifactStore
from vision_harness.config import load_settings
from vision_harness.contracts import Answer, Assessment, Review
from vision_harness.evidence_routing.contracts import Inspection, Observation, ObservedCandidate
from vision_harness.evidence_routing.measurements import (
    disagreement,
    mask_candidate,
    visual_candidate,
)
from vision_harness.evidence_routing.runtime import run_comparison, validate_inspection
from vision_harness.providers.jev import Jev
from vision_harness.routing.catalog import load_catalog, sha256
from vision_harness.routing.contracts import Intent
from vision_harness.tracing import Trace, write_json

CATALOG = Path("catalog/microscopy-v1.json")


def answer(value=7, status="answered"):
    return Answer(
        status=status,
        value=value,
        evidence_ids=["original"],
        explanation="visual estimate",
        limitations=["uncertain"],
    )


@pytest.fixture
def field(tmp_path):
    path = tmp_path / "field.png"
    cv2.imwrite(str(path), np.arange(256, dtype=np.uint8).reshape(16, 16))
    return path


def saved_mask(procedure, store, trace, directory):
    path = directory / "specialists" / procedure.plan_id / "labels.npz"
    path.parent.mkdir(parents=True)
    labels = np.zeros((16, 16), np.int32)
    labels[1:4, 1:4] = 2
    labels[8:12, 9:13] = 99
    np.savez_compressed(path, labels=labels)
    trace.emit("tool_started", {"call_id": procedure.plan_id, "step": {"tool": procedure.adapter}})
    evidence = {
        "procedure_id": procedure.plan_id,
        "evidence_id": procedure.plan_id,
        "count": 2,
        "coordinates": store.coordinates("original"),
        "overlay_id": store.save(store.load("original"), procedure.plan_id + "-overlay"),
        "worker": {
            "image_sha256": sha256(Path(store.records["original"]["path"])),
            "labels_sha256": sha256(path),
        },
    }
    trace.emit("evidence", evidence)
    return evidence


class Visual:
    def __init__(self, directory, value=7):
        self.directory, self.value = directory, value

    def answer(self, question, images, context):
        assert not (self.directory / "specialists").exists()
        assert not (self.directory / "intent.json").exists()
        assert len(images) == 1
        assert context == {"mode": "vanilla", "evidence": []}
        return answer(self.value, "abstained" if self.value is None else "answered")


class Inspector:
    def __init__(self, directory, unsupported=False, omit=False):
        self.directory, self.unsupported, self.omit = directory, unsupported, omit

    def structured(self, operation, question, images, context, schema):
        assert (self.directory / "vanilla-answer.json").exists()
        if schema is Intent:
            assert set(context) == {"input_probe"}
            return Intent(
                task="unsupported" if self.unsupported else "count_nuclei",
                modality="other" if self.unsupported else "fluorescence",
                target="nuclei",
                rationale="test",
                limitations=[],
            )
        assert schema is Inspection
        assert (self.directory / "candidates.json").exists()
        assert len(images) == len(context["image_order"])
        assert len(images) == 1 + sum(
            c["kind"] == "instance_measurement" for c in context["candidates"]
        )
        assert all("expected" not in c for c in context["candidates"])
        ids = [c["plan_id"] for c in context["candidates"]]
        if self.omit:
            ids = ids[:-1]
        return Inspection(
            observations=[
                Observation(
                    plan_id=i,
                    supporting_observations=[],
                    concerns=["fallible visual interpretation"],
                )
                for i in ids
            ],
            limitations=[],
        )


class Judge:
    def __init__(
        self, directory, selected="vanilla-astra", omit=False, review_error=False, tamper=False
    ):
        self.directory, self.selected, self.omit = directory, selected, omit
        self.review_error, self.tamper = review_error, tamper
        self.ids = []

    def assess(self, state, candidates):
        assert (self.directory / "inspection.json").exists()
        assert state["pixels_available_to_jev"] is False
        assert state["benchmark_labels_available"] is False
        self.ids = [c.plan_id for c in candidates]
        chosen = candidates[:-1] if self.omit else candidates
        return [
            Assessment(
                plan_id=c.plan_id,
                score=3 if c.plan_id == self.selected else 2,
                confidence=0.5,
                probabilities={"0": 0, "1": 0, "2": 1, "3": 0},
            )
            for c in chosen
        ]

    def review(self, state):
        assert (self.directory / "decision.json").exists()
        assert state["selected"]["value"] == state["answer"]["value"]
        if self.review_error:
            raise TimeoutError("review transport failure")
        if self.tamper:
            write_json(self.directory / "candidates.json", [])
        return Review(support_probability=0.1)


def run_case(field, directory, **overrides):
    return run_comparison(
        field,
        "Estimate nuclei in fluorescence.",
        load_settings(Path("configs/evidence-routing.toml")),
        load_settings(Path("configs/poc-adaptive.toml")),
        CATALOG,
        directory,
        astra=overrides.pop("astra", Inspector(directory)),
        vanilla=overrides.pop("vanilla", Visual(directory)),
        jev=overrides.pop("jev", Judge(directory)),
        executor=overrides.pop("executor", saved_mask),
        offline=True,
        **overrides,
    )


@pytest.mark.parametrize(
    "selected,value,kind",
    [("vanilla-astra", 7, "visual_estimate"), ("cellpose-sam", 2, "instance_measurement")],
)
def test_observed_selection_keeps_independent_candidate_and_exact_count(
    field, tmp_path, selected, value, kind
):
    directory = tmp_path / "run"
    judge = Judge(directory, selected=selected)
    result = run_case(field, directory, jev=judge)
    assert result["status"] == "answered" and result["value"] == value
    assert result["source_kind"] == kind
    assert result["review_status"] == "caution" and not result["review_is_calibrated_accuracy"]
    assert set(judge.ids) == {
        "vanilla-astra",
        *[p.plan_id for p in load_catalog(CATALOG).procedures],
    }
    assert json.loads((directory / "vanilla-answer.json").read_text())["value"] == 7
    events = [json.loads(x) for x in (directory / "events.jsonl").read_text().splitlines()]
    frozen = next(e["sequence"] for e in events if e["kind"] == "vanilla_frozen")
    decision = next(e["sequence"] for e in events if e["kind"] == "output_decision")
    assert all(frozen < e["sequence"] < decision for e in events if e["kind"] == "tool_started")
    trajectory = export(directory, directory / "trajectory.json")
    assert trajectory.extra["offline"] is True
    with pytest.raises(FileExistsError):
        run_case(field, directory)


def test_failed_and_abstained_candidates_are_excluded_without_rerun(field, tmp_path):
    directory = tmp_path / "partial"
    attempts = []

    def execute(p, store, trace, output):
        attempts.append(p.plan_id)
        if p.plan_id == "stardist-default":
            raise TimeoutError("worker failed")
        return saved_mask(p, store, trace, output)

    judge = Judge(directory, selected="cellpose-sam")
    result = run_case(
        field, directory, executor=execute, vanilla=Visual(directory, None), jev=judge
    )
    assert result["value"] == 2 and len(attempts) == len(set(attempts)) == 4
    assert {e["candidate_id"] for e in result["candidate_failures"]} == {
        "vanilla-astra",
        "stardist-default",
    }
    assert len(judge.ids) == 3 and "stardist-default" not in judge.ids


@pytest.mark.parametrize(
    "failure,stage",
    [
        ("inspection", "visual_inspection"),
        ("selection", "jev_output_selection"),
        ("review", "jev_review"),
        ("tamper", "jev_review"),
    ],
)
def test_incomplete_judgments_and_review_errors_do_not_turn_into_fallback_success(
    field, tmp_path, failure, stage
):
    directory = tmp_path / failure
    result = run_case(
        field,
        directory,
        astra=Inspector(directory, omit=failure == "inspection"),
        jev=Judge(
            directory,
            omit=failure == "selection",
            review_error=failure == "review",
            tamper=failure == "tamper",
        ),
    )
    assert result["status"] == "error" and result["value"] is None
    assert result["stage"] == stage and result["review_status"] == "not_completed"
    assert (directory / "vanilla-answer.json").exists()


def test_no_valid_candidates_abstains_without_judging(field, tmp_path):
    directory = tmp_path / "none"

    def broken(*args):
        raise ValueError("bad mask")

    result = run_case(
        field, directory, vanilla=Visual(directory, None), executor=broken, jev=object()
    )
    assert result["status"] == "abstained" and len(result["candidate_failures"]) == 5
    assert not (directory / "decision.json").exists()


def test_unsupported_input_remains_out_of_scope_even_with_vanilla_estimate(field, tmp_path):
    directory = tmp_path / "unsupported"
    result = run_case(field, directory, astra=Inspector(directory, unsupported=True), jev=object())
    assert result["status"] == "unsupported" and result["value"] is None
    assert (directory / "research-request.json").exists()
    assert not (directory / "specialists").exists()


@pytest.mark.parametrize("fault", ["hash", "image", "count", "coordinates"])
def test_tampered_mask_evidence_cannot_become_candidate(field, tmp_path, fault):
    store = ArtifactStore(tmp_path / "data")
    store.import_image(field)
    p = load_catalog(CATALOG).procedures[0]
    evidence = saved_mask(p, store, Trace(tmp_path / "data"), tmp_path / "data")
    if fault == "hash":
        evidence["worker"]["labels_sha256"] = "bad"
    elif fault == "image":
        evidence["worker"]["image_sha256"] = "wrong image"
    elif fault == "count":
        evidence["count"] = 99
    else:
        evidence["coordinates"]["width"] = 12
    with pytest.raises(ValueError):
        mask_candidate(p, evidence, store, tmp_path / "data")


def test_count_agreement_does_not_hide_foreground_disagreement_and_empty_union_is_unknown(
    field, tmp_path
):
    store = ArtifactStore(tmp_path / "data")
    store.import_image(field)
    p = load_catalog(CATALOG).procedures[0]
    ev = saved_mask(p, store, Trace(tmp_path / "data"), tmp_path / "data")
    first, labels = mask_candidate(p, ev, store, tmp_path / "data")
    second = first.model_copy(update={"plan_id": "other-profile"})
    # Same count, disjoint pixels: a count-only comparison misses this failure.
    shifted = np.roll(labels, 6, axis=1)
    d = disagreement([first, second], {first.plan_id: labels, second.plan_id: shifted})["pairs"][0]
    assert d["absolute_count_difference"] == 0 and d["foreground_iou"] == 0
    assert d["same_specialist_weights"] is True
    empty = np.zeros_like(labels)
    d = disagreement([first, second], {first.plan_id: empty, second.plan_id: empty})["pairs"][0]
    assert d["foreground_iou"] is None
    assert first.value == 2  # Sparse labels 2 and 99 are two instances, not 99.


def test_inspection_cannot_duplicate_or_invent_ids():
    c = visual_candidate(answer(), "image", "model")
    obs = Observation(plan_id="invented", supporting_observations=[], concerns=[])
    with pytest.raises(ValueError):
        validate_inspection(Inspection(observations=[obs], limitations=[]), [c])
    obs.plan_id = c.plan_id
    with pytest.raises(ValueError):
        validate_inspection(Inspection(observations=[obs, obs], limitations=[]), [c])


@pytest.mark.parametrize("value", ["seven", -1, 2.5, float("inf")])
def test_visual_count_must_be_finite_nonnegative_integer(value):
    with pytest.raises(ValueError):
        visual_candidate(answer(value), "image", "model")


def test_high_bit_depth_is_rejected_before_any_api_call(tmp_path):
    field = tmp_path / "uint16.tif"
    cv2.imwrite(str(field), np.arange(256, dtype=np.uint16).reshape(16, 16))
    result = run_case(
        field, tmp_path / "high-depth", astra=object(), vanilla=object(), jev=object()
    )
    assert result["status"] == "error" and result["stage"] == "input"
    assert "8-bit" in result["error"]
    assert not (tmp_path / "high-depth/calls").exists()


def test_catalog_above_budget_is_not_silently_truncated(field, tmp_path, monkeypatch):
    catalog = load_catalog(CATALOG)
    catalog.procedures.append(catalog.procedures[0].model_copy(update={"plan_id": "fifth"}))
    monkeypatch.setattr(
        "vision_harness.evidence_routing.runtime.load_catalog", lambda path: catalog
    )
    result = run_case(field, tmp_path / "over-budget")
    assert result["status"] == "error" and "four-procedure" in result["error"]
    assert not (tmp_path / "over-budget/specialists").exists()


def test_observed_candidates_use_actual_jev_wire_format(monkeypatch, tmp_path):
    monkeypatch.setenv("JEV_API_KEY", "test-only-key")
    c = visual_candidate(answer(), "image", "gpt-6-astra")
    observed = ObservedCandidate(
        plan_id=c.plan_id,
        candidate=c,
        astra_visual_observations=Observation(
            plan_id=c.plan_id, supporting_observations=[], concerns=[]
        ),
    )

    def handle(request):
        data = json.loads(request.content)
        assert data["questions"][c.plan_id]["type"] == "score"
        assert "visual_estimate" in data["questions"][c.plan_id]["instructions"]
        return httpx.Response(
            200,
            json={
                "answers": {
                    c.plan_id: {
                        "type": "score",
                        "score": 2,
                        "confidence": 0.5,
                        "probabilities": {"0": 0, "1": 0, "2": 1, "3": 0},
                    }
                }
            },
        )

    settings = load_settings(Path("configs/evidence-routing.toml"))
    # load_settings deliberately prefers local .env; set dummy value after loading too.
    monkeypatch.setenv("JEV_API_KEY", "test-only-key")
    jev = Jev(settings, Trace(tmp_path), client=httpx.Client(transport=httpx.MockTransport(handle)))
    assert jev.assess({"pixels_available_to_jev": False}, [observed])[0].plan_id == c.plan_id
