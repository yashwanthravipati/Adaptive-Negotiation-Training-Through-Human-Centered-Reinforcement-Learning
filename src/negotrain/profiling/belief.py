"""Discounted Beta filter and cost-weighted upper-confidence planning."""

from __future__ import annotations

import math
import random
from typing import Literal

from pydantic import BaseModel, Field

from negotrain.profiling.observations import Observations


class BetaBelief(BaseModel):
    alpha: float = Field(default=1.0, gt=0)
    beta: float = Field(default=1.0, gt=0)
    alpha0: float = Field(default=1.0, gt=0)
    beta0: float = Field(default=1.0, gt=0)
    opportunities: int = 0

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def sd(self) -> float:
        a, b = self.alpha, self.beta
        return math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))

    def interval(self, mass: float = 0.95) -> tuple[float, float]:
        from scipy.stats import beta

        lo, hi = beta.ppf([(1 - mass) / 2, (1 + mass) / 2], self.alpha, self.beta)
        return float(lo), float(hi)

    def update(self, x: int, o: int, forgetting: float, *, discount_prior: bool = False) -> None:
        if not 0 < forgetting <= 1 or not 0 <= x <= o:
            raise ValueError("invalid forgetting factor or counts")
        # Default: new-spec.md's fixed prior + discounted evidence. The alternative
        # implements report.tex verbatim and is included in sensitivity experiments.
        a0, b0 = (0.0, 0.0) if discount_prior else (self.alpha0, self.beta0)
        self.alpha = a0 + forgetting * (self.alpha - a0) + x
        self.beta = b0 + forgetting * (self.beta - b0) + o - x
        self.opportunities += o


class BeliefState(BaseModel):
    components: dict[str, BetaBelief] = Field(default_factory=dict)
    sessions: int = 0
    forgetting: float = Field(default=0.8, gt=0, le=1)
    discount_prior: bool = False

    def update(self, observations: Observations) -> None:
        for key in self.components.keys() | observations.counts.keys():
            posterior = self.components.setdefault(key, BetaBelief())
            count = observations.counts.get(key)
            posterior.update(
                count.occurrences if count else 0,
                count.opportunities if count else 0,
                self.forgetting,
                discount_prior=self.discount_prior,
            )
        self.sessions += 1


class CostModel(BaseModel):
    """Population fallback and per-user mean Δ per error occurrence (units: R)."""

    population: dict[str, float] = Field(default_factory=dict)
    opportunities: dict[str, float] = Field(default_factory=dict)
    loss_sum: dict[str, float] = Field(default_factory=dict)
    occurrences: dict[str, int] = Field(default_factory=dict)

    def weight(self, key: str) -> float:
        n = self.occurrences.get(key, 0)
        return self.loss_sum[key] / n if n else self.population.get(key, 1.0)

    def add(self, key: str, delta: float) -> None:
        self.loss_sum[key] = self.loss_sum.get(key, 0.0) + delta
        self.occurrences[key] = self.occurrences.get(key, 0) + 1

    def cost(self, key: str) -> float:
        return self.weight(key) * self.opportunities.get(key, 1.0)


def choose_focus(
    belief: BeliefState,
    costs: CostModel,
    *,
    policy: Literal["ucb", "greedy", "random", "none"] = "ucb",
    kappa: float = 1.0,
    rng: random.Random | None = None,
    candidates: list[str] | None = None,
) -> str | None:
    keys = sorted(candidates if candidates is not None else belief.components)
    if policy == "none" or not keys:
        return None
    if policy == "random":
        if rng is None:
            raise ValueError("random planning requires an explicit seeded RNG")
        return rng.choice(keys)
    if policy not in ("ucb", "greedy") or kappa < 0:
        raise ValueError("invalid planner configuration")

    def value(key: str) -> float:
        b = belief.components[key]
        deficit = b.mean if key.startswith("error:") else 1 - b.mean
        return costs.cost(key) * (deficit + (kappa * b.sd if policy == "ucb" else 0))

    return max(keys, key=value)
