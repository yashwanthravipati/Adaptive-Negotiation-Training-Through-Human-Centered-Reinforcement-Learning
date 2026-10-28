"""Check the exact Binomial oracle with the app's full error/fact/rapport action space."""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np

from negotrain.evaluation import POLICIES, interval, write_json
from negotrain.profiling.belief import BeliefState, BetaBelief, CostModel, choose_focus
from negotrain.profiling.observations import ERRORS, Count, Observations
from negotrain.virtual_users import VirtualTraits


def main():
    root = Path("results/sim3/offline-v1")
    costs = CostModel.model_validate_json((root / "costs.json").read_text())
    tuning = json.loads((root / "tuning.json").read_text())["selected"]
    population_rng = random.Random(302822)
    rows = []
    for uid in range(512):
        original = VirtualTraits.sample(population_rng)
        for policy in POLICIES:
            state = original.model_copy(deep=True)
            rng = np.random.default_rng(302822 + uid)
            planner_rng = random.Random(302822 + uid)
            belief = BeliefState(
                components={k: BetaBelief() for k in costs.population},
                forgetting=tuning["forgetting"],
            )
            focuses = []
            for _ in range(5):
                focus = choose_focus(
                    belief, costs, policy=policy, kappa=tuning["kappa"], rng=planner_rng
                )
                focuses.append(focus)
                truth = {
                    k: state.errors[k]
                    if k in ERRORS
                    else state.rapport
                    if k == "rapport"
                    else state.awareness
                    for k in belief.components
                }
                counts = {}
                for key in belief.components:
                    o = int(rng.poisson(costs.opportunities[key]))
                    counts[key] = Count(
                        opportunities=o, occurrences=int(rng.binomial(o, truth[key]))
                    )
                belief.update(Observations(counts=counts, score=None))
                state.learn(focus)
            rows.append(
                {
                    "user": uid,
                    "policy": policy,
                    "focuses": focuses,
                    "true_error_cost_reduction": sum(
                        costs.cost(k) * (original.errors[k] - state.errors[k]) for k in ERRORS
                    ),
                }
            )
    out = Path("results/sim3/validation")
    write_json(out / "full_action_oracle_rows.json", rows)
    write_json(
        out / "full_action_oracle.json",
        {
            "users": 512,
            "seed": 302822,
            "tuning": tuning,
            "assumptions": (
                "Independent Binomial counts for every component. Fact probabilities share the "
                "sampled awareness parameter and synthetic 30% deficit improvement. Opportunity "
                "rates fixed at calibrated focused means. Reward counts only error reductions, "
                "per new-spec."
            ),
            "policies": {
                p: interval([r["true_error_cost_reduction"] for r in rows if r["policy"] == p])
                for p in POLICIES
            },
        },
    )


if __name__ == "__main__":
    main()
