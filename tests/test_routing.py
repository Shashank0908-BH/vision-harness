import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from vision_harness.config import load_settings
from vision_harness.contracts import Answer, Assessment, Review
from vision_harness.routing.catalog import eligible, load_catalog, rank
from vision_harness.routing.contracts import CandidateReason, Intent, Proposal, ResearchFindings
from vision_harness.routing.executor import input_probe, validate_labels, worker_environment
from vision_harness.routing.research import consulted_urls, validate_sources
from vision_harness.routing.runtime import run_route, validate_answer, validate_proposal

CATALOG = Path("catalog/microscopy-v1.json")


def intent(modality="fluorescence", task="count_nuclei"):
    return Intent(task=task, modality=modality, target="nuclei", rationale="metadata", limitations=[])


def score(plan_id, value=2):
    return Assessment(plan_id=plan_id, score=value, confidence=.6, probabilities={"0": 0, "1": 0, "2": 1, "3": 0})


def test_catalog_eligibility_rejects_unknown_modality_and_binary():
    catalog = load_catalog(CATALOG)
    image = np.repeat(np.arange(256, dtype=np.uint8).reshape(16, 16, 1), 3, axis=2)
    assert len(eligible(catalog, intent(), input_probe(image))[0]) == 4
    assert not eligible(catalog, intent("unknown"), input_probe(image))[0]
    assert not eligible(catalog, intent(task="unsupported"), input_probe(image))[0]
    image[image > 100] = 255
    image[image <= 100] = 0
    assert not eligible(catalog, intent(), input_probe(image))[0]


def test_catalog_rejects_undeclared_parameters_and_duplicate_ids(tmp_path):
    data = json.loads(CATALOG.read_text())
    data["procedures"][0]["parameters"]["run_code"] = "bad"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Unexpected parameters"):
        load_catalog(path)
    data = json.loads(CATALOG.read_text())
    data["procedures"].append(data["procedures"][0])
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Duplicate"):
        load_catalog(path)


def test_ranking_requires_all_candidates_and_uses_stable_ties():
    assert rank([score("b"), score("a")], ["a", "b"]) == ["a", "b"]
    with pytest.raises(ValueError, match="exactly one"):
        rank([score("a")], ["a", "b"])


def test_proposal_cannot_omit_or_invent_procedures():
    procedures = load_catalog(CATALOG).procedures
    bad = Proposal(preferred_id="invented", candidates=[])
    with pytest.raises(ValueError):
        validate_proposal(bad, procedures)


def test_labels_count_ids_not_max_id_and_reject_bad_geometry():
    assert validate_labels(np.array([[0, 2], [2, 9]], np.int32), (2, 2)) == [2, 9]
    for labels in (np.array([[0, -1]], np.int32), np.array([[0, 1]], float), np.zeros((3, 3), np.int32)):
        with pytest.raises(ValueError):
            validate_labels(labels, (1, 2))


def test_worker_does_not_inherit_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("OTHER_PROVIDER_TOKEN", "must-not-leak")
    assert "OPENAI_API_KEY" not in worker_environment()
    assert "OTHER_PROVIDER_TOKEN" not in worker_environment()


def test_answer_must_match_measured_count():
    answer = Answer(status="answered", value=8, explanation="estimate", evidence_ids=["x"], limitations=[])
    with pytest.raises(ValueError, match="instance count"):
        validate_answer(answer, {"count": 7, "evidence_id": "x"})


def test_research_only_accepts_actual_consulted_citations():
    url = "https://github.com/example/model"
    response = {"output": [{"type": "web_search_call", "action": {"sources": [{"url": url}]}}]}
    assert consulted_urls(response) == [url]
    findings = ResearchFindings.model_validate({"proposals": [{"plan_id": "example", "model_name": "Example", "capability": "count", "applicable_inputs": "images", "checkpoint": None, "license": None, "hardware": None, "evidence": "unverified", "limitations": [], "sources": [url]}], "gaps": []})
    validate_sources(findings, [url])
    with pytest.raises(ValueError, match="absent"):
        validate_sources(findings, [])


