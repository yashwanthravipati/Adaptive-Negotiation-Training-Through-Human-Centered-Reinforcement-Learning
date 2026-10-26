"""Shared data models.

These models are the contract between workstreams: the parser produces a ``Case``, the
counterpart and UI append ``Turn``s to a ``Session``, scoring reads ``Offer``s, and the
feedback/profiling code reads finished ``Session``s. Change them deliberately and update
the tests and docs/architecture.md when you do.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

Speaker = Literal["user", "counterpart"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- cases


class Option(BaseModel):
    id: str
    label: str


class Issue(BaseModel):
    id: str
    name: str
    description: str = ""
    options: list[Option]

    def option_ids(self) -> list[str]:
        return [o.id for o in self.options]


class Constraint(BaseModel):
    """A rule a role must respect. ``disallowed`` makes it machine-checkable."""

    description: str
    hard: bool = True
    disallowed: dict[str, list[str]] = Field(
        default_factory=dict, description="issue_id -> option_ids this role cannot accept"
    )


class RoleSheet(BaseModel):
    """One side's confidential instructions. Never shown to the other side."""

    id: str
    name: str
    confidential_brief: str
    points: dict[str, dict[str, float]] = Field(description="issue_id -> option_id -> points")
    reservation_value: float = Field(description="Points from walking away (BATNA)")
    constraints: list[Constraint] = Field(default_factory=list)
    inferred: bool = Field(
        default=False,
        description="Estimated by the parser because the real sheet was not provided",
    )


class Case(BaseModel):
    id: str
    title: str
    public_brief: str
    issues: list[Issue]
    roles: list[RoleSheet]
    source: str = Field(default="", description="Provenance / license note")

    @model_validator(mode="after")
    def _check_points_cover_issues(self) -> Case:
        for role in self.roles:
            for issue in self.issues:
                table = role.points.get(issue.id)
                if table is None:
                    raise ValueError(f"role {role.id!r} has no points for issue {issue.id!r}")
                missing = set(issue.option_ids()) - set(table)
                if missing:
                    raise ValueError(
                        f"role {role.id!r} issue {issue.id!r} missing options {sorted(missing)}"
                    )
        return self

    def role(self, role_id: str) -> RoleSheet:
        for r in self.roles:
            if r.id == role_id:
                return r
        raise KeyError(f"unknown role {role_id!r}; have {[r.id for r in self.roles]}")

    def other_role(self, role_id: str) -> RoleSheet:
        others = [r for r in self.roles if r.id != role_id]
        if len(others) != 1:
            raise ValueError("other_role() only applies to two-party cases")
        return others[0]

    def issue(self, issue_id: str) -> Issue:
        for i in self.issues:
            if i.id == issue_id:
                return i
        raise KeyError(f"unknown issue {issue_id!r}")


# -------------------------------------------------------------------- negotiation


class Offer(BaseModel):
    """A proposal: issue_id -> option_id. May be partial (not every issue settled)."""

    terms: dict[str, str]

    def is_complete(self, case: Case) -> bool:
        return all(i.id in self.terms for i in case.issues)

    def describe(self, case: Case) -> str:
        parts = []
        for issue in case.issues:
            if issue.id in self.terms:
                label = next(
                    (o.label for o in issue.options if o.id == self.terms[issue.id]),
                    self.terms[issue.id],
                )
                parts.append(f"{issue.name}: {label}")
        return "; ".join(parts)


class Turn(BaseModel):
    index: int
    speaker: Speaker
    text: str
    offer: Offer | None = None
    accept: bool = Field(default=False, description="Accepts the other side's latest offer")
    walk_away: bool = False
    created_at: datetime = Field(default_factory=_now)


class CounterpartProfile(BaseModel):
    """Behavioral knobs for the counterpart. All dials are in [0, 1]."""

    name: str
    tier: int = Field(ge=1, le=5, description="Curriculum difficulty, 1 = easiest")
    cooperativeness: float = Field(ge=0, le=1)
    aggression: float = Field(ge=0, le=1)
    anchoring: float = Field(ge=0, le=1, description="How extreme the opening offer is")
    concession_rate: float = Field(ge=0, le=1, description="How readily it gives ground")
    disclosure: float = Field(ge=0, le=1, description="How much private info it shares")
    bluffing: float = Field(ge=0, le=1, description="Willingness to misstate its position")


SessionStatus = Literal["active", "agreed", "impasse", "abandoned"]
SessionKind = Literal["rehearsal", "real"]


class Session(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    participant_id: str = "anonymous"
    case_id: str
    user_role_id: str
    counterpart_role_id: str
    counterpart_profile: CounterpartProfile | None = None
    turns: list[Turn] = Field(default_factory=list)
    status: SessionStatus = "active"
    agreement: Offer | None = None
    created_at: datetime = Field(default_factory=_now)
    kind: SessionKind = Field(
        default="rehearsal",
        description="rehearsal = vs the counterpart agent; real = a logged human negotiation",
    )
    notes: str = ""
    observed_counterpart: dict[str, float] = Field(
        default_factory=dict,
        description="Real sessions: participant's ratings of the other side on the dials (0-1)",
    )

    def latest_offer_from(self, speaker: Speaker) -> Offer | None:
        for turn in reversed(self.turns):
            if turn.speaker == speaker and turn.offer is not None:
                return turn.offer
        return None

    def add_turn(self, turn: Turn, case: Case) -> None:
        """Append a turn and update status/agreement. Accepting needs a complete offer."""
        if self.status != "active":
            raise ValueError(f"session is {self.status}")
        if turn.index != len(self.turns):
            raise ValueError(f"expected turn index {len(self.turns)}, got {turn.index}")
        self.turns.append(turn)
        if turn.walk_away:
            self.status = "impasse"
        elif turn.accept:
            other: Speaker = "counterpart" if turn.speaker == "user" else "user"
            offer = self.latest_offer_from(other)
            if offer is None or not offer.is_complete(case):
                raise ValueError("can only accept a complete offer from the other side")
            self.agreement = offer
            self.status = "agreed"


# -------------------------------------------------------------------- participants


class Participant(BaseModel):
    """Onboarding record. Pseudonymous: the id is the only identifier we store."""

    id: str
    experience: Literal["none", "some", "lots"] = "some"
    goals: str = ""
    self_ratings: dict[str, int] = Field(
        default_factory=dict, description="skill -> 1-5 self-assessment at onboarding"
    )
    consented: bool = False
    created_at: datetime = Field(default_factory=_now)
