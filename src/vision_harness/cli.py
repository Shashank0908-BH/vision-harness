"""Human-facing commands. CLI output is a view of saved execution evidence."""

import importlib.metadata
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .config import load_settings
from .contracts import PlanSet, Step
from .routing.cli import app as specialist_app
from .runtime import Mode, run
from .tracing import redact, write_json

app = typer.Typer(
    no_args_is_help=True,
    help="Inspectable Astra + OpenCV + Jev harness.",
    pretty_exceptions_enable=False,
)
tool_app = typer.Typer(no_args_is_help=True, help="Run a perception operation independently.")
app.add_typer(tool_app, name="tool")
app.add_typer(specialist_app, name="specialist")
console = Console()
Config = Annotated[Path, typer.Option(help="Project-relative configuration file.")]


def observe(event):
    kind, data = event["kind"], event["data"]
    console.print(f"[{event['sequence']:03}] {kind}", markup=False)
    if kind in {
        "selection",
        "assessments",
        "answer_review",
        "error",
        "tool_error",
        "evidence_compacted",
        "format_retry",
        "review_feedback",
        "loop_stopped",
        "tool_reused",
        "routing_decision",
        "research_finished",
    }:
        console.print_json(data=data)


def checkpoint(label, data):
    console.print(label)
    console.print_json(data=data)
    if not typer.confirm("Continue?", default=True):
        raise typer.Abort()


@app.command()
def doctor(config: Config = Path("configs/poc.toml"), check_api: bool = False):
    """Check local setup. --check-api explicitly makes small billed requests."""
    settings = load_settings(config)
    checks = {
        "packages": {
            n: importlib.metadata.version(n)
            for n in ("vision-harness", "openai", "opencv-python-headless")
        },
        "keys": {
            "OPENAI_API_KEY": "configured"
            if os.getenv("OPENAI_API_KEY", "").strip()
            else "missing",
            "JEV_API_KEY / TYPESAFE_API_KEY": "configured"
            if (os.getenv("JEV_API_KEY", "").strip() or os.getenv("TYPESAFE_API_KEY", "").strip())
            else "missing",
        },
        "docker_cli": bool(shutil.which("docker")),
        "astra_model": settings.models.astra,
        "jev_model": settings.models.jev,
    }
    try:
        checks["harbor"] = importlib.metadata.version("harbor")
    except importlib.metadata.PackageNotFoundError:
        checks["harbor"] = "not installed; uv sync --extra eval"
    console.print_json(data=checks)
    if check_api:
        from .providers.astra import Astra
        from .providers.jev import Jev
        from .tracing import Trace

        trace = Trace(Path(settings.paths.runs) / f"connection-{uuid.uuid4().hex[:8]}", observe)
        try:
            Astra(settings, trace).answer(
                "Return answered with value 1 as a connection test.", [], {"evidence": []}
            )
            Jev(settings, trace).review(
                {
                    "question": "Is the sky described as blue?",
                    "evidence": "The sky is blue.",
                    "answer": "yes",
                }
            )
        except Exception as error:
            console.print(redact(str(error)), markup=False)
            raise typer.Exit(1) from None
        console.print("Both API connection tests succeeded.")


@app.command("run")
def run_command(
    image: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    prompt: Annotated[str, typer.Option()],
    mode: Mode = "full",
    config: Config = Path("configs/poc.toml"),
    output: Path | None = None,
    step: bool = False,
    model: str | None = None,
    plans: Annotated[
        Path | None,
        typer.Option(help="Replay a saved PlanSet for controlled selection comparisons."),
    ] = None,
    offline: Annotated[
        bool, typer.Option(help="Use deterministic stand-ins; NOT model evaluation.")
    ] = False,
):
    """Analyze an image and save the complete observable run."""
    settings = load_settings(config)
    if model:
        settings.models.astra = model
    frozen = PlanSet.model_validate_json(plans.read_text()) if plans else None
    factories = {}
    if offline:
        from .demo import DemoAstra, DemoJev

        factories = {"astra_factory": DemoAstra, "jev_factory": DemoJev}
        console.print("OFFLINE DEMONSTRATION — no Astra or Jev inference.")
    directory = run(
        image,
        prompt,
        settings,
        mode,
        output=output,
        observer=observe,
        checkpoint=checkpoint if step else None,
        frozen_plans=frozen,
        offline=offline,
        **factories,
    )
    console.print(f"Saved run: {directory}")
    answer = json.loads((directory / "answer.json").read_text())
    console.print_json(data=answer)
    if answer["status"] == "error":
        raise typer.Exit(1)


