"""Architecture and measurement checks; fixtures are not capability benchmarks."""

import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from evals.research_execution.prepare import independent_reference_count
from evals.research_execution.verifier import grade
from vision_harness.research_execution.contracts import Candidate, Catalog, Requirement, Task
from vision_harness.research_execution.discovery import validate_catalog
from vision_harness.research_execution.evidence import inspect_artifacts
from vision_harness.research_execution.scoring import Scorer, retain_candidates


def task():
    return Task(query="Count nuclei", task_type="nucleus_counting", modality="fluorescence",
        biological_target="nuclei", counting_rules=["include border"],
        requirements=[Requirement(requirement_id=r, purpose=r, acceptance_check="check", required=True)
                      for r in ("decode", "segment", "count")],
        observed_facts=[], assumptions=[], unknowns=[])


def candidate(ident, roles, kind="model"):
    return Candidate(candidate_id=ident, name=ident, kind=kind, requirement_ids=roles,
        capability="test", version_or_checkpoint="test", input_requirements=[],
        output_semantics="instances", deployment_requirements=[], license="unknown",
        limitations=[], source_urls=["https://example.org/doc"], documentation_urls=["https://example.org/doc"],
        supported_claims=[], unknowns=[])


def test_per_requirement_selection_not_mean_across_unrelated_roles():
    catalog = Catalog(candidates=[candidate("a", ["decode", "segment", "count"], "library"),
        candidate("b", ["decode", "segment", "count"], "library")], gaps=[], search_coverage="bounded")
    scores = {"a": {"mean": 2, "requirements": {"decode": 3, "segment": 0, "count": 3}},
              "b": {"mean": 1, "requirements": {"decode": 0, "segment": 3, "count": 0}}}
    assert {c.candidate_id for c in retain_candidates(task(), catalog, scores)} == {"a", "b"}


def test_every_discovered_candidate_role_is_scored(tmp_path):
    catalog = Catalog(candidates=[candidate("a", ["decode", "segment"]), candidate("b", ["count"])],
                      gaps=[], search_coverage="bounded")
    scorer = object.__new__(Scorer)
    seen = []

    def score(state, subjects, purpose, output):
        seen.extend(s.plan_id for s in subjects)
        return {s.plan_id: 2 for s in subjects}

    scorer.score = score
    scorer.candidates(task(), catalog, {}, tmp_path / "scores.json")
    assert seen == ["a--decode", "a--segment", "b--count"]


def test_jev_batches_split_without_losing_plan_code_or_subjects(tmp_path, monkeypatch):
    from vision_harness.config import Settings
    from vision_harness.providers.evidence_budget import encoded_size
    from vision_harness.research_execution.contracts import Scorable
    from vision_harness.tracing import Trace

    settings = Settings()
    settings.limits.jev_max_request_bytes = 6000
    scorer = Scorer(settings, Trace(tmp_path / "trace"))
    seen = []

    def request(operation, state, questions):
        assert encoded_size({"model": settings.models.jev, "state": state, "questions": questions}) <= 6000
        seen.extend(questions)
        assert all("x"*3000 in q["instructions"] for q in questions.values())
        return {key: {"type": "score", "score": 2, "confidence": 1,
                      "probabilities": {"0": 0, "1": 0, "2": 1, "3": 0}} for key in questions}

    monkeypatch.setattr(scorer.jev, "_request", request)
    scores = scorer.score({}, [Scorable(plan_id=f"p{i}", subject_json="x"*3000) for i in range(3)],
                          "Test only", tmp_path / "scores.json")
    assert seen == ["p0", "p1", "p2"]
    assert scores == {"p0": 2, "p1": 2, "p2": 2}


def test_benchmark_disallows_development_replay(tmp_path):
    from evals.research_execution.prepare import prepare

    with pytest.raises(ValueError, match="forbids"):
        prepare("test", tmp_path)


