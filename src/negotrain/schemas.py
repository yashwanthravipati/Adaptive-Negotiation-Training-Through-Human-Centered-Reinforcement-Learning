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


class SourceDocument(BaseModel):
    """Original extracted text and the roles allowed to read the whole document."""

    name: str
    text: str
    visible_to: list[str] = Field(default_factory=list)


class Case(BaseModel):
    id: str
    title: str
    public_brief: str
    issues: list[Issue]
    roles: list[RoleSheet]
    source: str = Field(default="", description="Provenance / license note")
    source_documents: list[SourceDocument] = Field(default_factory=list)

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
    """A proposal with listed option ids and/or custom wording, keyed by issue id."""

    terms: dict[str, str] = Field(default_factory=dict)
    custom_terms: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_custom_terms(self) -> Offer:
        if self.terms.keys() & self.custom_terms.keys():
            raise ValueError("an issue cannot have both a listed option and custom terms")
        if any(not text.strip() for text in self.custom_terms.values()):
            raise ValueError("custom terms cannot be blank")
        return self

    @classmethod
    def from_labels(cls, case: Case, labels: dict[str, str | None]) -> Offer:
        """Keep known labels scorable and preserve other proposals as custom wording."""
        terms, custom = {}, {}
        for issue in case.issues:
            text = (labels.get(issue.id) or "").strip()
            if not text:
                continue
            option = next((o for o in issue.options if o.label == text), None)
            if option:
                terms[issue.id] = option.id
            else:
                custom[issue.id] = text
        return cls(terms=terms, custom_terms=custom)

    def is_complete(self, case: Case) -> bool:
        return all(i.id in self.terms or i.id in self.custom_terms for i in case.issues)

    def label(self, issue: Issue) -> str | None:
        if issue.id in self.custom_terms:
            return self.custom_terms[issue.id]
        option_id = self.terms.get(issue.id)
        return next((o.label for o in issue.options if o.id == option_id), option_id)

    def describe(self, case: Case) -> str:
        return "; ".join(
            f"{issue.name}: {label}" for issue in case.issues if (label := self.label(issue))
        )


class TurnTags(BaseModel):
    """Observed message annotations, never inferred from a synthetic user's hidden state."""

    fact_ids: list[str] = Field(default_factory=list)
    raised_issues: list[str] = Field(default_factory=list)
    rapport: bool = False
    source: Literal["llm", "scripted", "human"]


class Turn(BaseModel):
    index: int
    speaker: Speaker
    text: str
    offer: Offer | None = None
    accept: bool = Field(default=False, description="Accepts the other side's latest offer")
    walk_away: bool = False
    tags: TurnTags | None = None
    hook_applied: bool | None = None
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
    concession_floor: float = Field(default=0.05, ge=0, le=1)
    focus: str | None = None
    focus_issue: str | None = None


SessionStatus = Literal["active", "agreed", "impasse", "abandoned"]
SessionKind = Literal["rehearsal", "real"]


class Session(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    participant_id: str = "anonymous"
    case_id: str
    user_role_id: str
    counterpart_role_id: str
    counterpart_profile: CounterpartProfile | None = None
    seed: int = 0
    max_user_turns: int = Field(default=20, ge=1, le=20)
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

    @property
    def has_custom_terms(self) -> bool:
        return bool(self.agreement and self.agreement.custom_terms) or any(
            t.offer and t.offer.custom_terms for t in self.turns
        )

    def add_turn(self, turn: Turn, case: Case) -> None:
        """Append a turn and update status/agreement. Accepting needs a complete offer."""
        if self.status != "active":
            raise ValueError(f"session is {self.status}")
        if turn.index != len(self.turns):
            raise ValueError(f"expected turn index {len(self.turns)}, got {turn.index}")
        if sum((turn.offer is not None, turn.accept, turn.walk_away)) > 1:
            raise ValueError("a move has at most one formal action")
        if turn.offer is not None:
            issue_ids = {i.id for i in case.issues}
            if (turn.offer.terms.keys() | turn.offer.custom_terms.keys()) - issue_ids:
                raise ValueError("offer contains an unknown issue")
            for issue_id, option_id in turn.offer.terms.items():
                if option_id not in case.issue(issue_id).option_ids():
                    raise ValueError("offer contains an unknown option")
        agreement = None
        if turn.accept and not turn.walk_away:
            other: Speaker = "counterpart" if turn.speaker == "user" else "user"
            agreement = self.latest_offer_from(other)
            if agreement is None or not agreement.is_complete(case):
                raise ValueError("can only accept a complete offer from the other side")
        self.turns.append(turn)
        if turn.walk_away:
            self.status = "impasse"
        elif turn.accept:
            self.agreement = agreement
            self.status = "agreed"
        elif turn.speaker == "counterpart" and self.user_turns >= self.max_user_turns:
            self.status = "impasse"

    @property
    def user_turns(self) -> int:
        return sum(t.speaker == "user" for t in self.turns)


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
