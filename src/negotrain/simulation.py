"""Simulated negotiators and an episode runner (agent vs agent).

Shared by counterfactual rollouts (feedback/rollouts.py) and the simulation experiments
(T-016, T-017, T-026). ``ScriptedUser`` is a transparent policy with knobs that mirror the
behaviors we profile (opening claim, concession step, questions), so traits can be injected
and recovered.
"""

from __future__ import annotations

from negotrain.cases.offers import best_points, closest_offer, points, surplus_share
from negotrain.cases.scoring import score_offer
from negotrain.counterpart.rule_based import Counterpart
from negotrain.schemas import Case, Session, Turn


class ScriptedUser:
    """Plays the user's role: opens at ``open_share`` of the way from walk-away to best,
    concedes ``step`` of that span per turn, and accepts any complete offer at or above its
    current aspiration. Never uses the other side's hidden points."""

    def __init__(
        self,
        case: Case,
        role_id: str,
        *,
        open_share: float = 0.9,
        step: float = 0.08,
        start_points: float | None = None,
        asks_questions: bool = False,
    ):
        self.case = case
        self.role = case.role(role_id)
        rv = self.role.reservation_value
        self.span = max(0.0, best_points(case, role_id) - rv)
        self.start = start_points if start_points is not None else rv + open_share * self.span
        self.step = step
        self.asks_questions = asks_questions
        self.turns_taken = 0

    def aspiration(self) -> float:
        rv = self.role.reservation_value
        return max(rv, self.start - self.step * self.span * self.turns_taken)

    def respond(self, session: Session) -> Turn:
        index = len(session.turns)
        level = self.aspiration()
        self.turns_taken += 1
        theirs = session.latest_offer_from("counterpart")
        if theirs is not None and theirs.is_complete(self.case):
            result = score_offer(self.case, self.role.id, theirs)
            if result.valid and result.points is not None and result.points >= level:
                return Turn(index=index, speaker="user", text="Agreed.", accept=True)
        offer = closest_offer(self.case, self.role.id, level, theirs)
        if offer is None:
            return Turn(index=index, speaker="user", text="I'll walk away.", walk_away=True)
        text = "Here is my proposal."
        if self.asks_questions:
            text += " What matters most to you here?"
        return Turn(index=index, speaker="user", text=text, offer=offer)


def run_episode(
    case: Case,
    session: Session,
    counterpart: Counterpart,
    user: ScriptedUser,
    *,
    max_turns: int = 12,
) -> Session:
    """Continue ``session`` (mutated in place) alternating sides until agreement, impasse,
    or ``max_turns`` more turns. Whoever did not speak last moves next."""
    for _ in range(max_turns):
        if session.status != "active":
            break
        last = session.turns[-1].speaker if session.turns else "user"
        mover = user if last == "counterpart" else counterpart
        session.add_turn(mover.respond(session), case)
    return session


def episode_value(case: Case, session: Session) -> float:
    """Realized points only: an unaccepted standing offer has no terminal value."""
    role = case.role(session.user_role_id)
    if session.status == "agreed" and session.agreement is not None:
        return points(case, role.id, session.agreement)
    return role.reservation_value


def episode_score(case: Case, session: Session) -> float | None:
    """The only rehearsal reward, R. Custom agreements are unscored; no deal is zero."""
    if session.status != "agreed" or session.agreement is None:
        return 0.0
    if session.agreement.custom_terms:
        return None
    return surplus_share(case, session.user_role_id, episode_value(case, session))
