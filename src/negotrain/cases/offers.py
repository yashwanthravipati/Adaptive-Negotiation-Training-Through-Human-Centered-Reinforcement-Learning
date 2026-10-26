"""Searching the space of complete offers.

The counterpart's concession schedule, the rule-based counterpart, the simulated user in
rollouts, and the counterfactual alternatives all need the same primitive: "find a complete
offer worth at least X points to role R that is as close as possible to some other offer".
Small cases are enumerated exactly; large ones fall back to a greedy search.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterator

from negotrain.cases.scoring import score_offer
from negotrain.schemas import Case, Offer

MAX_ENUMERATE = 50_000


def space_size(case: Case) -> int:
    return math.prod(len(i.options) for i in case.issues)


def points(case: Case, role_id: str, offer: Offer) -> float:
    return score_offer(case, role_id, offer).points


def best_offer_for(case: Case, role_id: str) -> Offer:
    role = case.role(role_id)
    return Offer(terms={i.id: max(i.option_ids(), key=role.points[i.id].get) for i in case.issues})


def best_points(case: Case, role_id: str) -> float:
    return points(case, role_id, best_offer_for(case, role_id))


def claim(case: Case, role_id: str, offer: Offer) -> float:
    """Share of the role's maximum on the issues the offer settles, in [0, 1].

    Comparable across partial and complete offers, which is what concession tracking needs.
    """
    role = case.role(role_id)
    got = top = low = 0.0
    for issue_id, option_id in offer.terms.items():
        table = role.points.get(issue_id)
        if table is None or option_id not in table:
            continue
        got += table[option_id]
        top += max(table.values())
        low += min(table.values())
    return (got - low) / (top - low) if top > low else 1.0


def surplus_share(case: Case, role_id: str, pts: float) -> float:
    """Points as a fraction of the gap between walking away (0) and the best deal (1)."""
    rv = case.role(role_id).reservation_value
    best = best_points(case, role_id)
    return (pts - rv) / (best - rv) if best > rv else 0.0


def complete_with(case: Case, offer: Offer | None, fill: Offer) -> Offer:
    """``offer`` with unsettled issues taken from ``fill``."""
    terms = dict(fill.terms)
    if offer:
        terms.update({k: v for k, v in offer.terms.items() if k in terms})
    return Offer(terms=terms)


def _evaluator(case: Case, role_id: str):
    """Fast (points, valid) for a complete offer as a tuple of option ids in issue order.

    Avoids building pydantic objects inside enumeration loops.
    """
    role = case.role(role_id)
    tables = [role.points[i.id] for i in case.issues]
    banned = [set() for _ in case.issues]
    index = {i.id: n for n, i in enumerate(case.issues)}
    for c in role.constraints:
        if c.hard:
            for issue_id, opts in c.disallowed.items():
                if issue_id in index:
                    banned[index[issue_id]].update(opts)

    def evaluate(combo: tuple[str, ...]) -> tuple[float, bool]:
        pts = sum(t[o] for t, o in zip(tables, combo, strict=False))
        return pts, not any(o in b for o, b in zip(combo, banned, strict=False))

    return evaluate


def _combos(case: Case) -> Iterator[tuple[str, ...]]:
    return itertools.product(*(i.option_ids() for i in case.issues))


def _offer(case: Case, combo: tuple[str, ...]) -> Offer:
    return Offer(terms={i.id: o for i, o in zip(case.issues, combo, strict=False)})


def closest_offer(
    case: Case, role_id: str, min_points: float, target: Offer | None = None
) -> Offer | None:
    """The complete offer worth at least ``min_points`` to ``role_id`` that differs from
    ``target`` on the fewest issues, conceding as much as allowed (lowest own points) on ties.

    Returns None if no offer reaches ``min_points``. Valid offers only (no hard-constraint
    violations for this role).
    """
    if space_size(case) <= MAX_ENUMERATE:
        evaluate = _evaluator(case, role_id)
        wanted = [target.terms.get(i.id) if target else None for i in case.issues]
        best: tuple[int, float] | None = None
        choice = None
        for combo in _combos(case):
            pts, valid = evaluate(combo)
            if pts < min_points or not valid:
                continue
            key = (
                sum(1 for o, w in zip(combo, wanted, strict=False) if w is not None and o != w),
                pts,
            )
            if best is None or key < best:
                best, choice = key, combo
        return _offer(case, choice) if choice else None
    return _greedy_closest(case, role_id, min_points, target)


def _greedy_closest(
    case: Case, role_id: str, min_points: float, target: Offer | None
) -> Offer | None:
    role = case.role(role_id)
    current = complete_with(case, target, best_offer_for(case, role_id))
    changed: set[str] = set()
    while points(case, role_id, current) < min_points:
        moves = [
            (role.points[i.id][o] - role.points[i.id][current.terms[i.id]], i.id, o)
            for i in case.issues
            if i.id not in changed
            for o in i.option_ids()
        ]
        gain, issue_id, option_id = max(moves, default=(0.0, "", ""))
        if gain <= 0:
            return None
        current = Offer(terms={**current.terms, issue_id: option_id})
        changed.add(issue_id)
    return current


def best_joint_offer(case: Case, role_id: str, min_points: float) -> Offer | None:
    """The complete offer maximizing joint points subject to ``role_id`` getting at least
    ``min_points``: the "trade across issues" benchmark used in hindsight feedback."""
    if space_size(case) > MAX_ENUMERATE:
        return None
    evaluate = _evaluator(case, role_id)
    others = [_evaluator(case, r.id) for r in case.roles if r.id != role_id]
    best: tuple[float, float] | None = None
    choice = None
    for combo in _combos(case):
        own, valid = evaluate(combo)
        if own < min_points or not valid:
            continue
        key = (own + sum(e(combo)[0] for e in others), own)
        if best is None or key > best:
            best, choice = key, combo
    return _offer(case, choice) if choice else None
