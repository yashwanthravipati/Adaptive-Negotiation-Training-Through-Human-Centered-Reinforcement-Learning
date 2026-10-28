"""Rebuild the opportunity-based belief from persisted, finished transcripts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from negotrain.profiling.belief import BeliefState, BetaBelief, CostModel
from negotrain.profiling.observations import ERRORS, case_facts, observe
from negotrain.schemas import Case, Session

if TYPE_CHECKING:
    from negotrain.feedback.rollouts import CounterfactualReport


class NegotiatorProfile(BaseModel):
    participant_id: str
    n_sessions: int
    belief: BeliefState
    labels: dict[str, str]
    costs: CostModel = Field(default_factory=CostModel)
    untagged_user_turns: int = 0


def build_profile(
    participant_id: str,
    history: list[tuple[Session, Case]],
    *,
    forgetting: float = 0.8,
    discount_prior: bool = False,
    costs: CostModel | None = None,
    reports: dict[str, CounterfactualReport] | None = None,
) -> NegotiatorProfile:
    finished = sorted(
        [(s, c) for s, c in history if s.status in ("agreed", "impasse") and s.turns],
        key=lambda item: item[0].created_at,
    )
    belief = BeliefState(
        components={k: BetaBelief() for k in [*ERRORS, "rapport"]},
        forgetting=forgetting,
        discount_prior=discount_prior,
    )
    labels = {**ERRORS, "rapport": "Building rapport"}
    untagged = 0
    personal_costs = costs.model_copy(deep=True) if costs else CostModel()
    for session, case in finished:
        labels.update({f.id: f.description for f in case_facts(case, session.user_role_id)})
        observation = observe(session, case)
        belief.update(observation)
        untagged += observation.untagged_user_turns
        report = (reports or {}).get(session.id)
        if report is not None and report.reward == "surplus_share":
            for estimate in report.estimates:
                if estimate.delta is not None:
                    for key in ERRORS:
                        if estimate.turn_index in observation.counts[key].turns:
                            personal_costs.add(key, estimate.delta)
    return NegotiatorProfile(
        participant_id=participant_id,
        n_sessions=len(finished),
        belief=belief,
        labels=labels,
        costs=personal_costs,
        untagged_user_turns=untagged,
    )