def test_review_uses_noul_boolean_criteria_wire_contract(tmp_path, monkeypatch):
    from vision_harness.config import Settings
    from vision_harness.tracing import Trace

    scorer = Scorer(Settings(), Trace(tmp_path / "trace"))

    def request(operation, state, questions):
        for question in questions.values():
            assert question["type"] == "noul"
            assert set(question["criteria"]) == {"true", "false"}
            assert all(isinstance(text, str) and text for text in question["criteria"].values())
        return {key: {"type": "noul", "noul": 0.8} for key in questions}

    monkeypatch.setattr(scorer.jev, "_request", request)
    result = scorer.review({}, tmp_path / "review.json")
    assert set(result) == {"method", "evidence"}


def test_discovery_rejects_uncited_urls_and_unknown_roles():
    catalog = Catalog(candidates=[candidate("a", ["decode"]), candidate("b", ["count"])],
                      gaps=[], search_coverage="bounded")
    with pytest.raises(ValueError, match="search evidence"):
        validate_catalog(catalog, task(), [])
    catalog.candidates[0].requirement_ids = ["invented"]
    with pytest.raises(ValueError, match="unknown task"):
        validate_catalog(catalog, task(), ["https://example.org/doc"])


def test_artifacts_measure_ids_preserve_fragment_warning_and_reject_bad_shape(tmp_path):
    preview = tmp_path / "input.png"
    cv2.imwrite(str(preview), np.zeros((8, 8), np.uint8))
    labels = np.zeros((8, 8), np.int32)
    labels[1, 1] = labels[6, 6] = 9
    labels[3:5, 3:5] = 25
    np.savez_compressed(tmp_path / "labels.npz", labels=labels)
    (tmp_path / "execution-metadata.json").write_text('{"model":"test"}')
    outcome = SimpleNamespace(plan_id="p", program_executed_unchanged=True)
    result = inspect_artifacts(tmp_path, outcome, [8, 8], preview)
    assert result["count"] == 2
    assert result["fragmented_instance_ids"] == [{"id": 9, "components": 2}]
    assert result["fragmentation_repaired"] is False
    with pytest.raises(ValueError, match="original image geometry"):
        inspect_artifacts(tmp_path, outcome, [16, 16], preview)


def test_separate_grader_does_not_accept_fabricated_count(tmp_path):
    tests, output = tmp_path / "tests", tmp_path / "output"
    tests.mkdir()
    output.mkdir()
    labels = np.array([[0, 1], [0, 2]], dtype=np.int32)
    np.savez_compressed(tests / "reference.npz", labels=labels)
    np.savez_compressed(output / "labels.npz", labels=labels)
    (output / "answer.json").write_text(json.dumps({"mode": "full", "status": "answered", "count": 42}))
    result = grade(output, tests, tmp_path / "result")
    assert not result["answered"] and not result["within_10_percent"]
    assert "differs from final instance map" in result["error"]


def test_reference_decoder_reused_values_disconnected_and_diagonal():
    red = np.array([[1, 0, 0, 1], [0, 1, 0, 0], [0, 0, 2, 2]], dtype=np.uint8)
    assert independent_reference_count(red) == 3


def test_document_excerpt_reaches_usage_beyond_page_prefix():
    from vision_harness.research_execution.documents import usage_excerpt

    source = "Long navigation or imports\n" * 1000 + "\ndef predict_instances(image, scale=None):\n    pass\n"
    excerpt = usage_excerpt(source, 5000)
    assert "def predict_instances" in excerpt
    assert "source characters" in excerpt


