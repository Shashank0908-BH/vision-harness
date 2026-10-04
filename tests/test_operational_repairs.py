"""Regression checks for observed documentation, device and interpreter failures."""

import ast
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from vision_harness.research_execution.contracts import Policy, UsageContract, UsageSet
from vision_harness.research_execution.documents import compile_usage, validate_usage
from vision_harness.research_execution.planning import validate_installed_calls
from vision_harness.research_execution.preflight import (
    commands,
    validate_dependencies,
    validate_report,
)
from vision_harness.tracing import Trace


def candidate(name, url):
    return SimpleNamespace(candidate_id=name, documentation_urls=[url],
                           model_dump=lambda: {"candidate_id": name, "documentation_urls": [url]})


def usage(ident="model", sources=None, ready=True):
    return UsageContract(candidate_id=ident, source_ids=sources or [], installation=[],
        supported_inputs="YX", channel_and_axis_rules="YX", normalization="documented",
        scale_and_resolution="native", inference_api="documented", output_interpretation="IDs",
        failure_modes=[], unresolved=[], ready_for_trial=ready)


@pytest.mark.parametrize("failure", ["typo", "foreign", "omitted", "duplicate"])
def test_usage_repairs_observed_citation_failures_once(tmp_path, monkeypatch, failure):
    candidates = [candidate("model", "https://example.org/model"), candidate("io", "https://example.org/io")]
    docs = [{"source_id": c.candidate_id + "-doc", "url": c.documentation_urls[0], "status": "retrieved"}
            for c in candidates]
    monkeypatch.setattr("vision_harness.research_execution.documents.fetch_document",
                        lambda url, *_: next(d for d in docs if d["url"] == url))
    good = UsageSet(contracts=[usage("model", ["model-doc"]), usage("io", ["io-doc"])], coverage_gaps=[])
    bad = good.model_copy(deep=True)
    if failure == "duplicate":
        bad.contracts[1].candidate_id = "model"
    else:
        bad.contracts[1].source_ids = {"typo": ["io-doc-doc"], "foreign": ["model-doc"], "omitted": []}[failure]
    contexts = []

    def structured(operation, query, images, context, schema):
        contexts.append(dict(context))
        return bad if len(contexts) == 1 else good

    agent = SimpleNamespace(structured=structured, trace=Trace(tmp_path / "trace"))
    task = SimpleNamespace(query="Count", model_dump=lambda: {})
    result, _ = compile_usage(agent, task, candidates, {}, tmp_path / "docs", Policy())
    assert result == good
    assert len(contexts) == 2
    assert contexts[1]["candidate_source_ids"] == {"model": ["model-doc"], "io": ["io-doc"]}
    assert "validation_error_to_repair" in contexts[1]
    assert (tmp_path / "docs/proposed-usage-1.json").exists()
    assert (tmp_path / "docs/validation-errors-1.json").exists()


def test_unavailable_docs_never_become_ready_and_repeated_bad_citations_fail_closed(tmp_path, monkeypatch):
    candidates = [candidate("model", "https://example.org/model")]
    docs = [{"source_id": "failed", "url": candidates[0].documentation_urls[0], "status": "error"}]
    with pytest.raises(ValueError, match="unavailable"):
        validate_usage(UsageSet(contracts=[usage(sources=["failed"])], coverage_gaps=[]), candidates, docs)
    monkeypatch.setattr("vision_harness.research_execution.documents.fetch_document", lambda *_: docs[0])
    agent = SimpleNamespace(structured=lambda *_: pytest.fail("No model call without documentation"))
    task = SimpleNamespace(query="Count", model_dump=lambda: {})
    blocked, _ = compile_usage(agent, task, candidates, {}, tmp_path / "blocked", Policy())
    assert not blocked.contracts[0].ready_for_trial and blocked.coverage_gaps
    docs[0]["status"] = "retrieved"
    calls = []

    def invalid(*_):
        calls.append(True)
        return UsageSet(contracts=[usage(sources=["invented"])], coverage_gaps=[])

    agent = SimpleNamespace(structured=invalid, trace=Trace(tmp_path / "trace"))
    with pytest.raises(ValueError, match="invented"):
        compile_usage(agent, task, candidates, {}, tmp_path / "invalid", Policy())
    assert len(calls) == 2
    assert not (tmp_path / "invalid/usage-contracts.json").exists()


