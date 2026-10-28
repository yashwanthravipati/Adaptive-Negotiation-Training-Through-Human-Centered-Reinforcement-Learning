"""Rebuild the opportunity-based belief from persisted, finished transcripts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from negotrain.profiling.belief import BeliefState, BetaBelief, CostModel
from negotrain.profiling.observations import ERRORS, case_facts, failure_turns, observe
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
    planning_kappa: float = Field(default=1.0, ge=0)
    calibration_source: str | None = None


class CaseCalibration(BaseModel):
    case_sha256: str
    role: str
    costs: CostModel
    forgetting: float = Field(gt=0, le=1)
    kappa: float = Field(ge=0)
    source: str


def load_calibration(case: Case, role: str, directory: Path) -> CaseCalibration | None:
    """Never apply inferred utilities' calibration to another case or role."""
    digest = hashlib.sha256(case.model_dump_json().encode()).hexdigest()
    for path in sorted(directory.glob("*.json")):
        calibration = CaseCalibration.model_validate_json(path.read_text())
        if calibration.case_sha256 == digest and calibration.role == role:
            return calibration
    return None


def build_profile(
    participant_id: str,
    history: list[tuple[Session, Case]],
    *,
    forgetting: float = 0.8,
    discount_prior: bool = False,
    costs: CostModel | None = None,
    reports: dict[str, CounterfactualReport] | None = None,
    context: tuple[Case, str] | None = None,
    calibration: CaseCalibration | None = None,
) -> NegotiatorProfile:
    if calibration:
        if (
            context is None
            or calibration.case_sha256
            != hashlib.sha256(context[0].model_dump_json().encode()).hexdigest()
            or calibration.role != context[1]
        ):
            raise ValueError("calibration does not match the active case and role")
        forgetting, costs = calibration.forgetting, calibration.costs
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
    if context:
        facts = case_facts(*context)
        labels.update({f.id: f.description for f in facts})
        belief.components.update({f.id: BetaBelief() for f in facts})
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
                    for key in observation.counts:
                        if estimate.turn_index in failure_turns(session, observation, key):
                            personal_costs.add(key, estimate.delta)
    return NegotiatorProfile(
        participant_id=participant_id,
        n_sessions=len(finished),
        belief=belief,
        labels=labels,
        costs=personal_costs,
        untagged_user_turns=untagged,
        planning_kappa=calibration.kappa if calibration else 1.0,
        calibration_source=calibration.source if calibration else None,
    )
