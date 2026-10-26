"""Per-session behavioral features (T-024) and error flags.

Everything is computed from structured offers and the deterministic scorer, so the same code
works for rehearsals, logged real negotiations (outcome features only when there is no
transcript), and simulated users. Offer "claim" is the share of the user's maximum on the
issues an offer settles (offers.claim), so partial and complete offers are comparable.
"""

from __future__ import annotations

from negotrain.cases.offers import claim, surplus_share
from negotrain.cases.scoring import efficiency, score_offer
from negotrain.schemas import Case, Session

Features = dict[str, float | None]

FLAG_DESCRIPTIONS = {
    "weak_anchor": "Opened with a modest first offer (claimed under 70% of what was available)",
    "early_concession": "Conceded before the other side had conceded anything",
    "big_concessions": "Gave ground in large steps (averaging over 15% per concession)",
    "accepted_low": "Accepted a deal that captured little of the available surplus",
    "below_walkaway": "Agreed to a deal worth less than walking away",
    "no_logroll": "Left joint value on the table (deal under 90% of the best joint outcome)",
    "impasse_with_zopa": "Ended without a deal although the other side's offer beat walking away",
    "no_questions": "Asked no questions about the other side's interests",
}


def _offers(session: Session, speaker: str) -> list[tuple[int, object]]:
    return [(t.index, t.offer) for t in session.turns if t.speaker == speaker and t.offer]


def extract_features(session: Session, case: Case) -> Features:
    me, them = session.user_role_id, session.counterpart_role_id
    user_turns = [t for t in session.turns if t.speaker == "user"]
    mine = _offers(session, "user")
    theirs = _offers(session, "counterpart")
    f: Features = {
        "n_turns": float(len(user_turns)),
        "n_offers": float(len(mine)),
        "anchored_first": None,
        "first_offer_claim": None,
        "n_concessions": None,
        "mean_concession": None,
        "total_concession": None,
        "early_concession": None,
        "reciprocity": None,
        "question_rate": None,
        "agreement": None,
        "impasse": None,
        "points": None,
        "surplus_share": None,
        "efficiency": None,
    }
    if user_turns:
        asks = sum(1 for t in user_turns if "?" in t.text)
        f["question_rate"] = asks / len(user_turns)
    if mine or theirs:
        first_mine = mine[0][0] if mine else float("inf")
        first_theirs = theirs[0][0] if theirs else float("inf")
        f["anchored_first"] = 1.0 if first_mine < first_theirs else 0.0
    # Custom wording cannot be assigned a point claim or compared numerically with
    # listed offers. Keep observable behavior without inventing concession scores.
    if mine and not session.has_custom_terms:
        claims = [claim(case, me, o) for _, o in mine]
        f["first_offer_claim"] = claims[0]
        drops = [
            (i, a - b) for (i, _), a, b in zip(mine[1:], claims, claims[1:], strict=False) if b < a
        ]
        f["n_concessions"] = float(len(drops))
        f["mean_concession"] = sum(d for _, d in drops) / len(drops) if drops else 0.0
        f["total_concession"] = max(0.0, claims[0] - min(claims))
        if drops:
            # Their concessions: their offers getting worse for *them*.
            their_claims = [(i, claim(case, them, o)) for i, o in theirs]
            their_drops = [
                i
                for (_, a), (i, b) in zip(their_claims, their_claims[1:], strict=False)
                if b < a - 1e-9
            ]
            first_drop = drops[0][0]
            f["early_concession"] = 0.0 if any(i < first_drop for i in their_drops) else 1.0
            # A concession is reciprocal if they conceded since the user's previous offer.
            drop_turns = {i for i, _ in drops}
            reciprocated = sum(
                1
                for (i, _), (j, _) in zip(mine, mine[1:], strict=False)
                if j in drop_turns and any(i < k < j for k in their_drops)
            )
            f["reciprocity"] = reciprocated / len(drops)

    if session.status in ("agreed", "impasse"):
        f["agreement"] = 1.0 if session.status == "agreed" else 0.0
        f["impasse"] = 1.0 - f["agreement"]
        rv = case.role(me).reservation_value
        pts = rv
        if session.status == "agreed" and session.agreement is not None:
            pts = score_offer(case, me, session.agreement).points
            f["efficiency"] = efficiency(case, session.agreement)
        f["points"] = pts
        f["surplus_share"] = surplus_share(case, me, pts) if pts is not None else None
    return f


def flags(session: Session, case: Case, f: Features | None = None) -> list[str]:
    """Error patterns from PLAN.md §7 (behavior change), as keys of FLAG_DESCRIPTIONS."""
    f = f or extract_features(session, case)
    out = []
    if f["first_offer_claim"] is not None and f["first_offer_claim"] < 0.7:
        out.append("weak_anchor")
    if f["early_concession"] == 1.0:
        out.append("early_concession")
    if f["mean_concession"] is not None and f["mean_concession"] > 0.15:
        out.append("big_concessions")
    if session.status == "agreed":
        if f["surplus_share"] is not None and f["surplus_share"] < 0:
            out.append("below_walkaway")
        elif f["surplus_share"] is not None and f["surplus_share"] < 0.25:
            out.append("accepted_low")
        if f["efficiency"] is not None and f["efficiency"] < 0.9:
            out.append("no_logroll")
    if session.status == "impasse":
        offer = session.latest_offer_from("counterpart")
        if offer is not None and offer.is_complete(case):
            result = score_offer(case, session.user_role_id, offer)
            if result.valid and result.surplus is not None and result.surplus > 0:
                out.append("impasse_with_zopa")
    if f["question_rate"] is not None and f["n_turns"] and f["n_turns"] >= 3:
        if f["question_rate"] == 0:
            out.append("no_questions")
    return out
