"""The counterpart agent: plays the other side from its hidden role sheet and profile.

The LLM writes the dialogue and picks offers; code enforces the economics (decision 0003):
valid ids, never below the reservation value, and (unless ``enforce_schedule`` is off, for
the prompt-only vs hybrid comparison in T-017) never below the current aspiration level.
If the model keeps producing invalid moves, code makes a counteroffer instead of failing.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from negotrain.cases.offers import closest_offer
from negotrain.cases.scoring import score_offer
from negotrain.counterpart.aspiration import aspiration
from negotrain.counterpart.profiles import describe
from negotrain.llm import LLM, Message
from negotrain.schemas import Case, CounterpartProfile, Offer, Session, Turn

MAX_ATTEMPTS = 3


class OfferTerm(BaseModel):
    issue_id: str
    option_id: str


class CounterpartMove(BaseModel):
    message: str = Field(description="What you say to the other side, in character")
    offer: list[OfferTerm] = Field(
        description="A formal proposal, one option per issue it covers; empty for none"
    )
    accept: bool = Field(description="True only to accept the other side's latest offer as-is")
    walk_away: bool = Field(description="True to end the negotiation without a deal")


class CounterpartAgent:
    def __init__(
        self,
        case: Case,
        role_id: str,
        profile: CounterpartProfile,
        llm: LLM,
        *,
        enforce_schedule: bool = True,
    ):
        self.case = case
        self.role = case.role(role_id)
        self.profile = profile
        self.llm = llm
        self.enforce_schedule = enforce_schedule
        self.fallbacks = 0  # moves code had to make because the model kept erring
        self.system = self._system_prompt()

    def minimum(self, session: Session) -> float:
        """Least points this side may propose or accept this turn."""
        if not self.enforce_schedule:
            return self.role.reservation_value
        return max(
            self.role.reservation_value, aspiration(self.case, self.role.id, self.profile, session)
        )

    def _system_prompt(self) -> str:
        issues = "\n".join(
            f"- {i.id} ({i.name}): " + ", ".join(f"{o.id} = {o.label}" for o in i.options)
            for i in self.case.issues
        )
        points = "\n".join(
            f"- {issue_id}: " + ", ".join(f"{opt}={pts:g}" for opt, pts in table.items())
            for issue_id, table in self.role.points.items()
        )
        return f"""You are role-playing one side of a negotiation exercise that trains a human \
negotiator. Stay in character. Do not coach the other side or comment on the exercise.

# Case (public information both sides have)
{self.case.public_brief}

# Issues and options (use these ids in formal offers)
{issues}

# Your role: {self.role.name} (confidential; the other side cannot see this)
{self.role.confidential_brief}

Your points for each option (higher is better for you):
{points}
Walking away without a deal is worth {self.role.reservation_value:g} points to you. Never \
accept or propose a complete deal worth less than that.

# How you negotiate
{describe(self.profile)}