def test_executor_rejects_changed_approved_program(tmp_path, monkeypatch):
    from vision_harness.config import Settings
    from vision_harness.research_execution import executor
    from vision_harness.tracing import Trace

    exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda p: True if str(p) == "/.dockerenv" else exists(p))
    monkeypatch.setattr(executor, "require_key", lambda name: "test-key")
    plan = SimpleNamespace(plan_id="p", python_program="print(1)", model_dump=lambda: {"plan_id": "p"})
    folder = tmp_path / "execution"

    class Process:
        returncode = 0

        def __init__(self, command, **kwargs):
            assert command[:3] == ["codex", "exec", "--ignore-user-config"]
            assert "test-key" not in " ".join(command)

        def communicate(self, *args, **kwargs):
            (folder / "approved.py").write_text("print(999)")
            (folder / "outcome.json").write_text(json.dumps({"status": "executed", "plan_id": "p",
                "program_executed_unchanged": True, "labels_path": "labels.npz",
                "metadata_path": "execution-metadata.json", "setup_actions": [],
                "failure_details": [], "suggested_repair": None}))
            return "", ""

    monkeypatch.setattr(executor.subprocess, "Popen", Process)
    with pytest.raises(ValueError, match="changed the approved program"):
        executor.execute(plan, {}, folder, Settings(), Trace(tmp_path / "trace"), 20)


def test_generated_task_has_separate_verifier_and_no_references_in_image():
    from harbor.models.task.task import Task as HarborTask

    root = Path("evals/tasks/generated/research-execution/dev-01/image-01")
    if not root.exists():
        pytest.skip("Generated development task unavailable")
    configured = HarborTask(root)
    assert configured.config.verifier.environment_mode.value == "separate"
    assert not list((root / "environment").rglob("reference.npz"))
    assert not (root / "environment/app/.env").exists()
    assert not (root / "environment/app/reports").exists()
    assert not (root / "environment/app/evals").exists()


@pytest.mark.parametrize("second_review_fails", [False, True])
def test_low_review_replans_and_passes_feedback_back_to_selection(tmp_path, monkeypatch, second_review_fails):
    from vision_harness.config import Settings
    from vision_harness.research_execution import runtime
    from vision_harness.research_execution.contracts import Inspection

    preview = tmp_path / "preview.png"
    cv2.imwrite(str(preview), np.zeros((8, 8), np.uint8))
    catalog = Catalog(candidates=[candidate("model", ["segment"]),
        candidate("library", ["decode", "count"], "library")], gaps=[], search_coverage="bounded")
    planned_packets, scored_packets, executed = [], [], []

    class FakeAstra:
        def __init__(self, settings, trace):
            self.settings, self.trace = settings, trace

        def structured(self, operation, question, images, context, schema):
            if schema is Task:
                return task()
            assert schema is Inspection
            return Inspection(plan_id=executed[-1], visual_observations=[], suspected_failures=[],
                checks_supported_by_artifacts=["geometry"], unresolved_requirements=[],
                recommended_action="finish", next_evidence_needed=[])

    class FakeScorer:
        def __init__(self, settings, trace):
            self.round = 0

        def candidates(self, task, catalog, packet, output):
            return {c.candidate_id: {"mean": 2, "requirements": {r: 2 for r in c.requirement_ids}}
                    for c in catalog.candidates}

        def plans(self, plans, packet, output):
            scored_packets.append(packet)
            return {p.plan_id: 2 for p in plans}

        def outputs(self, observations, packet, output):
            return {o["plan_id"]: index for index, o in enumerate(observations)}

        def review(self, packet, output):
            self.round += 1
            if second_review_fails and self.round == 2:
                raise RuntimeError("Injected provider failure on second review")
            return {"method": {"noul": 0.9}, "evidence": {"noul": 0.2 if self.round == 1 else 0.9}}

    def proposed(astra, task, candidates, usage, packet, images, folder):
        planned_packets.append(packet)
        plan = SimpleNamespace(plan_id=f"p{len(planned_packets)}", python_program=f"x={len(planned_packets)}",
                               candidate_ids=[], model_dump=lambda **kwargs: {})
        return SimpleNamespace(plans=[plan], preferred_plan_id=plan.plan_id)

    def execute(plan, packet, folder, settings, trace, timeout):
        executed.append(plan.plan_id)
        folder.mkdir(parents=True)
        labels = np.zeros((8, 8), np.int32)
        labels[2:4, 2:4] = 1
        if len(executed) == 2:
            labels[6, 6] = 2
        np.savez_compressed(folder / "labels.npz", labels=labels)
        (folder / "execution-metadata.json").write_text('{"model":"test"}')
        return SimpleNamespace(plan_id=plan.plan_id, program_executed_unchanged=True)

    monkeypatch.setattr(runtime, "Astra", FakeAstra)
    monkeypatch.setattr(runtime, "Scorer", FakeScorer)
    monkeypatch.setattr(runtime, "probe", lambda raw: {"shape": [8, 8]})
    monkeypatch.setattr(runtime, "discover", lambda *args: catalog)
    monkeypatch.setattr(runtime, "compile_usage", lambda *args: (SimpleNamespace(
        model_dump=lambda: {}, contracts=[SimpleNamespace(candidate_id=c.candidate_id, ready_for_trial=True)
                                         for c in catalog.candidates]), []))
    monkeypatch.setattr(runtime, "propose", proposed)
    monkeypatch.setattr(runtime, "execute", execute)
    answer = runtime.run("Count nuclei", "full", Settings(), tmp_path / "run", preview=preview)
    assert executed == ["p1", "p2"]
    assert planned_packets[1]["feedback"][0]["review"]["evidence"]["noul"] == 0.2
    assert scored_packets[1]["feedback"][0]["review"]["evidence"]["noul"] == 0.2
    assert answer["count"] == (1 if second_review_fails else 2)
    assert answer["review_status"] == ("provisional_after_error" if second_review_fails else "approved")
    with np.load(tmp_path / "run/labels.npz") as archive:
        assert np.count_nonzero(np.unique(archive["labels"]) > 0) == answer["count"]


