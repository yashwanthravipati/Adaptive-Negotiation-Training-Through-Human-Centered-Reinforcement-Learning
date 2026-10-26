"""Tailored scenario selection (T-027): choose the next counterpart tier and dial emphasis
that target a negotiator's weakest skill while raising difficulty gradually.

Rule-based on purpose (PLAN.md §3): step the tier up after two strong rehearsals in a row,
down after an impasse or a weak result, and bend the counterpart's dials toward the
situation that exercises the weakest skill.
"""

from __future__ import annotations

import random

from pydantic import BaseModel, Field

from negotrain.counterpart.profiles import sample_profile
from negotrain.profiling import NegotiatorProfile, extract_features
from negotrain.schemas import Case, CounterpartProfile, Session

START_TIER = 2

# Which counterpart behavior makes a weak skill matter.
FOCUS_DIALS: dict[str, tuple[dict[str, float], str]] = {
    "anchoring": (
        {"anchoring": 0.9},
        "a counterpart that anchors aggressively, so you practice opening ambitiously and "
        "not letting their number set the range",
    ),
    "concession_discipline": (
        {"concession_rate": 0.15, "aggression": 0.6},
        "a counterpart that concedes slowly and applies pressure, so you practice conceding "
        "in small, reciprocated steps",
    ),
    "information_gathering": (
        {"disclosure": 0.85, "cooperativeness": 0.6},
        "a counterpart that shares its priorities when asked, so questions pay off",
    ),
    "value_creation": (
        {"cooperativeness": 0.85, "disclosure": 0.6},
        "a cooperative counterpart with room for trades across issues",
    ),
    "value_claiming": (
        {"anchoring": 0.8, "bluffing": 0.5},
        "a counterpart that claims hard and overstates its alternatives",
    ),
    "closing": (
        {"concession_rate": 0.5, "aggression": 0.3},
        "a reasonable counterpart, so you practice recognizing and closing a good deal",
    ),
}


class ScenarioSpec(BaseModel):
    tier: int = Field(ge=1, le=5)
    focus_skill: str | None = None
    dial_overrides: dict[str, float] = Field(default_factory=dict)
    case_id: str | None = None
    rationale: str


def _strong(session: Session, case: Case) -> bool:
    f = extract_features(session, case)
    return session.status == "agreed" and (f["surplus_share"] or 0) >= 0.5


def _weak(session: Session, case: Case) -> bool:
    f = extract_features(session, case)
    return session.status == "impasse" or (
        f["surplus_share"] is not None and f["surplus_share"] < 0.1
    )


def next_scenario(
    profile: NegotiatorProfile,
    history: list[tuple[Session, Case]],
    case_ids: list[str] | None = None,
) -> ScenarioSpec:
    rehearsals = [
        (s, c)
        for s, c in history
        if s.kind == "rehearsal" and s.status in ("agreed", "impasse") and s.counterpart_profile
    ]
    reasons = []
    if not rehearsals:
        tier = START_TIER
        reasons.append(f"First rehearsal: starting at tier {tier}.")
    else:
        last, last_case = rehearsals[-1]
        tier = last.counterpart_profile.tier
        if _weak(last, last_case):
            tier = max(1, tier - 1)
            reasons.append(f"Last rehearsal was difficult, so easing to tier {tier}.")
        elif len(rehearsals) >= 2 and all(_strong(s, c) for s, c in rehearsals[-2:]):
            tier = min(5, tier + 1)
            reasons.append(f"Two strong results in a row, so stepping up to tier {tier}.")
        else:
            reasons.append(f"Staying at tier {tier} to consolidate.")

    focus = profile.weaknesses[0] if profile.weaknesses else None
    overrides: dict[str, float] = {}
    if focus:
        overrides, why = FOCUS_DIALS[focus]
        reasons.append(f"Your weakest area so far is {focus.replace('_', ' ')}; you'll face {why}.")

    case_id = None
    if case_ids:
        played: dict[str, int] = {cid: 0 for cid in case_ids}
        for s, _ in rehearsals:
            if s.case_id in played:
                played[s.case_id] += 1
        case_id = min(case_ids, key=lambda cid: (played[cid], cid))
    return ScenarioSpec(
        tier=tier,
        focus_skill=focus,
        dial_overrides=dict(overrides),
        case_id=case_id,
        rationale=" ".join(reasons),
    )


def counterpart_for(spec: ScenarioSpec, rng: random.Random) -> CounterpartProfile:
    """A sampled profile for the spec: the tier's preset, jittered, with the focus overrides."""
    profile = sample_profile(spec.tier, rng)
    if spec.dial_overrides:
        profile = profile.model_copy(update=spec.dial_overrides)
    return profile


__all__ = ["FOCUS_DIALS", "ScenarioSpec", "counterpart_for", "next_scenario"]
