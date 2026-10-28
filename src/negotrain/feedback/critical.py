"""Formal user actions and detector firings, with focus-first analysis ordering."""

from __future__ import annotations

from pydantic import BaseModel, Field

from negotrain.cases.offers import points
from negotrain.profiling.observations import ERRORS, observe
from negotrain.schemas import Case, Session


class CriticalTurn(BaseModel):
    turn_index: int
    kind: str
    description: str
    weight: float = 0.0
    errors: list[str] = Field(default_factory=list)


def critical_turns(session: Session, case: Case, cap: int | None = None) -> list[CriticalTurn]:
    if session.has_custom_terms:
        return []
    observation = observe(session, case)
    found = []
    previous = None
    seen_counterpart = False
    for turn in session.turns:
        if turn.speaker == "counterpart":
            seen_counterpart |= turn.offer is not None
            continue
        errors = [key for key in ERRORS if turn.index in observation.counts[key].turns]
        if not (turn.offer or turn.accept or turn.walk_away or errors):
            continue
        if turn.accept:
            kind, description = "accept", "You accepted their offer"
        elif turn.walk_away:
            kind, description = "walk_away", "You walked away"
        elif previous is None and turn.offer:
            kind = "anchor_response" if seen_counterpart else "first_offer"
            description = "Your first offer"
        elif (
            turn.offer
            and previous
            and turn.offer.is_complete(case)
            and previous.is_complete(case)
            and points(case, session.user_role_id, turn.offer)
            < points(case, session.user_role_id, previous)
        ):
            kind, description = "concession", "Your concession"
        else:
            kind, description = "offer", "Your proposal"
        if turn.offer:
            previous = turn.offer
        if errors:
            description += ": " + ", ".join(ERRORS[k].lower() for k in errors)
        found.append(
            CriticalTurn(turn_index=turn.index, kind=kind, description=description, errors=errors)
        )
    focus = session.counterpart_profile.focus if session.counterpart_profile else None
    found.sort(
        key=lambda c: (
            focus not in c.errors,
            not c.errors,
            c.kind not in ("accept", "walk_away"),
            c.turn_index,
        )
    )
    return found if cap is None else found[:cap]
