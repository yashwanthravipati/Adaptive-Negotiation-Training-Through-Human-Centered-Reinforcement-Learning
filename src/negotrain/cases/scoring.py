"""Deterministic scoring of offers and agreements.

Assumes additive point schedules (each issue scored independently), which is how most
classroom cases are written. If a case has cross-issue dependencies, extend this module
rather than special-casing callers.
"""

from __future__ import annotations

from pydantic import BaseModel

from negotrain.schemas import Case, Offer


class ScoreResult(BaseModel):
    role_id: str
    points: float
    reservation_value: float
    surplus: float  # points - reservation_value; negative means worse than walking away
    complete: bool
    violations: list[str]

    @property
    def valid(self) -> bool:
        return self.complete and not self.violations


def score_offer(case: Case, role_id: str, offer: Offer) -> ScoreResult:
    """Points a role gets from ``offer``. Unsettled issues contribute 0."""
    role = case.role(role_id)
    points = 0.0
    violations: list[str] = []
    for issue_id, option_id in offer.terms.items():
        table = role.points.get(issue_id)
        if table is None or option_id not in table:
            violations.append(f"unknown term {issue_id}={option_id}")
            continue
        points += table[option_id]
    for c in role.constraints:
        if not c.hard:
            continue
        for issue_id, banned in c.disallowed.items():
            if offer.terms.get(issue_id) in banned:
                violations.append(c.description)
    return ScoreResult(
        role_id=role_id,
        points=points,
        reservation_value=role.reservation_value,
        surplus=points - role.reservation_value,
        complete=offer.is_complete(case),
        violations=violations,
    )


def joint_points(case: Case, offer: Offer) -> float:
    return sum(score_offer(case, r.id, offer).points for r in case.roles)


def max_joint_offer(case: Case) -> Offer:
    """The agreement maximizing total points across roles (ignores constraints).

    With additive schedules this is separable: pick the best option per issue.
    """
    terms = {}
    for issue in case.issues:
        terms[issue.id] = max(
            issue.option_ids(),
            key=lambda opt, iid=issue.id: sum(r.points[iid][opt] for r in case.roles),
        )
    return Offer(terms=terms)


def efficiency(case: Case, offer: Offer) -> float:
    """Joint points of ``offer`` as a fraction of the best achievable joint points."""
    best = joint_points(case, max_joint_offer(case))
    return joint_points(case, offer) / best if best else 0.0
