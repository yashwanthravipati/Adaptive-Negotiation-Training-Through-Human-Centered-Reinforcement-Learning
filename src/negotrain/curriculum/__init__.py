"""Tailored scenario selection (T-027): choose the next counterpart tier and dial emphasis
that target a negotiator's weakest skill while raising difficulty gradually.

Rule-based on purpose (PLAN.md §3): step the tier up after two strong rehearsals in a row,
down after an impasse or a weak result, and bend the counterpart's dials toward the
situation that exercises the weakest skill.
"""

from __future__ import annotations

import random

from pydantic import BaseModel, Field

from negotrain.counterpart.profiles import FOCUS_DIALS, sample_profile
from negotrain.profiling import NegotiatorProfile, extract_features
from negotrain.profiling.belief import choose_focus
from negotrain.schemas import Case, CounterpartProfile, Session

START_TIER = 2

FOCUS_PREP = {
    "error:1": "Before conceding, look for movement from the other side.",
    "error:2": "Track what you received for your last concession before making another.",
    "error:3": "Choose an opening from your priorities before seeing their opening number.",
    "error:4": "Compare any agreement with your walk-away and your achievable target.",
    "error:5": "Raise every issue you value and explore different options on it.",
    "error:6": "Compare new packages with previous ones; avoid making both sides worse off.",
    "rapport": "Acknowledge their concerns and ask constructive questions about interests.",
}


def focus_callout(focus: str | None) -> str:
    if focus is None:
        return "Use your preparation to negotiate without a targeted practice focus."
    return FOCUS_PREP.get(
        focus, "Identify the relevant case fact and plan how to use or ask about it."
    )


class ScenarioSpec(BaseModel):
    tier: int = Field(ge=1, le=5)
    focus: str | None = None
    focus_issue: str | None = None
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

    # Fact beliefs are case-specific; do not practice a fact from another upload.
    candidates = [
        key
        for key in profile.belief.components
        if not key.startswith("fact:")
        or not case_ids
        or any(key.startswith(f"fact:{cid}:") for cid in case_ids)
    ]
    focus = choose_focus(profile.belief, profile.costs, candidates=candidates)
    overrides: dict[str, float] = {}
    if focus:
        overrides, why = FOCUS_DIALS.get(focus, ({}, "reveal the relevant fact when asked"))
        reasons.append(f"Practice {profile.labels[focus].lower()}; the counterpart will {why}.")
    # Tier 5 requires two strong tier-4 rehearsals, not just any two successes.
    if tier == 5 and not (
        len(rehearsals) >= 2
        and all(s.counterpart_profile.tier >= 4 and _strong(s, c) for s, c in rehearsals[-2:])
    ):
        tier = 4

    case_id = None
    if case_ids:
        played: dict[str, int] = {cid: 0 for cid in case_ids}
        for s, _ in rehearsals:
            if s.case_id in played:
                played[s.case_id] += 1
        case_id = min(case_ids, key=lambda cid: (played[cid], cid))
    return ScenarioSpec(
        tier=tier,
        focus=focus,
        dial_overrides=dict(overrides),
        case_id=case_id,
        rationale=" ".join(reasons),
    )


def counterpart_for(spec: ScenarioSpec, rng: random.Random) -> CounterpartProfile:
    """A sampled profile for the spec: the tier's preset, jittered, with the focus overrides."""
    profile = sample_profile(spec.tier, rng, jitter=0.0)
    profile = profile.model_copy(update={"focus": spec.focus, "focus_issue": spec.focus_issue})
    if spec.dial_overrides:
        profile = profile.model_copy(update=spec.dial_overrides)
    return profile


__all__ = ["FOCUS_DIALS", "ScenarioSpec", "counterpart_for", "next_scenario"]
