"""Render numeric sim3 artifacts into reproducible figures and session summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from negotrain.cases import load_case
from negotrain.evaluation import correlation, interval, metrics, write_json
from negotrain.schemas import Session

POLICIES = ("ucb", "greedy", "random", "none")
LABELS = ("Adaptive (κ=0)", "Greedy", "Random focus", "No focus")


def read(path):
    return json.loads(path.read_text())


def session_summary(case, root):
    records = []
    for path in sorted((root / "raw").glob("*.json")):
        data = read(path)
        if "session" not in data or not data.get("complete"):
            continue
        session = Session.model_validate(data["session"])
        key = path.stem
        records.append(
            {
                "id": key,
                "tier": session.counterpart_profile.tier,
                "focus": session.counterpart_profile.focus,
                "schedule_violations": data["schedule_violations"],
                **metrics(session, case),
            }
        )
    grouped = {}
    for policy in POLICIES:
        subset = [r for r in records if f"_{policy}_train" in r["id"]]
        if not subset:
            continue
        keys = list(subset[0]["counts"])
        grouped[policy] = {
            "episodes": len(subset),
            "mean_R": float(np.mean([r["R"] for r in subset])),
            "agreement_rate": float(np.mean([r["agreement"] for r in subset])),
            "counts": {
                k: {field: sum(r["counts"][k][field] for r in subset) for field in ("o", "x")}
                for k in keys
            },
        }
    baseline = [r for r in records if "_baseline_" in r["id"]]
    tiers = {str(t): interval([r["R"] for r in baseline if r["tier"] == t]) for t in (1, 3, 5)}
    result = {
        "completed_sessions": len(records),
        "schedule_violations": sum(r["schedule_violations"] for r in records),
        "training_by_policy": grouped,
        "baseline_tiers": tiers,
        "baseline_tier_spearman": correlation([1, 3, 5], [tiers[str(t)]["mean"] for t in (1, 3, 5)])
        if all(tiers[str(t)]["n"] for t in (1, 3, 5))
        else None,
    }
    if root.name.startswith("live"):
        write_json(root / "session_rows.json", records)
    write_json(root / "sessions.json", result)
    return result


def points(ax, entries, labels, color="#265c8c"):
    means = np.array([d["mean"] for d in entries])
    bounds = np.array([d["ci95"] for d in entries]).T
    ax.errorbar(
        means,
        np.arange(len(labels)),
        xerr=[means - bounds[0], bounds[1] - means],
        fmt="o",
        capsize=4,
        color=color,
    )
    ax.set_yticks(np.arange(len(labels)), labels)
    ax.invert_yaxis()
    ax.axvline(0, color="#aaaaaa", linewidth=0.8)
    ax.grid(axis="x", alpha=0.18)
    ax.spines[["top", "right"]].set_visible(False)


def figures(root):
    plt.rcParams["svg.hashsalt"] = "negotrain-sim3"
    plt.rcParams["svg.fonttype"] = "none"
    offline = root / "offline-v1"
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    tiers = read(offline / "steering.json")["tiers"]
    vals = [tiers[str(i)]["R"] for i in range(1, 6)]
    m = np.array([d["mean"] for d in vals])
    b = np.array([d["ci95"] for d in vals]).T
    axes[0, 0].errorbar(
        range(1, 6), m, yerr=[m - b[0], b[1] - m], fmt="o-", capsize=4, color="#265c8c"
    )
    axes[0, 0].set(
        title="Counterpart steering · 32 scripted users",
        xlabel="Tier",
        ylabel="Terminal surplus share R",
        xticks=range(1, 6),
    )
    axes[0, 0].grid(alpha=0.18)
    train = read(offline / "training.json")
    points(axes[0, 1], [train[p]["competence_gain"] for p in POLICIES], LABELS)
    axes[0, 1].set(
        title="Grounded learning · 128 scripted users", xlabel="Held-out G gain after 5 rehearsals"
    )
    oracle = read(root / "validation" / "full_action_oracle.json")["policies"]
    points(
        axes[1, 0],
        [oracle[p] for p in POLICIES],
        LABELS,
        "#a35c20",
    )
    axes[1, 0].set(
        title="Full-action Binomial oracle · 512 users",
        xlabel="True error-cost reduction (oracle units)",
    )
    live = root / "live-v1" / "training.json"
    if live.exists():
        data = read(live)
        points(axes[1, 1], [data[p]["competence_gain"] for p in POLICIES], LABELS, "#38755b")
        axes[1, 1].set(
            title=f"LLM personas · {data['ucb']['competence_gain']['n']} users",
            xlabel="Held-out G gain after 5 rehearsals",
        )
    else:
        axes[1, 1].text(
            0.5,
            0.5,
            "LLM cohort running; no completed estimate",
            ha="center",
            va="center",
            transform=axes[1, 1].transAxes,
        )
        axes[1, 1].axis("off")
    fig.suptitle("sim3 evaluation · inferred utilities · user-bootstrap 95% intervals", fontsize=14)
    svg = root / "evaluation.svg"
    fig.savefig(svg, metadata={"Date": None})
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    fig.savefig(root / "evaluation.png", dpi=170)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, default=Path("data/cases/private/sim3_inferred.json"))
    parser.add_argument("--root", type=Path, default=Path("results/sim3"))
    args = parser.parse_args()
    case = load_case(args.case)
    for name in ("offline-v1", "live-v1"):
        if (args.root / name / "config.json").exists():
            summary = session_summary(case, args.root / name)
            print(
                name,
                summary["completed_sessions"],
                "sessions,",
                summary["schedule_violations"],
                "schedule violations",
            )
    figures(args.root)


if __name__ == "__main__":
    main()
