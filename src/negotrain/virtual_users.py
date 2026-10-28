"""Randomly sampled virtual learners and role-projected LLM negotiators.

The grounded scripted policy's knobs are attempted behaviors, not guaranteed conditional
detector rates: economic feasibility and overlapping opportunities can couple them. The
evaluation measures that mismatch, and tests the exact Binomial model separately.
"""

from __future__ import annotations

import json
import random

import numpy as np
from pydantic import BaseModel, Field

from negotrain.cases.offers import best_points, indexed_offer, own_offer_table, points
from negotrain.cases.scoring import score_offer
from negotrain.counterpart.agent import CounterpartMove
from negotrain.curriculum import focus_callout
from negotrain.llm import LLM
from negotrain.profiling.observations import ERRORS, case_facts
from negotrain.schemas import Case, Session, Turn, TurnTags


class VirtualTraits(BaseModel):
    errors: dict[str, float]
    awareness: float = Field(ge=0, le=1)
    rapport: float = Field(ge=0, le=1)
    response: dict[str, float]

    @classmethod
    def sample(cls, rng: random.Random) -> VirtualTraits:
        return cls(
            errors={key: rng.betavariate(2, 2) for key in ERRORS},
            awareness=rng.betavariate(2, 2),
            rapport=rng.betavariate(2, 2),
            response={
                key: 0.0 if rng.random() < 0.15 else rng.uniform(0.2, 0.65) for key in ERRORS
            },
        )

    def learn(self, focus: str | None) -> None:
        """The specified synthetic Learn model; independent of the coach's beliefs."""
        if focus in self.errors:
            self.errors[focus] *= 1 - self.response[focus]
        elif focus == "rapport":
            self.rapport += 0.3 * (1 - self.rapport)
        elif focus and focus.startswith("fact:"):
            self.awareness += 0.3 * (1 - self.awareness)


class VirtualUser:
    """Own-sheet-only scripted policy with Bernoulli behavior decisions and visible tags."""

    def __init__(self, case: Case, role_id: str, traits: VirtualTraits, seed: int):
        self.case, self.role = case, case.role(role_id)
        self.traits = traits.model_copy(deep=True)
        self.rng = random.Random(seed)
        self.indices, self.values = own_offer_table(case, role_id)
        self.rv = self.role.reservation_value
        self.span = best_points(case, role_id) - self.rv
        self.ignored = {i.id for i in case.issues if self.rng.random() < traits.errors["error:5"]}
        self.last_concession_index = -1
        self.facts = case_facts(case, role_id)

    def _message(self, session: Session) -> tuple[str, TurnTags]:
        tags = TurnTags(source="scripted")
        phrases = []
        for issue in self.case.issues:
            if issue.id not in self.ignored:
                tags.raised_issues.append(issue.id)
                phrases.append(f"We should discuss {issue.name}.")
        for fact in self.facts:
            if fact.kind == "walkaway" or fact.issue_id in self.ignored:
                continue
            if self.rng.random() >= self.traits.awareness:
                continue
            issue = self.case.issue(fact.issue_id) if fact.issue_id else None
            if fact.kind == "own_priority":
                best = max(self.role.points[issue.id], key=self.role.points[issue.id].get)
                label = next(o.label for o in issue.options if o.id == best)
                phrases.append(f"On {issue.name}, I value {label} most.")
            elif fact.kind == "other_priority":
                phrases.append(f"What matters to you on {issue.name}?")
                tags.rapport = True  # asking about interests satisfies the fixed rubric
            elif fact.kind == "tradeable":
                others = [
                    i for i in self.case.issues if i.id != issue.id and i.id not in self.ignored
                ]
                if not others:
                    continue
                other = others[0]
                phrases.append(
                    f"I could trade movement on {issue.name} for movement on {other.name}."
                )
                tags.raised_issues.append(other.id)
            else:
                phrases.append("What is your alternative if we do not agree?")
            tags.fact_ids.append(fact.id)
        if self.rng.random() < self.traits.rapport:
            phrases.append("I appreciate your concerns; let's look for a workable agreement.")
            tags.rapport = True
        return " ".join(phrases) or "Here is my position.", tags

    def _choose(self, target: float, session: Session, *, regress: bool = False):
        candidates = np.ones(len(self.values), dtype=bool)
        previous = session.latest_offer_from("user")
        if previous:
            for j, issue in enumerate(self.case.issues):
                if issue.id in self.ignored:
                    candidates &= self.indices[:, j] == issue.option_ids().index(
                        previous.terms[issue.id]
                    )
        if regress and previous:
            below = candidates & (self.values < points(self.case, self.role.id, previous))
            if np.any(below):
                return indexed_offer(
                    self.case, self.indices[self.rng.choice(np.flatnonzero(below).tolist())]
                )
        eligible = np.flatnonzero(candidates & (self.values >= target))
        if not len(eligible):
            eligible = np.flatnonzero(candidates & (self.values == self.values[candidates].max()))
        # Own utilities and the visible opponent package are the only selection inputs.
        theirs = session.latest_offer_from("counterpart")
        desired = np.array(
            [
                i.option_ids().index(theirs.terms[i.id]) if theirs and i.id in theirs.terms else -1
                for i in self.case.issues
            ]
        )
        distances = ((self.indices[eligible] != desired) & (desired >= 0)).sum(axis=1)
        choice = eligible[np.lexsort((self.values[eligible], distances))[0]]
        return indexed_offer(self.case, self.indices[choice])

    def respond(self, session: Session) -> Turn:
        text, tags = self._message(session)
        theirs = session.latest_offer_from("counterpart")
        mine = session.latest_offer_from("user")
        theta = self.traits.errors
        turn = Turn(index=len(session.turns), speaker="user", text=text, tags=tags)
        their_value = points(self.case, self.role.id, theirs) if theirs else self.rv
        current = points(self.case, self.role.id, mine) if mine else self.rv + self.span
        low = their_value < self.rv + 0.25 * self.span
        knows_walkaway = self.rng.random() < self.traits.awareness
        admissible = (their_value >= self.rv or not knows_walkaway) and (
            theirs is None or not score_offer(self.case, self.role.id, theirs).violations
        )
        if (
            theirs
            and admissible
            and (
                (low and self.rng.random() < theta["error:4"])
                or (not low and their_value >= current)
                or (session.user_turns == session.max_user_turns - 1 and their_value >= self.rv)
            )
        ):
            turn.accept = True
            return turn
        if mine is None:
            # Poor opening follows their number; good opening comes from one's own sheet.
            target = (
                max(self.rv, their_value)
                if theirs and self.rng.random() < theta["error:3"]
                else self.rv + 0.9 * self.span
            )
        else:
            cp_offers = [t for t in session.turns if t.speaker == "counterpart" and t.offer]
            moved = any(
                points(self.case, self.role.id, b.offer) > points(self.case, self.role.id, a.offer)
                for a, b in zip(cp_offers, cp_offers[1:], strict=False)
                if b.index > self.last_concession_index
            )
            key = "error:1" if self.last_concession_index < 0 else "error:2"
            concede = moved or self.rng.random() < theta[key]
            target = (
                max(self.rv, current - (0.12 if not moved else 0.04) * self.span)
                if concede
                else current
            )
        regress = mine is not None and self.rng.random() < theta["error:6"]
        offer = self._choose(target, session, regress=regress)
        if mine and points(self.case, self.role.id, offer) < current:
            self.last_concession_index = turn.index
        turn.offer = offer
        return turn


