"""Standalone scientific figures; run with system Python (matplotlib installed)."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPORT = Path(__file__).resolve().parents[2] / "reports/kromp-repeated-20260922"


def save_figure(fig, name):
    for suffix in ["png", "svg"]:
        path = REPORT / f"{name}.{suffix}"
        fig.savefig(path, dpi=180, bbox_inches="tight")
        if suffix == "svg":
            path.write_text(
                "\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n"
            )


def main():
    data = json.loads((REPORT / "results.json").read_text())
    arms = [
        "vanilla",
        "astra_tools_paired",
        "jev_selection_stage",
        "full_harness",
        "stardist-default",
        "stardist-sensitive",
        "stardist-conservative",
        "cellpose-sam",
    ]
    labels = [
        "Vanilla Astra",
        "Astra + preferred specialist¹",
        "Astra + Jev selection²",
        "Full current harness",
        "Fixed StarDist default",
        "Fixed StarDist sensitive",
        "Fixed StarDist conservative",
        "Fixed Cellpose-SAM",
    ]
    colors = [
        "#70828b",
        "#36a0a5",
        "#187f94",
        "#064f6b",
        "#b6966d",
        "#bc8444",
        "#967148",
        "#6c8b45",
    ]
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, ax = plt.subplots(figsize=(10, 6.6))
    y = np.arange(len(arms))
    rates = [data["metrics"][a]["all_attempt_success_at_10_percent"] * 100 for a in arms]
    ax.barh(y, rates, color=colors, height=0.62)
    for i, arm in enumerate(arms):
        groups = {}
        for r in data["records"]:
            v = r["values"].get(arm)
            success = v is not None and abs(v - r["expected"]) / r["expected"] <= 0.1
            groups.setdefault(r["id"], []).append(float(success))
        means = np.array([np.mean(v) * 100 for v in groups.values()])
        boot = (
            np.random.default_rng(2026092203)
            .choice(means, (10000, len(means)), replace=True)
            .mean(axis=1)
        )
        lo, hi = np.percentile(boot, [2.5, 97.5])
        mean = float(means.mean())
        ax.errorbar(
            mean, i, xerr=[[mean - lo], [hi - mean]], color="#172d36", capsize=4, fmt="none", lw=1.4
        )
        m = data["metrics"][arm]
        ax.text(102, i, f"{m['within_10_percent']}/111", va="center", fontsize=9)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 113)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.set_xlabel("Count within 10% of reference (% of all scheduled attempts)")
    ax.set_title(
        "Reliable counts across the entire schedule", loc="left", fontweight="bold", pad=18
    )
    ax.grid(axis="x", alpha=0.15)
    ax.set_axisbelow(True)
    fig.text(
        0.02,
        0.015,
        "Missing answers count as failures. Whiskers: 95% image-cluster bootstrap intervals.\n¹ Shared proposal, separate answer. ² Saved pre-review stage. 37 images × 3 repetitions; not 111 independent images.",
        fontsize=8,
        color="#415b63",
    )
    fig.tight_layout(rect=(0, 0.075, 1, 1))
    save_figure(fig, "count-success")
    plt.close(fig)
    heat_arms = [
        "vanilla",
        "astra_tools_paired",
        "jev_selection_stage",
        "full_harness",
        "stardist-sensitive",
        "cellpose-sam",
    ]
    heat_labels = [
        "Vanilla",
        "Astra-tools¹",
        "Selection²",
        "Full",
        "StarDist\nsensitive",
        "Cellpose-SAM",
    ]
    classes = list(data["by_class"])
    values = np.array(
        [
            [
                data["by_class"][c][a]["conditional_mape_percent"]
                if data["by_class"][c][a]["conditional_mape_percent"] is not None
                else np.nan
                for a in heat_arms
            ]
            for c in classes
        ]
    )
    fig, ax = plt.subplots(figsize=(9, 7.3))
    heat = ax.imshow(np.ma.masked_invalid(values), cmap="YlOrRd", vmin=0, vmax=100, aspect="auto")
    ax.set_yticks(range(len(classes)), classes)
    ax.set_xticks(range(len(heat_arms)), heat_labels)
    for i, c in enumerate(classes):
        for j, a in enumerate(heat_arms):
            m = data["by_class"][c][a]
            v = values[i, j]
            label = "missing" if np.isnan(v) else f"{v:.1f}%"
            label += f"\n{m['completed']}/{m['attempts']}"
            ax.text(
                j,
                i,
                label,
                ha="center",
                va="center",
                fontsize=8,
                color="white" if v > 65 else "#243438",
            )
    ax.set_title(
        "Where errors concentrate: published test groups", loc="left", fontweight="bold", pad=18
    )
    fig.colorbar(heat, ax=ax, label="Conditional count MAPE (%); color saturates at 100%")
    fig.text(
        0.02,
        0.015,
        "Each cell: error on returned counts, then completed/scheduled trials. Lower is better.\nConditional error must be read with coverage; low error with many abstentions does not establish a better system.",
        fontsize=8,
        color="#415b63",
    )
    fig.tight_layout(rect=(0, 0.075, 1, 1))
    save_figure(fig, "group-errors")
    plt.close(fig)


if __name__ == "__main__":
    main()
