"""Deterministic schedule: independent opening, per-turn concession, and floor."""

from __future__ import annotations

import random

from negotrain.cases.offers import best_points, points
from negotrain.counterpart.profiles import focused_profile
from negotrain.schemas import Case, CounterpartProfile, Session


def user_concessions(case: Case, session: Session) -> int:
    count, previous = 0, None
    for turn in session.turns:
        if turn.speaker != "user" or turn.offer is None:
            continue
        if turn.offer.custom_terms or not turn.offer.is_complete(case):
            previous = None
            continue
        current = points(case, session.user_role_id, turn.offer)
        if previous is not None and current < previous:
            count += 1
        previous = current
    return count


def aspiration_at(
    case: Case,
    role_id: str,
    profile: CounterpartProfile,
    own_turns: int,
    reciprocity: int = 0,
    *,
    deadline: int = 20,
    bonus_steps: int = 0,
) -> float:
    """All dials are fractions of P^C_max-W^C. Deadline pressure accelerates release.

    `reciprocity` is retained for callers, but has no implicit schedule effect: the
    specification gives each focus an explicit hook instead of a hidden global bonus.
    """
    rv = case.role(role_id).reservation_value
    span = max(0.0, best_points(case, role_id) - rv)
    opening, floor, rate = profile.anchoring, profile.concession_floor, profile.concession_rate
    clock = max(0, own_turns)
    pressure = (opening - floor) * min(1.0, clock / max(1, deadline - 1)) ** 4
    fraction = max(floor, opening - rate * (clock + bonus_steps) - pressure)
    return rv + max(0.0, fraction) * span


def aspiration(case: Case, role_id: str, profile: CounterpartProfile, session: Session) -> float:
    profile = focused_profile(profile)
    own_turns = sum(t.speaker == "counterpart" for t in session.turns)
    concessions = user_concessions(case, session)
    clock = own_turns
    if profile.focus == "error:1" and concessions == 0 and own_turns < 6:
        clock = 0
    bonus = 0
    if profile.focus == "rapport":
        # Each tagged user move buys exactly one extra rate step, on its next reply.
        bonus = sum(
            t.speaker == "user" and t.tags is not None and t.tags.rapport for t in session.turns
        )
    level = aspiration_at(
        case, role_id, profile, clock, deadline=session.max_user_turns, bonus_steps=bonus
    )
    previous = session.latest_offer_from("counterpart")
    if previous and not previous.custom_terms and previous.is_complete(case):
        previous_points = points(case, role_id, previous)
        if profile.focus == "error:1" and concessions == 0 and own_turns < 6:
            level = max(level, previous_points)
        if profile.focus == "error:4" and own_turns in (1, 2):
            level = max(level, previous_points)
        if profile.focus == "error:2" and concessions >= 2:
            # Only react to a new concession, not repeatedly to the historical count.
            prefix = session.model_copy(update={"turns": session.turns[:-1]})
            new_concession = concessions > user_concessions(case, prefix)
            if new_concession and random.Random(session.seed + 7919 * own_turns).random() < 0.5:
                level = max(level, previous_points)
    return level