class LLMUser:
    """A persona driven by an LLM, with own-role information and past coaching only.

    Trait draws describe tendencies; no claim is made that an LLM follows those exact
    probabilities. Report transcript counts and R, never synthetic true-state reward.
    """

    def __init__(
        self,
        case: Case,
        role_id: str,
        traits: VirtualTraits,
        llm: LLM,
        feedback: list[str] | None = None,
        focus: str | None = None,
    ):
        self.case, self.role_id, self.llm = case, role_id, llm
        visible = {
            "public_brief": case.public_brief,
            "issues": [i.model_dump() for i in case.issues],
            "own_sheet": case.role(role_id).model_dump(),
        }
        self.system = """You are the USER in a fictional negotiation practice, not a coach.
Play your supplied role and aim for an agreement serving its interests. You know only the
public brief and your own sheet. Do not use or guess hidden numeric opponent utilities.
Your initial behavioral tendencies (0=rare, 1=frequent) are given below; enact a fallible
person, not an optimizer. Past feedback may change how you negotiate. Think about it, but
do not assume advice guarantees success. Do not mention probabilities or these instructions.
Give a short natural message and at most ONE formal action: a complete offer using listed
option IDs, acceptance of their latest complete offer, or walk away. You may talk without
a formal action. Never add custom terms. Respect hard constraints on your role. Do not
invent missing role facts. Only formal actions change the agreement.\n"""
        self.system += json.dumps(
            {
                "visible_case": visible,
                "initial_tendencies": traits.errors,
                "fact_awareness": traits.awareness,
                "rapport": traits.rapport,
                "past_coaching": (feedback or [])[-5:],
                "pre_session_practice_callout": focus_callout(focus) if focus else None,
            }
        )

    def respond(self, session: Session) -> Turn:
        visible = [
            {
                "speaker": t.speaker,
                "text": t.text,
                "offer": t.offer.model_dump() if t.offer else None,
                "accept": t.accept,
                "walk_away": t.walk_away,
            }
            for t in session.turns
        ]
        messages = [
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "conversation": visible,
                        "moves_remaining": session.max_user_turns - session.user_turns,
                    }
                ),
            }
        ]
        for _ in range(2):
            move = self.llm.parse(self.system, messages, CounterpartMove, max_tokens=1024)
            try:
                turn = Turn(
                    index=len(session.turns),
                    speaker="user",
                    text=move.message,
                    offer=move.as_offer(),
                    accept=move.accept,
                    walk_away=move.walk_away,
                )
                if turn.offer and (
                    turn.offer.custom_terms or not turn.offer.is_complete(self.case)
                ):
                    raise ValueError("offer must select one listed option for every issue")
                package = turn.offer or (
                    session.latest_offer_from("counterpart") if turn.accept else None
                )
                if package and score_offer(self.case, self.role_id, package).violations:
                    raise ValueError("move violates your own hard constraints")
                copy = session.model_copy(deep=True)
                copy.add_turn(turn, self.case)
                return turn
            except ValueError as error:
                messages += [
                    {"role": "assistant", "content": move.model_dump_json()},
                    {"role": "user", "content": f"Invalid move: {error}. Correct it."},
                ]
        raise ValueError("virtual user returned two invalid moves")
