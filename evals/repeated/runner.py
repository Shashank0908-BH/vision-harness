"""Repeated paired trials without changing the frozen harness policy."""

import concurrent.futures
import hashlib
import json
import random
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2

from evals.atif import export
from vision_harness.artifacts import ArtifactStore
from vision_harness.config import load_settings
from vision_harness.contracts import Answer
from vision_harness.providers.astra import Astra
from vision_harness.routing.catalog import load_catalog, sha256
from vision_harness.routing.executor import execute
from vision_harness.routing.runtime import run_route, source_hash, validate_answer
from vision_harness.runtime import run
from vision_harness.tracing import Trace, write_json

from .data import CATALOG, CONFIG, DATA, REPEATS, REPORT, RUNS, VANILLA_CONFIG

NATIVE = threading.Semaphore(3)
MPS = threading.Lock()
PRINT = threading.Lock()


def log(data):
    with PRINT:
        print(json.dumps(data), flush=True)


def locked_execute(procedure, store, trace, directory):
    queued = time.monotonic()
    # Acquire MPS first so waiting GPU work does not consume all CPU slots.
    if procedure.adapter == "cellpose":
        with MPS, NATIVE:
            trace.emit("worker_queue", {"procedure_id": procedure.plan_id, "wait_seconds": time.monotonic()-queued})
            return execute(procedure, store, trace, directory)
    with NATIVE:
        trace.emit("worker_queue", {"procedure_id": procedure.plan_id, "wait_seconds": time.monotonic()-queued})
        return execute(procedure, store, trace, directory)


def store_from_run(directory):
    store = ArtifactStore(directory)
    store.records = json.loads((directory / "artifacts/index.json").read_text())
    return store


def complete_fixed(directory, catalog):
    """Fill only unattempted procedures after a failed route; never repair its answer."""
    trace = Trace(directory)
    event_path = directory / "events.jsonl"
    trace.sequence = max((json.loads(x)["sequence"] for x in event_path.read_text().splitlines()), default=0)
    store = store_from_run(directory)
    statuses = {}
    for p in catalog.procedures:
        folder = directory / "specialists" / p.plan_id
        evidence = folder / "evidence.json"
        if evidence.exists():
            statuses[p.plan_id] = "success"
        elif folder.exists():
            statuses[p.plan_id] = "error_preserved_without_retry"
        else:
            try:
                locked_execute(p, store, trace, directory)
                statuses[p.plan_id] = "success_evaluation_only"
            except Exception as error:
                statuses[p.plan_id] = "error: " + str(error)
    write_json(directory / "fixed-completion.json", {"statuses": statuses, "does_not_change_harness_answer": True})


def tools_answer(row, route, directory, settings, catalog):
    """Paired no-Jev-selection ablation; sees one mask and no Jev scores."""
    directory.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    trace = Trace(directory)
    manifest = {"run_id": str(directory.parent.name) + "-" + directory.name, "mode": "astra-preferred-paired-ablation",
                "offline": False, "config": settings.model_dump(), "source_sha256": source_hash(),
                "shared_stages": "intent and proposal from full route; separate Astra answer request",
                "evidence_generated_after_routing": True}
    write_json(directory / "manifest.json", manifest)
    store = ArtifactStore(directory)
    store.import_image(Path(row["image"]))
    trace.emit("input", {"question": row["question"]})
    result = {"status": "error", "value": None, "stage": "missing_shared_proposal"}
    try:
        proposal = json.loads((route / "proposal.json").read_text())
        pid = proposal["preferred_id"]
        evidence = json.loads((route / "specialists" / pid / "evidence.json").read_text())
        procedure = next(p for p in catalog.procedures if p.plan_id == pid)
        overlay = cv2.imread(str(route / "artifacts" / (evidence["overlay_id"] + ".png")))
        store.save(overlay, "preferred-overlay")
        evidence = {**evidence, "overlay_id": "preferred-overlay"}
        trace.emit("evidence", evidence)
        answer = Astra(settings, trace).structured(
            "return a grounded estimate using only the selected procedure", row["question"],
            [store.image_input("original"), store.image_input("preferred-overlay")],
            {"intent": json.loads((route / "intent.json").read_text()),
             "procedure": procedure.model_dump(), "evidence": evidence}, Answer,
        )
        validate_answer(answer, evidence)
        result = {**answer.model_dump(), "preferred_id": pid}
        trace.emit("final_answer", result)
    except Exception as error:
        result = {"status": "error", "value": None, "error_type": type(error).__name__, "error": str(error)}
        trace.emit("error", result)
    finally:
        write_json(directory / "answer.json", result)
        manifest["elapsed_seconds"] = time.monotonic()-started
        manifest["status"] = result["status"]
        write_json(directory / "manifest.json", manifest)
        export(directory, directory / "trajectory.json")
    return result


