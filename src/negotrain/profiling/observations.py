"""The six opportunity/occurrence detectors in new-spec.md, section 2.

Message-dependent observations require explicit tags. Missing tags are missing data,
not evidence of poor awareness or rapport. Numeric detectors never call an LLM.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from negotrain.cases.offers import feasible_best_points, points, surplus_share
from negotrain.schemas import Case, Offer, Session

ERRORS = {
    "error:1": "Conceding first",
    "error:2": "Unreciprocated concession",
    "error:3": "Anchoring on their number",
    "error:4": "Accepting low",
    "error:5": "Ignoring an issue",
    "error:6": "Dominated offer",
}


class Fact(BaseModel):
    id: str
    kind: str
    description: str
    issue_id: str | None = None


def case_facts(case: Case, role_id: str) -> list[Fact]:
    """A case-specific rubric built from public issues and the user's own sheet only.

    Counterpart priorities and alternatives are hypotheses to investigate, not private
    values exposed by the coach. Stable ids keep beliefs separate across cases and roles.
    """
    prefix = f"fact:{case.id}:{role_id}:"
    facts = [Fact(id=prefix + "walkaway", kind="walkaway", description="Act on your walk-away")]
    for issue in case.issues:
        for kind, description in (
            ("own_priority", f"Use your priority on {issue.name}"),
            ("other_priority", f"Ask about or use their stated priority on {issue.name}"),
            ("tradeable", f"Explore a trade involving {issue.name}"),
        ):
            facts.append(
                Fact(
                    id=prefix + kind + ":" + issue.id,
                    kind=kind,
                    issue_id=issue.id,
                    description=description,
                )
            )
    facts.append(
        Fact(
            id=prefix + "alternative",
            kind="alternative",
            description="Ask about or use their stated alternative to agreement",
        )
    )
    return facts


class Count(BaseModel):
    opportunities: int = Field(default=0, ge=0)
    occurrences: int = Field(default=0, ge=0)
    turns: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_counts(self) -> Count:
        if self.occurrences > self.opportunities:
            raise ValueError("occurrences exceed opportunities")
        return self

    def observe(self, occurred: bool, turn: int) -> None:
        self.opportunities += 1
        if occurred:
            self.occurrences += 1
            self.turns.append(turn)


class Observations(BaseModel):
    counts: dict[str, Count]
    score: float | None
    untagged_user_turns: int = 0
    excluded_numeric_turns: int = 0


def observe(session: Session, case: Case) -> Observations:
    facts = case_facts(case, session.user_role_id)
    counts = {key: Count() for key in [*ERRORS, *(f.id for f in facts), "rapport"]}
    me, them = session.user_role_id, session.counterpart_role_id
    rv = case.role(me).reservation_value
    top = feasible_best_points(case, me)
    previous: dict[str, Offer] = {}
    table: list[Offer] = []
    cp_concessions = 0
    cp_at_last_concession = 0
    user_concessions = 0
    seen_user_offer = False
    issue_options: dict[str, set[str]] = {i.id: set() for i in case.issues}
    raised: set[str] = set()
    untagged = excluded = 0
    user_turns = [t for t in session.turns if t.speaker == "user"]
    for turn in session.turns:
        offer = turn.offer
        numeric = offer is not None and offer.is_complete(case) and not offer.custom_terms
        if turn.speaker == "counterpart":
            old = previous.get("counterpart")
            if numeric:
                if old and points(case, them, offer) < points(case, them, old):
                    cp_concessions += 1
                previous["counterpart"] = offer
                table.append(offer)
            continue
        if turn.tags is None:
            untagged += 1
        else:
            raised.update(turn.tags.raised_issues)
            counts["rapport"].observe(turn.tags.rapport, turn.index)
            for fact in facts:
                if fact.kind != "walkaway":
                    counts[fact.id].observe(fact.id in turn.tags.fact_ids, turn.index)
        if offer is not None and not numeric:
            excluded += 1
        accepted = session.latest_offer_from("counterpart") if turn.accept else None
        # Acceptance must use the standing offer in this prefix, never a future offer.
        if turn.accept:
            accepted = next(
                (
                    t.offer
                    for t in reversed(session.turns[: turn.index])
                    if t.speaker == "counterpart" and t.offer is not None
                ),
                None,
            )
        own_package = offer if numeric else accepted
        if own_package and own_package.is_complete(case) and not own_package.custom_terms:
            counts[facts[0].id].observe(points(case, me, own_package) >= rv, turn.index)
        if turn.accept and accepted and not accepted.custom_terms:
            counts["error:4"].observe(
                surplus_share(case, me, points(case, me, accepted)) < 0.25, turn.index
            )
        if not numeric:
            continue
        own = points(case, me, offer)
        old = previous.get("user")
        if old and own < points(case, me, old):
            counts["error:1"].observe(cp_concessions == 0, turn.index)
            if user_concessions:
                counts["error:2"].observe(cp_concessions == cp_at_last_concession, turn.index)
            user_concessions += 1
            cp_at_last_concession = cp_concessions
        if not seen_user_offer and "counterpart" in previous:
            midpoint = 0.5 * (points(case, me, previous["counterpart"]) + top)
            counts["error:3"].observe(own < midpoint, turn.index)
        cp = points(case, them, offer)
        dominated = any(
            points(case, me, d) >= own
            and points(case, them, d) >= cp
            and (points(case, me, d) > own or points(case, them, d) > cp)
            for d in table
        )
        counts["error:6"].observe(dominated, turn.index)
        for issue, option in offer.terms.items():
            issue_options[issue].add(option)
        seen_user_offer = True
        previous["user"] = offer
        table.append(offer)
    if session.status in ("agreed", "impasse") and user_turns:
        for issue in case.issues:
            if len(set(case.role(me).points[issue.id].values())) <= 1:
                continue
            used = len(issue_options[issue.id]) > 1 or issue.id in raised
            # With incomplete tagging, absence of a mention is not observable.
            if used or untagged == 0:
                counts["error:5"].observe(not used, user_turns[-1].index)
    score = 0.0
    if session.status == "agreed" and session.agreement:
        score = (
            None
            if session.agreement.custom_terms
            else surplus_share(case, me, points(case, me, session.agreement))
        )
    return Observations(
        counts=counts, score=score, untagged_user_turns=untagged, excluded_numeric_turns=excluded
    )


def failure_turns(session: Session, observation: Observations, key: str) -> set[int]:
    """Observed errors or eligible turns lacking a positive fact/rapport label."""
    count = observation.counts[key]
    if key in ERRORS:
        return set(count.turns)
    eligible = {t.index for t in session.turns if t.speaker == "user" and t.tags is not None}
    if key.endswith(":walkaway"):
        eligible = {t.index for t in session.turns if t.speaker == "user" and (t.offer or t.accept)}
    return eligible - set(count.turns)
