"""Critical-turn detection (T-020): the user decisions worth counterfactual analysis.

Rule-based on structured offers: the first offer, responses to the counterpart's anchor,
concessions (the user's claim drops from their previous offer), accepting, and walking away.
Capped per session because each critical turn costs K x N rollouts.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from negotrain.cases.offers import claim
from negotrain.schemas import Case, Session

CriticalKind = Literal["first_offer", "anchor_response", "concession", "accept", "walk_away"]

# Lower is more important when the cap bites.
_PRIORITY = {"accept": 0, "walk_away": 0, "first_offer": 1, "anchor_response": 2, "concession": 3}


class CriticalTurn(BaseModel):
    turn_index: int
    kind: CriticalKind
    description: str
    weight: float = 0.0  # e.g. concession size, used to rank within a kind


def critical_turns(session: Session, case: Case, cap: int = 3) -> list[CriticalTurn]:
    if session.has_custom_terms:
        return []  # Numeric counterfactuals cannot value custom proposals.
    me = session.user_role_id
    found: list[CriticalTurn] = []
    previous_claim: float | None = None
    seen_their_offer = False
    for turn in session.turns:
        if turn.speaker == "counterpart":
            seen_their_offer = seen_their_offer or turn.offer is not None
            continue
        if turn.accept:
            found.append(
                CriticalTurn(
                    turn_index=turn.index, kind="accept", description="You accepted their offer"
                )
            )
        elif turn.walk_away:
            found.append(
                CriticalTurn(turn_index=turn.index, kind="walk_away", description="You walked away")
            )
        elif turn.offer is not None:
            current = claim(case, me, turn.offer)
            if previous_claim is None:
                kind = "anchor_response" if seen_their_offer else "first_offer"
                text = (
                    "Your first offer, in response to their opening"
                    if seen_their_offer
                    else "Your opening offer"
                )
                found.append(CriticalTurn(turn_index=turn.index, kind=kind, description=text))
            elif current < previous_claim - 1e-9:
                size = previous_claim - current
                found.append(
                    CriticalTurn(
                        turn_index=turn.index,
                        kind="concession",
                        description=f"You conceded {size:.0%} of your range",
                        weight=size,
                    )
                )
            previous_claim = current
    ranked = sorted(found, key=lambda c: (_PRIORITY[c.kind], -c.weight, c.turn_index))[:cap]
    return sorted(ranked, key=lambda c: c.turn_index)
