import pytest

from negotrain.schemas import Case, Offer, Session, Turn


def test_case_requires_points_for_every_option(case):
    data = case.model_dump()
    del data["roles"][0]["points"]["salary"]["s150"]
    with pytest.raises(ValueError, match="missing options"):
        Case.model_validate(data)


def test_other_role(case):
    assert case.other_role("candidate").id == "recruiter"


def _session(case):
    return Session(case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter")


FULL = {"salary": "s140", "bonus": "b0", "remote": "r4", "start": "w4", "vacation": "v20"}


def test_accepting_complete_offer_records_agreement(case):
    s = _session(case)
    s.add_turn(Turn(index=0, speaker="user", text="How about this?", offer=Offer(terms=FULL)), case)
    s.add_turn(Turn(index=1, speaker="counterpart", text="Deal.", accept=True), case)
    assert s.status == "agreed"
    assert s.agreement == Offer(terms=FULL)


def test_cannot_accept_partial_offer(case):
    s = _session(case)
    s.add_turn(Turn(index=0, speaker="user", text="", offer=Offer(terms={"salary": "s150"})), case)
    with pytest.raises(ValueError, match="complete offer"):
        s.add_turn(Turn(index=1, speaker="counterpart", text="Deal.", accept=True), case)


def test_walk_away_is_impasse_and_closes_session(case):
    s = _session(case)
    s.add_turn(Turn(index=0, speaker="user", text="I'm out.", walk_away=True), case)
    assert s.status == "impasse"
    with pytest.raises(ValueError):
        s.add_turn(Turn(index=1, speaker="counterpart", text="Wait!"), case)