@pytest.mark.parametrize("review_fails", [False, True])
def test_routing_freezes_all_scores_before_execution_and_keeps_soft_caution(tmp_path, monkeypatch, review_fails):
    monkeypatch.setattr("vision_harness.routing.runtime.verify_procedure", lambda p: {})
    catalog = load_catalog(CATALOG)
    ids = [p.plan_id for p in catalog.procedures]
    output = tmp_path / "run"
    image = tmp_path / "image.png"
    gray = np.arange(256, dtype=np.uint8).reshape(16, 16)
    cv2.imwrite(str(image), gray)
    seen = []

    class FakeAstra:
        def structured(self, operation, question, images, context, schema):
            if schema is Intent:
                return intent()
            if schema is Proposal:
                return Proposal(preferred_id=ids[0], candidates=[CandidateReason(plan_id=i, rationale="test", assumptions=[]) for i in ids])
            assert not (output / "comparison.json").exists()
            assert len(seen) == 1
            return Answer(status="answered", value=7, explanation="estimate", evidence_ids=[context["evidence"]["evidence_id"]], limitations=["unverified biology"])

    class FakeJev:
        def assess(self, state, candidates):
            assert not seen
            assert [c.plan_id for c in candidates] == ids
            assert "astra_preferred_id" not in state
            return [score(i, 2.5 if i == ids[1] else 2) for i in ids]

        def review(self, state):
            assert len(seen) == 1
            if review_fails:
                raise TimeoutError("API timeout, not rejection")
            return Review(support_probability=.2)

    def fake_execute(p, store, trace, directory):
        decision = json.loads((directory / "decision.json").read_text())
        assert decision["selected_id"] == ids[1]
        if seen:
            assert (directory / "answer.json").exists()
        seen.append(p.plan_id)
        return {"count": 7, "evidence_id": p.plan_id, "overlay_id": "original"}

    result = run_route(image, "count", load_settings(Path("configs/routing.toml")), CATALOG, output,
                       compare_all=True, astra=FakeAstra(), jev=FakeJev(), executor=fake_execute)
    if review_fails:
        assert result["status"] == "error"
        assert result["stage"] == "jev_review"
        assert result["review_status"] == "not_completed"
        assert (output / "candidate-answer.json").exists()
        assert len(seen) == 1
    else:
        assert result["status"] == "answered" and result["value"] == 7
        assert result["review_status"] == "caution"
        assert set(seen) == set(ids)
        assert len(json.loads((output / "comparison.json").read_text())) == 4


def test_checkpoint_tampering_is_rejected(tmp_path, monkeypatch):
    import vision_harness.routing.catalog as registry

    monkeypatch.setattr(registry, "ROOT", tmp_path)
    p = load_catalog(CATALOG).procedures[0]
    python = tmp_path / p.python
    python.parent.mkdir(parents=True)
    python.write_text("interpreter placeholder")
    for file in p.files:
        path = tmp_path / file.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"wrong weights")
    with pytest.raises(ValueError, match="hash mismatch"):
        registry.verify_procedure(p)


def test_unsupported_route_saves_research_request_without_running_models(tmp_path):
    image = tmp_path / "image.png"
    cv2.imwrite(str(image), np.arange(256, dtype=np.uint8).reshape(16, 16))

    class FakeAstra:
        def structured(self, operation, question, images, context, schema):
            assert schema is Intent
            return intent("other", "unsupported")

    output = tmp_path / "unsupported"
    result = run_route(image, "analyze this MRI", load_settings(Path("configs/routing.toml")), CATALOG,
                       output, astra=FakeAstra(), jev=object())
    assert result["status"] == "unsupported" and result["value"] is None
    assert (output / "research-request.json").exists()
    assert not (output / "decision.json").exists()
    assert not (output / "specialists").exists()


def test_incomplete_cohort_has_no_misleading_full_mape():
    from evals.routing import summarize

    assert summarize([10, None], [10, 20]) == {"completed": 1, "total": 2, "mape_percent": None, "exact": 1}
    assert summarize([12, 18], [10, 20])["mape_percent"] == 15
