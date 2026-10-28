import random

from negotrain.counterpart import TIERS, RuleBasedCounterpart
from negotrain.curriculum import counterpart_for, next_scenario
from negotrain.profiling import build_profile, extract_features, flags
from negotrain.schemas import Offer, Session, Turn
from negotrain.simulation import ScriptedUser, run_episode


def play(case, *, open_share=0.95, step=0.05, tier=3):
    s = Session(
        case_id=case.id,
        user_role_id="candidate",
        counterpart_role_id="recruiter",
        counterpart_profile=TIERS[tier],
    )
    user = ScriptedUser(case, "candidate", open_share=open_share, step=step)
    run_episode(case, s, RuleBasedCounterpart(case, "recruiter", TIERS[tier]), user, max_turns=60)
    return s


def test_features_on_a_hand_written_session(case):
    s = Session(case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter")
    high = {"salary": "s150", "bonus": "b20", "remote": "r4", "start": "w4", "vacation": "v25"}
    low = {"salary": "s130", "bonus": "b0", "remote": "r2", "start": "w4", "vacation": "v20"}
    s.add_turn(
        Turn(index=0, speaker="user", text="What matters to you?", offer=Offer(terms=high)), case
    )
    s.add_turn(Turn(index=1, speaker="counterpart", text="No.", offer=Offer(terms=low)), case)
    s.add_turn(Turn(index=2, speaker="user", text="Fine", offer=Offer(terms=low)), case)
    s.add_turn(Turn(index=3, speaker="counterpart", text="Deal", accept=True), case)
    f = extract_features(s, case)
    assert f["anchored_first"] == 1.0
    assert f["first_offer_claim"] == 1.0
    assert f["n_concessions"] == 1.0
    assert f["early_concession"] == 1.0  # the counterpart never conceded first
    assert f["question_rate"] == 0.5
    assert f["agreement"] == 1.0
    assert f["points"] == 1500 + 0 + 1200 + 800 + 500
    assert "early_concession" in flags(s, case, f)
    assert "big_concessions" in flags(s, case, f)


def test_features_for_a_logged_real_negotiation_without_turns(case):
    deal = {"salary": "s140", "bonus": "b0", "remote": "r4", "start": "w4", "vacation": "v20"}
    s = Session(
        case_id=case.id,
        user_role_id="candidate",
        counterpart_role_id="recruiter",
        kind="real",
        status="agreed",
        agreement=Offer(terms=deal),
    )
    f = extract_features(s, case)
    assert f["points"] == 3000 + 0 + 2400 + 800 + 500
    assert f["first_offer_claim"] is None


def test_profile_separates_a_weak_anchor_from_a_strong_one(case):
    from negotrain.cases.offers import best_offer_for

    def history(role):
        sessions = []
        for _ in range(3):
            session = Session(
                case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter"
            )
            session.add_turn(
                Turn(
                    index=0, speaker="counterpart", text="", offer=best_offer_for(case, "recruiter")
                ),
                case,
            )
            session.add_turn(
                Turn(index=1, speaker="user", text="", offer=best_offer_for(case, role)), case
            )
            session.add_turn(Turn(index=2, speaker="counterpart", text="", walk_away=True), case)
            sessions.append((session, case))
        return sessions

    pw = build_profile("w", history("recruiter"))
    ps = build_profile("s", history("candidate"))
    assert pw.belief.components["error:3"].mean > ps.belief.components["error:3"].mean
    assert pw.belief.components["error:3"].opportunities == 3


def test_empty_profile_is_neutral(case):
    p = build_profile("nobody", [])
    assert p.n_sessions == 0
    assert all(b.mean == 0.5 and b.opportunities == 0 for b in p.belief.components.values())


def test_curriculum_starts_at_tier_two_and_targets_the_weakness(case):
    spec = next_scenario(build_profile("x", []), [], [case.id])
    assert spec.tier == 2 and spec.case_id == case.id
    weak = [(play(case, open_share=0.3, tier=2), case)]
    spec = next_scenario(build_profile("w", weak), weak, [case.id])
    assert spec.focus is not None
    profile = counterpart_for(spec, random.Random(0))
    for dial, value in spec.dial_overrides.items():
        assert getattr(profile, dial) == value


def test_curriculum_steps_up_after_two_strong_results(case):
    from negotrain.cases.offers import closest_offer

    strong = []
    for _ in range(2):
        session = play(case, tier=1)
        session.status = "agreed"
        session.agreement = closest_offer(case, "candidate", 7000)
        strong.append((session, case))
    spec = next_scenario(build_profile("s", strong), strong)
    assert spec.tier == 2