@tool_app.command("run")
def tool_run(
    name: str,
    request: Annotated[Path, typer.Option(exists=True)],
    config: Config = Path("configs/poc.toml"),
    output: Path | None = None,
):
    """Execute a saved JSON request containing image, input_ref and arguments."""
    from .artifacts import ArtifactStore
    from .tools.dispatch import execute, probe

    settings = load_settings(config)
    payload = json.loads(request.read_text())
    directory = output or Path(settings.paths.runs) / f"tool-{uuid.uuid4().hex[:8]}"
    if directory.exists() and any(directory.iterdir()):
        raise typer.BadParameter("Output must be empty")
    store = ArtifactStore(directory, settings.limits.max_pixels, settings.limits.max_input_bytes)
    store.import_image(Path(payload["image"]))
    result = (
        probe(store)
        if name == "probe"
        else execute(
            Step(
                step_id="standalone",
                tool=name,
                input_ref="original",
                arguments=payload["arguments"],
            ),
            "original",
            "standalone",
            store,
        )
    )
    write_json(directory / "evidence.json", result.model_dump())
    console.print_json(data=result.model_dump())
    console.print(f"Saved artifacts: {directory}")


def resolve_run(value: str) -> Path:
    path = Path(value)
    return path if path.is_dir() else Path("runs") / value


@app.command("inspect")
def inspect_run(run_id: str):
    """Show a saved run's configuration and final answer."""
    directory = resolve_run(run_id)
    for name in ("manifest.json", "answer.json"):
        console.print(name)
        console.print_json((directory / name).read_text())


@app.command()
def replay(run_id: str):
    """Display every recorded event; makes no API calls and executes no tools."""
    for line in (resolve_run(run_id) / "events.jsonl").read_text().splitlines():
        console.print_json(line)


@app.command("export")
def export_run(run_id: str, output: Path | None = None):
    """Export and validate an ATIF trajectory (requires eval extra)."""
    from evals.atif import export

    directory = resolve_run(run_id)
    target = output or directory / "trajectory.json"
    export(directory, target)
    console.print(f"Validated trajectory: {target}")


@app.command()
def dataset(
    output: Path = Path("evals/datasets/generated"),
    dev: int = 20,
    test: int = 60,
    seed: int = 20260922,
):
    """Generate versioned synthetic images with independent ground-truth labels."""
    from evals.generate_dataset import generate

    generate(output, dev, test, seed)
    console.print(f"Dataset: {output}")


@app.command("build-tasks")
def build_tasks(
    dataset: Path = Path("evals/datasets/generated"),
    output: Path = Path("evals/tasks/generated/current"),
    split: str = "dev",
    limit: int = 0,
):
    """Package images into self-contained Harbor tasks; excludes secrets and labels from agent image."""
    from evals.build_tasks import build

    build(dataset, output, split, limit)
    console.print(f"Harbor tasks: {output}")


@app.command("eval")
def evaluate(config: Path = Path("configs/evaluation.toml"), offline: bool = False):
    """Run Harbor jobs. Offline mode verifies plumbing, never model quality."""
    from evals.run import launch

    launch(config, offline)


@app.command()
def report(jobs: Path = Path("jobs"), output: Path = Path("jobs/comparison.json")):
    """Summarize completed trials, separating offline and live runs."""
    from evals.report import summarize

    result = summarize(jobs)
    write_json(output, result)
    console.print_json(data=result)


if __name__ == "__main__":
    app()
