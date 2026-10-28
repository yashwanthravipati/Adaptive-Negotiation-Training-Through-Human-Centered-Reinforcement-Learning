"""A counterpart driven only by the concession schedule, with templated dialogue.

Used in offline mode (no API key), as a fast and free opponent for counterfactual rollouts,
and as a baseline in simulation experiments. Its offers follow the same aspiration schedule
as the hybrid LLM counterpart, so its economics are comparable; only the talk is canned.
"""

from __future__ import annotations

from typing import Protocol

from negotrain.cases.offers import closest_offer, feasible_best_points, listed_packages
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
        if self.profile.focus == "error:5":
            spread.pop(self.ignored_issue(), None)
        if not spread:
            return " What matters most to you?"
        top = max(spread, key=spread.get)
        return f" For us, {self.case.issue(top).name.lower()} matters most."

    def ignored_issue(self) -> str:
        return (
            self.profile.focus_issue
            or min(
                self.case.issues,
                key=lambda i: (
                    max(self.role.points[i.id].values()) - min(self.role.points[i.id].values())
                ),
            ).id
        )

    def _hook_offer(self, session: Session, minimum: float):
        """Hooks shape only available, schedule-feasible formal packages."""
        focus = self.profile.focus
        n = sum(t.speaker == "counterpart" for t in session.turns)
        previous = session.latest_offer_from("counterpart")
        if focus == "error:4" and n in (1, 2) and previous:
            return previous
        if not (
            (focus == "error:4" and n == 0) or focus == "error:5" or (focus == "error:6" and n == 1)
        ):
            return None
        eligible = [
            (d, own, other)
            for d, own, other in listed_packages(self.case, self.role.id)
            if own >= minimum
        ]
        if focus == "error:4":
            me = session.user_role_id
            rv = self.case.role(me).reservation_value
            upper = rv + 0.25 * (feasible_best_points(self.case, me) - rv)
            eligible = [(d, own, u) for d, own, u in eligible if rv <= u < upper]
        elif focus == "error:5":
            issue = self.ignored_issue()
            worst = min(self.role.points[issue], key=self.role.points[issue].get)
            eligible = [(d, own, u) for d, own, u in eligible if d.terms[issue] == worst]
        else:
            eligible = [(d, own, u) for d, own, u in eligible if d != previous]
        return (
            min(eligible, key=lambda item: (item[1], tuple(item[0].terms.values())))[0]
            if eligible
            else None
        )

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
        hook_offer = self._hook_offer(session, minimum)
        offer = hook_offer or closest_offer(self.case, self.role.id, minimum, theirs)
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
            if self.profile.disclosure >= 0.5 or (
                self.profile.focus and self.profile.focus.startswith("fact:")
            ):
                text += self._priority_hint()
            else:
                text += " I'd rather focus on the terms themselves."
        n = sum(t.speaker == "counterpart" for t in session.turns)
        active_hook = (
            self.profile.focus == "error:5"
            or (self.profile.focus == "error:4" and n <= 2)
            or (self.profile.focus == "error:6" and n == 1)
        )
        return Turn(
            index=index,
            speaker="counterpart",
            text=text,
            offer=offer,
            hook_applied=(hook_offer is not None) if active_hook else None,
        )
