"""Offline robustness checks for a saved simulation cohort; never makes API calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

from negotrain.cases import load_case
from negotrain.cases.offers import best_points
from negotrain.counterpart import RuleBasedCounterpart
from negotrain.evaluation import (
    Experiment,
    correlation,
    grounded_training,
    initial_belief,
    interval,
    write_json,
)
from negotrain.feedback import analyze_session
from negotrain.profiling.belief import CostModel
from negotrain.profiling.observations import observe
from negotrain.schemas import Session, Turn, TurnTags


def load_session(path):
    return Session.model_validate(json.loads(path.read_text())["session"])


def auc(labels, scores):
    positive = np.asarray(labels, dtype=bool)
    n1, n0 = positive.sum(), (~positive).sum()
    if not n1 or not n0:
        return None
    return float((rankdata(scores)[positive].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def expanded_recovery(case, role, root, output):
    config = json.loads((root / "config.json").read_text())
    tuning = json.loads((root / "tuning.json").read_text())["selected"]
    records = []
    for uid in range(config["recovery_users"]):
        belief = initial_belief(case, role, tuning["forgetting"])
        keys = list(belief.components)
        halves = [{key: [0, 0] for key in keys} for _ in range(2)]
        reference = {key: [0, 0] for key in keys}
        for t in range(5):
            obs = observe(load_session(root / "raw" / f"recover{uid}_train{t}.json"), case)
            belief.update(obs)
            for key in keys:
                halves[t % 2][key][0] += obs.counts[key].occurrences
                halves[t % 2][key][1] += obs.counts[key].opportunities
        for t in range(config["reference_sessions"]):
            obs = observe(load_session(root / "raw" / f"recover{uid}_reference{t}.json"), case)
            for key in keys:
                reference[key][0] += obs.counts[key].occurrences
                reference[key][1] += obs.counts[key].opportunities
        for key in keys:
            x, o = reference[key]
            lo, hi = belief.components[key].interval()
            records.append(
                {
                    "user": uid,
                    "component": key,
                    "posterior": belief.components[key].mean,
                    "reference": x / o if o else None,
                    "reference_opportunities": o,
                    "covered_reference": lo <= x / o <= hi if o else None,
                    "halves": [(1 + a[key][0]) / (2 + a[key][1]) for a in halves],
                }
            )
    summary = {}
    for key in keys:
        rows = [r for r in records if r["component"] == key and r["reference"] is not None]
        summary[key] = {
            "n": len(rows),
            "reference_above_half": sum(r["reference"] >= 0.5 for r in rows),
            "rmse": float(np.sqrt(np.mean([(r["posterior"] - r["reference"]) ** 2 for r in rows]))),
            "coverage_of_mc_reference": float(np.mean([r["covered_reference"] for r in rows])),
            "auc_reference_above_half": auc(
                [r["reference"] >= 0.5 for r in rows], [r["posterior"] for r in rows]
            ),
            "split_half_spearman": correlation(
                [r["halves"][0] for r in rows], [r["halves"][1] for r in rows]
            ),
        }
    write_json(output / "recovery_all_rows.json", records)
    write_json(output / "recovery_all.json", summary)


def credit_checks(case, role, root, output, users=12):
    records, blunders = [], []
    for uid in range(users):
        session = load_session(root / "raw" / f"steer{uid}_tier3.json")

        def factory(session=session):
            return RuleBasedCounterpart(
                case, session.counterpart_role_id, session.counterpart_profile
            )

        reports = {
            n: analyze_session(
                session, case, factory, opponent="rule-based", cap=3, n=n, max_workers=1
            )
            for n in (4, 5, 16)
        }
        for estimates in zip(*(reports[n].estimates for n in (4, 5, 16)), strict=True):
            records.append(
                {
                    "user": uid,
                    "turn": estimates[0].turn_index,
                    **{str(n): e.delta for n, e in zip((4, 5, 16), estimates, strict=True)},
                }
            )
        # Replace the first answer to an opening with an early acceptance. This is a
        # known intervention, not a claim that every early acceptance is actually bad.
        opening = next((t for t in session.turns if t.speaker == "counterpart" and t.offer), None)
        if opening is None:
            continue
        planted = session.model_copy(
            deep=True,
            update={
                "turns": session.turns[: opening.index + 1],
                "status": "active",
                "agreement": None,
            },
        )
        planted.add_turn(
            Turn(
                index=len(planted.turns),
                speaker="user",
                text="I accept.",
                accept=True,
                tags=TurnTags(source="scripted"),
            ),
            case,
        )
        report = analyze_session(
            planted, case, factory, opponent="rule-based", cap=None, n=16, max_workers=1
        )
        scores = [(e.turn_index, e.delta) for e in report.estimates if e.delta is not None]
        target = next(v for i, v in scores if i == len(planted.turns) - 1)
        # Ties share rank 1. A one-turn episode has no ranking discrimination.
        blunders.append(
            {
                "user": uid,
                "delta": target,
                "competing_turns": len(scores),
                "rank": 1 + sum(v > target for _, v in scores),
            }
        )
    summary = {
        "sessions": users,
        "estimated_turns": len(records),
        "small_M_vs_16": {
            str(n): {
                "spearman": correlation([r[str(n)] for r in records], [r["16"] for r in records]),
                "mean_absolute_difference": float(
                    np.mean([abs(r[str(n)] - r["16"]) for r in records])
                ),
                "sign_agreement": float(
                    np.mean([np.sign(r[str(n)]) == np.sign(r["16"]) for r in records])
                ),
            }
            for n in (4, 5)
        },
        "early_acceptance": {
            "mean_delta": interval([r["delta"] for r in blunders]),
            "positive_fraction": float(np.mean([r["delta"] > 0 for r in blunders])),
            "multi_turn_top_rank_fraction": float(
                np.mean([r["rank"] == 1 for r in blunders if r["competing_turns"] > 1])
            )
            if any(r["competing_turns"] > 1 for r in blunders)
            else None,
            "multi_turn_cases": sum(r["competing_turns"] > 1 for r in blunders),
        },
        "limitation": "M=16 is a larger Monte Carlo reference, not ground truth; no human ratings.",
    }
    write_json(output / "credit_rows.json", records)
    write_json(output / "planted_acceptance_rows.json", blunders)
    write_json(output / "credit.json", summary)


def sensitivity(case, role, root, output, users):
    costs = CostModel.model_validate_json((root / "costs.json").read_text())
    tuning = json.loads((root / "tuning.json").read_text())
    source = b"".join(p.read_bytes() for p in sorted(Path("src/negotrain").rglob("*.py")))
    summary = {}
    for i, name in enumerate(
        ("lower_walkaways", "higher_walkaways", "issue_weights_1", "issue_weights_2")
    ):
        variant = case.model_copy(deep=True)
        rng = random.Random(7822 + i)
        for sheet in variant.roles:
            maximum = best_points(case, sheet.id)
            if i < 2:
                sheet.reservation_value += (
                    (-1 if i == 0 else 1) * 0.1 * (maximum - sheet.reservation_value)
                )
            else:
                weights = {key: math.exp(rng.gauss(0, 0.2)) for key in sheet.points}
                weighted_max = sum(
                    max(table.values()) * weights[key] for key, table in sheet.points.items()
                )
                sheet.points = {
                    key: {
                        option: value * weights[key] * maximum / weighted_max
                        for option, value in table.items()
                    }
                    for key, table in sheet.points.items()
                }
        exp = Experiment(
            variant,
            role,
            output / name,
            {
                "variant": name,
                "users": users,
                "seed": 602822,
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "calibration": "primary offline-v1 costs and tuning held fixed",
                "perturbation": (
                    "BATNA +/-10% of own range, or log-normal issue weights "
                    "sigma=.2 preserving own maximum"
                ),
            },
        )
        # Persist the precise case locally for independent reruns; raw is ignored.
        write_json(exp.raw / "case.json", variant.model_dump(mode="json"))
        summary[name] = grounded_training(exp, costs, tuning, users, 602822)
    write_json(output / "sensitivity.json", summary)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--case", type=Path, default=Path("data/cases/private/sim3_inferred.json"))
    p.add_argument("--role", default="officer")
    p.add_argument("--input", type=Path, default=Path("results/sim3/offline-v1"))
    p.add_argument("--output", type=Path, default=Path("results/sim3/validation"))
    p.add_argument("--users", type=int, default=64)
    p.add_argument("--stage", choices=["all", "inference", "credit", "sensitivity"], default="all")
    args = p.parse_args()
    case = load_case(args.case)
    for name, fn in [
        ("inference", expanded_recovery),
        ("credit", credit_checks),
        ("sensitivity", sensitivity),
    ]:
        if args.stage in ("all", name):
            kwargs = {"users": args.users} if name == "sensitivity" else {}
            fn(case, args.role, args.input, args.output, **kwargs)
            print(f"{name} complete", flush=True)


if __name__ == "__main__":
    main()