def trial(row, repetition, settings, vanilla_settings, catalog):
    directory = RUNS / f"repeat-{repetition}" / row["id"]
    if (directory / "complete.json").exists():
        return {"id": row["id"], "repeat": repetition, "status": "already_complete"}
    if directory.exists():
        # Interrupted attempts remain visible; the runner does not replay them.
        raise ValueError(f"Partially completed attempt needs explicit audit, not silent retry: {directory}")
    directory.mkdir(parents=True)
    started = time.monotonic()
    image = Path(row["image"])
    if sha256(image) != row["image_sha256"]:
        raise ValueError("Frozen input changed")
    arms = ["vanilla", "routing"]
    if hashlib.sha256(f'{repetition}:{row["id"]}'.encode()).digest()[0] % 2:
        arms.reverse()
    write_json(directory / "schedule.json", {"id": row["id"], "repeat": repetition, "order": arms, "started_at": datetime.now(timezone.utc).isoformat()})
    statuses = {}
    for arm in arms:
        output = directory / arm
        if arm == "vanilla":
            run(image, row["question"], vanilla_settings, mode="vanilla", output=output)
        else:
            run_route(image, row["question"], settings, CATALOG, output, compare_all=True, executor=locked_execute)
            complete_fixed(output, catalog)
        export(output, output / "trajectory.json")
        answer = json.loads((output / "answer.json").read_text())
        statuses[arm] = answer["status"]
        log({"id": row["id"], "repeat": repetition, "arm": arm, "status": answer["status"], "stage": answer.get("stage"), "review_status": answer.get("review_status")})
    answer = tools_answer(row, directory / "routing", directory / "astra-tools", settings, catalog)
    statuses["astra-tools"] = answer["status"]
    complete = {"id": row["id"], "repeat": repetition, "statuses": statuses,
                "elapsed_seconds": time.monotonic()-started, "completed_at": datetime.now(timezone.utc).isoformat()}
    write_json(directory / "complete.json", complete)
    log({"event": "trial_complete", **complete})
    return complete


def infer():
    protocol = json.loads((REPORT / "protocol.json").read_text())
    if source_hash() != protocol["source_sha256"]:
        raise ValueError("Frozen harness source changed")
    for name, expected in {**protocol["resources_sha256"], **protocol["script_sha256"]}.items():
        if sha256(Path(name)) != expected:
            raise ValueError(f"Frozen resource changed: {name}")
    if sha256(DATA / "inputs.json") != json.loads((REPORT / "input-freeze.json").read_text())["sha256"]:
        raise ValueError("Input manifest changed")
    settings, vanilla_settings = load_settings(CONFIG), load_settings(VANILLA_CONFIG)
    catalog = load_catalog(CATALOG)
    rows = json.loads((DATA / "inputs.json").read_text())
    schedule = [(r, repeat) for repeat in range(1, REPEATS+1) for r in rows]
    random.Random(2026092203).shuffle(schedule)
    RUNS.mkdir(parents=True, exist_ok=True)
    if not (RUNS / "schedule.json").exists():
        write_json(RUNS / "schedule.json", [{"id": r["id"], "repeat": repeat} for r, repeat in schedule])
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(trial, row, repeat, settings, vanilla_settings, catalog): (row["id"], repeat) for row, repeat in schedule}
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as error:
                record = {"id": futures[future][0], "repeat": futures[future][1], "error": str(error)}
                failures.append(record)
                log({"event": "orchestration_failure", **record})
    write_json(RUNS / "inference-finished.json", {"finished_at": datetime.now(timezone.utc).isoformat(),
                                               "attempts": len(schedule), "orchestration_failures": failures,
                                               "source_sha256": source_hash()})
    if failures:
        raise SystemExit("Some attempts failed orchestration; preserve them and score missing outcomes explicitly")
