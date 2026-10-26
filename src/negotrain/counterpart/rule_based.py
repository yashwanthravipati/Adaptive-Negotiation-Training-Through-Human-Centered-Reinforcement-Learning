"""A counterpart driven only by the concession schedule, with templated dialogue.

Used in offline mode (no API key), as a fast and free opponent for counterfactual rollouts,
and as a baseline in simulation experiments. Its offers follow the same aspiration schedule
as the hybrid LLM counterpart, so its economics are comparable; only the talk is canned.
"""

from __future__ import annotations

from typing import Protocol

from negotrain.cases.offers import closest_offer
from negotrain.cases.scoring import score_offer
from negotrain.counterpart.aspiration import aspiration
from negotrain.schemas import Case, CounterpartProfile, Session, Turn


class Counterpart(Protocol):
    def respond(self, session: Session) -> Turn: ...


_OPEN = {
    "warm": "Thanks for making the time. Here's where we'd like to start.",
    "civil": "Let's get into it. Here is our proposal.",
    "forceful": "I'll be direct: this is what we need to see.",
}
_COUNTER = {
    "warm": "I hear you. Let me see what I can do. How about this?",
    "civil": "That doesn't quite work for us, but here's a counterproposal.",
    "forceful": "That's not realistic. This is the best I can do right now.",
}
_HOLD = {
    "warm": "I'd love to move further, but I really can't go beyond this yet.",
    "civil": "We're not able to move on this yet; our proposal stands.",
    "forceful": "My offer stands. You'll need to give me something to work with.",
}
_ACCEPT = "That works for us. We have a deal."


def _tone(profile: CounterpartProfile) -> str:
    return (
        "warm"
        if profile.aggression < 1 / 3
        else "civil"
        if profile.aggression < 2 / 3
        else "forceful"
    )


class RuleBasedCounterpart:
    def __init__(self, case: Case, role_id: str, profile: CounterpartProfile):
        self.case = case
        self.role = case.role(role_id)
        self.profile = profile

    def minimum(self, session: Session) -> float:
        return max(
            self.role.reservation_value, aspiration(self.case, self.role.id, self.profile, session)
        )

    def _priority_hint(self) -> str:
        """What a disclosing counterpart says when asked: its most important issue."""
        spread = {
            issue_id: max(table.values()) - min(table.values())
            for issue_id, table in self.role.points.items()
        }
        top = max(spread, key=spread.get)
        return f" For us, {self.case.issue(top).name.lower()} matters most."

    def respond(self, session: Session) -> Turn:
        index = len(session.turns)
        minimum = self.minimum(session)
        theirs = session.latest_offer_from("user")
        last = session.turns[-1] if session.turns else None
        if theirs is not None and theirs.is_complete(self.case) and last and last.offer:
            result = score_offer(self.case, self.role.id, theirs)
            if result.valid and result.points is not None and result.points >= minimum:
                return Turn(index=index, speaker="counterpart", text=_ACCEPT, accept=True)

        tone = _tone(self.profile)
        offer = closest_offer(self.case, self.role.id, minimum, theirs)
        if offer is None:
            return Turn(
                index=index,
                speaker="counterpart",
                text="I don't see a deal here that works for us.",
                walk_away=True,
            )
        previous = session.latest_offer_from("counterpart")
        if previous is None:
            text = _OPEN[tone]
        elif previous == offer:
            text = _HOLD[tone]
        else:
            text = _COUNTER[tone]
        if theirs is not None and theirs.custom_terms:
            text = (
                "I can only evaluate the listed options in offline mode. "
                "Here is a proposal using those options."
            )
        if last and last.speaker == "user" and "?" in last.text:
            if self.profile.disclosure >= 0.5:
                text += self._priority_hint()
            else:
                text += " I'd rather focus on the terms themselves."
        return Turn(index=index, speaker="counterpart", text=text, offer=offer)
