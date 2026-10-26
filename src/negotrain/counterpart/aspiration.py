"""Code-enforced concession schedule (T-011, decision 0003).

LLM counterparts concede too easily, which would teach users bad habits. So the counterpart
may only propose or accept complete deals worth at least ``aspiration(...)`` points to
itself. The level starts high (set by ``anchoring``), decays toward a floor just above the
reservation value at a rate set by ``concession_rate``, and moves faster when the user has
made concessions (reciprocity, weighted by ``cooperativeness``).
"""

from __future__ import annotations

from negotrain.cases.offers import best_points, claim
from negotrain.schemas import Case, CounterpartProfile, Session


def user_concessions(case: Case, session: Session) -> int:
    """How many times the user's offers got worse for the user than their previous offer."""
    count, previous = 0, None
    for turn in session.turns:
        if turn.speaker != "user" or turn.offer is None:
            continue
        current = claim(case, session.user_role_id, turn.offer)
        if previous is not None and current < previous - 1e-9:
            count += 1
        previous = current
    return count


def aspiration_at(
    case: Case, role_id: str, profile: CounterpartProfile, own_turns: int, reciprocity: int = 0
) -> float:
    rv = case.role(role_id).reservation_value
    best = best_points(case, role_id)
    if best <= rv:
        return rv
    span = best - rv
    start = rv + (0.55 + 0.45 * profile.anchoring) * span
    floor = rv + 0.1 * (1 - profile.concession_rate) * span
    decay = 0.04 + 0.26 * profile.concession_rate
    clock = own_turns + profile.cooperativeness * reciprocity
    return floor + (start - floor) * (1 - decay) ** clock


def aspiration(case: Case, role_id: str, profile: CounterpartProfile, session: Session) -> float:
    """Minimum points the counterpart may propose or accept on its next turn."""
    own_turns = sum(1 for t in session.turns if t.speaker == "counterpart")
    return aspiration_at(case, role_id, profile, own_turns, user_concessions(case, session))
