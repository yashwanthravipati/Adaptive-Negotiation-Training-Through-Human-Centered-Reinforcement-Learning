from negotrain.cases.scoring import efficiency, joint_points, max_joint_offer, score_offer
from negotrain.schemas import Constraint, Offer

FULL = {"salary": "s140", "bonus": "b0", "remote": "r4", "start": "w4", "vacation": "v20"}


def test_score_full_offer(case):
    result = score_offer(case, "candidate", Offer(terms=FULL))
    assert result.points == 3000 + 0 + 2400 + 800 + 500
    assert result.surplus == result.points - 3500
    assert result.valid


def test_partial_offer_is_incomplete(case):
    result = score_offer(case, "candidate", Offer(terms={"salary": "s150"}))
    assert result.points == 4500
    assert not result.complete and not result.valid


def test_unknown_term_is_a_violation(case):
    result = score_offer(case, "candidate", Offer(terms={**FULL, "salary": "s999"}))
    assert result.violations == ["unknown term salary=s999"]


def test_hard_constraint_violation(case):
    case.role("recruiter").constraints.append(
        Constraint(description="No bonus above $10k", disallowed={"bonus": ["b20"]})
    )
    result = score_offer(case, "recruiter", Offer(terms={**FULL, "bonus": "b20"}))
    assert result.violations == ["No bonus above $10k"]


def test_max_joint_offer_and_efficiency(case):
    best = max_joint_offer(case)
    assert joint_points(case, best) == 11900
    assert efficiency(case, best) == 1.0
    # Bonus and remote are the integrative issues: giving the candidate a bonus instead of
    # remote days leaves value on the table.
    worse = Offer(terms={**best.terms, "bonus": "b20", "remote": "r0"})
    assert efficiency(case, worse) < 1.0