# Each turn
Say what you would say in a real conversation (a few sentences). Optionally attach a formal \
offer naming one option per issue. Set accept to true only to accept the other side's latest \
formal offer exactly as stated."""

    def _messages(self, session: Session) -> list[Message]:
        messages: list[Message] = []
        for turn in session.turns:
            if turn.speaker == "counterpart":
                messages.append({"role": "assistant", "content": _render_own(turn)})
            else:
                messages.append({"role": "user", "content": _render_other(turn)})
        if not messages:
            messages.append(
                {"role": "user", "content": "[The negotiation begins. You speak first.]"}
            )
        elif messages[-1]["role"] == "assistant":
            messages.append({"role": "user", "content": "[The other side is waiting for you.]"})
        if self.enforce_schedule:
            # Per-turn content goes in messages so the system prompt stays cacheable.
            messages.append(
                {
                    "role": "user",
                    "content": f"[Private note, unseen by the other side: at this stage only "
                    f"propose or accept complete deals worth at least "
                    f"{self.minimum(session):.0f} points to you.]",
                }
            )
        return _merge_consecutive(messages)

    def _problems(self, move: CounterpartMove, session: Session) -> list[str]:
        problems = []
        minimum = self.minimum(session)
        terms = {}
        for term in move.offer:
            try:
                if term.option_id not in self.case.issue(term.issue_id).option_ids():
                    problems.append(f"{term.option_id!r} is not an option for {term.issue_id!r}")
            except KeyError:
                problems.append(f"{term.issue_id!r} is not an issue id")
            terms[term.issue_id] = term.option_id
        if move.accept and move.walk_away:
            problems.append("you cannot both accept and walk away")
        if move.accept:
            theirs = session.latest_offer_from("user")
            if theirs is None or not theirs.is_complete(self.case):
                problems.append("there is no complete offer from the other side to accept")
            else:
                result = score_offer(self.case, self.role.id, theirs)
                if not result.valid or result.surplus < 0:
                    problems.append("their offer is worse for you than walking away")
                elif result.points < minimum:
                    problems.append(
                        f"their offer is worth {result.points:g} to you; hold out for at "
                        f"least {minimum:.0f} at this stage"
                    )
        if terms and not problems:
            mine = Offer(terms=terms)
            if mine.is_complete(self.case):
                result = score_offer(self.case, self.role.id, mine)
                if result.surplus < 0:
                    problems.append("that offer is worse for you than walking away")
                elif result.points < minimum:
                    problems.append(
                        f"that offer is worth {result.points:g} to you; at this stage only "
                        f"offer deals worth at least {minimum:.0f}"
                    )
        return problems

    def respond(self, session: Session) -> Turn:
        """The counterpart's next turn. Does not mutate ``session``."""
        messages = self._messages(session)
        for _ in range(MAX_ATTEMPTS):
            move = self.llm.parse(self.system, messages, CounterpartMove)
            problems = self._problems(move, session)
            if not problems:
                return Turn(
                    index=len(session.turns),
                    speaker="counterpart",
                    text=move.message,
                    offer=Offer(terms={t.issue_id: t.option_id for t in move.offer})
                    if move.offer
                    else None,
                    accept=move.accept,
                    walk_away=move.walk_away,
                )
            messages = messages + [
                {"role": "assistant", "content": move.model_dump_json()},
                {
                    "role": "user",
                    "content": "[Moderator: invalid move: "
                    + "; ".join(problems)
                    + ". Reply again.]",
                },
            ]
        return self._fallback(session)

    def _fallback(self, session: Session) -> Turn:
        """A code-made counteroffer at the current minimum, near the user's latest offer."""
        self.fallbacks += 1
        offer = closest_offer(
            self.case, self.role.id, self.minimum(session), session.latest_offer_from("user")
        )
        if offer is None:
            return Turn(
                index=len(session.turns),
                speaker="counterpart",
                text="I don't see a deal here that works for us.",
                walk_away=True,
            )
        return Turn(
            index=len(session.turns),
            speaker="counterpart",
            text="Let me put something concrete on the table.",
            offer=offer,
        )


def _render_own(turn: Turn) -> str:
    move = CounterpartMove(
        message=turn.text,
        offer=[
            OfferTerm(issue_id=k, option_id=v)
            for k, v in (turn.offer.terms if turn.offer else {}).items()
        ],
        accept=turn.accept,
        walk_away=turn.walk_away,
    )
    return move.model_dump_json()


def _render_other(turn: Turn) -> str:
    parts = [turn.text]
    if turn.offer:
        parts.append(
            "[Formal offer: " + ", ".join(f"{k}={v}" for k, v in turn.offer.terms.items()) + "]"
        )
    if turn.accept:
        parts.append("[They accept your latest offer.]")
    if turn.walk_away:
        parts.append("[They walk away.]")
    return "\n".join(p for p in parts if p)


def _merge_consecutive(messages: list[Message]) -> list[Message]:
    merged: list[Message] = []
    for m in messages:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1] = {
                "role": m["role"],
                "content": merged[-1]["content"] + "\n\n" + m["content"],
            }
        else:
            merged.append(dict(m))
    return merged
