from negotrain.cases.offers import best_points, claim, closest_offer, points
from negotrain.counterpart import TIERS, RuleBasedCounterpart
from negotrain.counterpart.aspiration import aspiration_at, user_concessions
from negotrain.schemas import Offer, Session, Turn

HIGH = {"salary": "s150", "bonus": "b20", "remote": "r4", "start": "w4", "vacation": "v25"}
LOWER = {"salary": "s140", "bonus": "b20", "remote": "r4", "start": "w4", "vacation": "v25"}


def test_closest_offer_meets_minimum_and_stays_near_target(case):
    target = Offer(terms=HIGH)
    offer = closest_offer(case, "recruiter", 6000, target)
    assert points(case, "recruiter", offer) >= 6000
    assert closest_offer(case, "recruiter", best_points(case, "recruiter") + 1) is None


def test_claim_is_comparable_for_partial_offers(case):
    assert claim(case, "candidate", Offer(terms={"salary": "s150"})) == 1.0
    assert claim(case, "candidate", Offer(terms={"salary": "s120"})) == 0.0


def test_aspiration_starts_high_and_decays_to_a_floor_above_reservation(case):
    rv = case.role("recruiter").reservation_value
    for tier in TIERS.values():
        levels = [aspiration_at(case, "recruiter", tier, t) for t in range(30)]
        assert all(a >= b for a, b in zip(levels, levels[1:], strict=False))
        assert levels[-1] >= rv
    # Harder tiers hold out for more at every point in time.
    for t in (0, 3, 8):
        assert aspiration_at(case, "recruiter", TIERS[5], t) > aspiration_at(
            case, "recruiter", TIERS[1], t
        )


def test_user_concessions_counted_from_offers(case):
    s = Session(case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter")
    s.add_turn(Turn(index=0, speaker="user", text="", offer=Offer(terms=HIGH)), case)
    s.add_turn(Turn(index=1, speaker="counterpart", text="no"), case)
    s.add_turn(Turn(index=2, speaker="user", text="", offer=Offer(terms=LOWER)), case)
    assert user_concessions(case, s) == 1


def test_rule_based_counterpart_respects_schedule_and_accepts_good_offers(case):
    s = Session(case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter")
    bot = RuleBasedCounterpart(case, "recruiter", TIERS[3])
    s.add_turn(Turn(index=0, speaker="user", text="Hi?", offer=Offer(terms=HIGH)), case)
    reply = bot.respond(s)
    assert not reply.accept
    assert points(case, "recruiter", reply.offer) >= bot.minimum(s)
    s.add_turn(reply, case)
    generous = {"salary": "s120", "bonus": "b0", "remote": "r0", "start": "w4", "vacation": "v15"}
    s.add_turn(Turn(index=2, speaker="user", text="", offer=Offer(terms=generous)), case)
    assert bot.respond(s).accept