def test_report_includes_missing_attempts_and_clusters_by_image(tmp_path, monkeypatch):
    from evals.research_execution import report

    destination = tmp_path / "report"
    destination.mkdir()
    monkeypatch.setattr(report, "ROOT", tmp_path)
    monkeypatch.setattr(report, "REPORT", destination)
    (destination / "selection.json").write_text(json.dumps({"arms": ["vanilla", "full"], "repetitions": 3}))
    (destination / "cohort.json").write_text(json.dumps([
        {"id": "image-01", "expected": 10}, {"id": "image-02", "expected": 10}]))
    for mode in ("vanilla", "full"):
        for image in ("image-01", "image-02"):
            for repeat in range(3):
                if (mode, image, repeat) == ("full", "image-02", 2):
                    continue
                folder = tmp_path / "jobs" / f"research-execution-test-{mode}" / f"{image}__r{repeat}"
                (folder / "verifier").mkdir(parents=True)
                (folder / "agent/run").mkdir(parents=True)
                (folder / "config.json").write_text(json.dumps({"task": {"path": f"tasks/{image}"}}))
                (folder / "verifier/grading.json").write_text(json.dumps({"expected": 10, "count": 10,
                    "answered": True, "within_10_percent": True, "percentage_error": 0}))
                (folder / "agent/run/answer.json").write_text(json.dumps({"status": "answered",
                    "review_status": "provisional", "elapsed_seconds": 1}))
    report.collect()
    result = json.loads((destination / "results.json").read_text())
    full = result["metrics"]["full"]
    assert full["attempts"] == 6 and full["answered"] == 5
    assert full["conditional_mape_percent"] == 0
    assert full["complete_cohort_mape_percent"] is None
    assert full["all_attempt_success_percent"] == pytest.approx(100*5/6)
    assert result["paired_success_difference"]["clusters"] == 2
    assert result["paired_success_difference"]["mean"] == pytest.approx(-1/6)
    assert (destination / "index.html").exists()