def test_missing_optional_candidate_can_remain_unready_with_valid_primary():
    candidates = [candidate("model", "https://example.org/model"), candidate("optional", "https://example.org/missing")]
    docs = [{"source_id": "model-doc", "url": candidates[0].documentation_urls[0], "status": "retrieved"}]
    result = UsageSet(contracts=[usage(sources=["model-doc"]), usage("optional", ready=False)],
                      coverage_gaps=["Optional documentation unavailable"])
    validate_usage(result, candidates, docs)


@pytest.mark.parametrize("call", ["tf.config.set_soft_device_placement(False)",
                                 "tf.config.set_soft_device_placement(enabled=False)",
                                 "set_soft_device_placement(False)"])
def test_gpu_stardist_rejects_strict_placement_before_plan_scoring(call):
    program = f"{call}\nwith tf.device('/GPU:0'):\n    labels, details = model.predict_instances(x)"
    env = {"tensorflow_soft_placement_required": True}
    with pytest.raises(ValueError, match="CPU-only"):
        validate_installed_calls(ast.parse(program), env)
    repaired = program.replace("False", "True")
    validate_installed_calls(ast.parse(repaired), env)
    # A standalone network probe with no full predict_instances is allowed.
    validate_installed_calls(ast.parse(call + "\nmodel.keras_model(x)"), env)


def test_preflight_uses_selected_interpreter_path_and_catches_missing_import(tmp_path):
    from vision_harness.research_execution import preflight

    target = tmp_path / "private packages"
    target.mkdir()
    folder = tmp_path / "execution with spaces"
    folder.mkdir()
    program = "import json\nfrom trial_missing_library import function\nraise RuntimeError('inference ran')\n"
    (folder / "approved.py").write_text(program)
    (folder / "import-preflight.py").write_text(Path(preflight.__file__).read_text())
    plan = SimpleNamespace(python_program=program, python_executable=sys.executable, install_requirements=[])
    environment = {"python_environments": {sys.executable: {"unset": ["LD_LIBRARY_PATH"],
                   "env": {"PYTHONPATH": str(target)}}}}
    launch = commands(plan, environment, folder)
    original_cuda = os.environ.get("CUDA_VISIBLE_DEVICES")
    result = subprocess.run(shlex.split(launch["preflight"]), capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads((folder / "import-preflight.json").read_text())
    assert report["checks"][0]["ok"] and not report["checks"][1]["ok"]
    assert "ModuleNotFoundError" in report["checks"][1]["error"]
    with pytest.raises(RuntimeError, match="failed"):
        validate_report(folder / "import-preflight.json", plan)
    # An approved setup's private target becomes visible without modifying the base interpreter.
    (target / "trial_missing_library.py").write_text("def function(): pass\n")
    result = subprocess.run(shlex.split(launch["preflight"]), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert validate_report(folder / "import-preflight.json", plan)["ok"]
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == original_cuda
    report = json.loads((folder / "import-preflight.json").read_text())
    report["checks"] = report["checks"][:1]
    (folder / "import-preflight.json").write_text(json.dumps(report))
    with pytest.raises(RuntimeError, match="cover"):
        validate_report(folder / "import-preflight.json", plan)
    plan.python_executable = "/unmeasured/python"
    with pytest.raises(ValueError, match="measured"):
        commands(plan, environment, folder)


def test_missing_skimage_requires_scored_pin_and_install_preserves_runtime(tmp_path):
    python = "/opt/venvs/torch/bin/python"
    modules = {"skimage": {"distribution": "scikit-image", "version": None, "module_found": False},
               "numpy": {"distribution": "numpy", "version": "2.5.3", "module_found": True}}
    env = {"python_environments": {python: {"modules": modules, "package_target": "/home/researcher/packages/torch"}}}
    plan = SimpleNamespace(python_executable=python, python_program="from skimage.measure import regionprops_table",
                           install_requirements=[])
    with pytest.raises(ValueError, match="absent.*scikit-image"):
        validate_dependencies(plan, env)
    plan.install_requirements = ["scikit-image==0.26.0"]
    validate_dependencies(plan, env)
    launch = commands(plan, env, tmp_path)
    assert "--target /home/researcher/packages/torch" in launch["install"]
    assert "--python /opt/venvs/torch/bin/python" in launch["install"]
    assert (tmp_path / "runtime-constraints.txt").read_text() == "numpy==2.5.3\n"
    for invalid in (["scikit-image"], ["scikit-image==0.26.0", "numpy==1.26.0"],
                    ["scikit-image==0.26.0", "scikit-image==0.25.0"], ["--target=/opt/venvs/torch"]):
        plan.install_requirements = invalid
        with pytest.raises(ValueError):
            validate_dependencies(plan, env)
