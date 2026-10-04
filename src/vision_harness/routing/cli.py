"""CLI wiring only; algorithms remain independently importable."""

import uuid
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ..config import load_settings
from .catalog import load_catalog, verify_procedure

app = typer.Typer(
    no_args_is_help=True,
    help="Research and route versioned specialist procedures.",
    pretty_exceptions_enable=False,
)
console = Console()


@app.command("catalog")
def catalog_command(path: Path = Path("catalog/microscopy-v1.json"), verify: bool = False):
    """Inspect complete procedures; --verify checks local checkpoint hashes."""
    catalog = load_catalog(path)
    console.print_json(data=catalog.model_dump())
    if verify:
        for procedure in catalog.procedures:
            console.print_json(data=verify_procedure(procedure))


@app.command("run")
def run_command(
    image: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    prompt: Annotated[str, typer.Option()],
    catalog: Path = Path("catalog/microscopy-v1.json"),
    config: Path = Path("configs/routing.toml"),
    output: Path | None = None,
    compare_all: bool = False,
):
    """Save Astra/Jev rankings before specialist execution and inspect every stage."""
    from ..cli import observe
    from .runtime import run_route

    output = output or Path("runs") / f"routing-{uuid.uuid4().hex[:8]}"
    result = run_route(image, prompt, load_settings(config), catalog, output, compare_all, observe)
    # ATIF is optional outside the evaluation installation; other export failures are errors.
    try:
        from evals.atif import export
    except ImportError:
        console.print("Install the eval extra for Harbor ATIF export.")
    else:
        export(output, output / "trajectory.json")
    console.print_json(data=result)
    console.print(f"Saved: {output}")
    if result["status"] == "error":
        raise typer.Exit(1)


@app.command("research")
def research_command(
    query: Annotated[str, typer.Option()],
    config: Path = Path("configs/routing.toml"),
    output: Path | None = None,
):
    """Make billed web research + Jev calls; save proposals without installing them."""
    from ..cli import observe
    from .research import research

    output = output or Path("runs") / f"research-{uuid.uuid4().hex[:8]}"
    result = research(query, load_settings(config), output, observe)
    console.print_json(data={"ranking": result["ranking"], "advisory_only": True})
    console.print(f"Sourced proposals and scores: {output}")


@app.command("compare")
def compare_command(
    image: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    prompt: Annotated[str, typer.Option()],
    catalog: Path = Path("catalog/microscopy-v1.json"),
    config: Path = Path("configs/evidence-routing.toml"),
    vanilla_config: Path = Path("configs/poc-adaptive.toml"),
    output: Path | None = None,
):
    """Experiment: execute up to four specialists, then select alongside vanilla Astra."""
    from ..cli import observe
    from ..evidence_routing.runtime import run_comparison

    def observe_comparison(event):
        observe(event)
        if event["kind"] in {"candidate_excluded", "candidates_frozen", "output_decision"}:
            console.print_json(data=event["data"])

    output = output or Path("runs") / f"observed-{uuid.uuid4().hex[:8]}"
    result = run_comparison(
        image,
        prompt,
        load_settings(config),
        load_settings(vanilla_config),
        catalog,
        output,
        observe_comparison,
    )
    try:
        from evals.atif import export
    except ImportError:
        console.print("Install the eval extra for Harbor ATIF export.")
    else:
        export(output, output / "trajectory.json")
    console.print_json(data=result)
    console.print(f"Saved: {output}")
    if result["status"] == "error":
        raise typer.Exit(1)
