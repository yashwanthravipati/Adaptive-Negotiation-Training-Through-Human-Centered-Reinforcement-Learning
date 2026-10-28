import random

import pytest

from negotrain.cases.offers import (
    best_offer_for,
    best_points,
    listed_packages,
    points,
    surplus_share,
)
from negotrain.counterpart import TIERS, CounterpartAgent, RuleBasedCounterpart
from negotrain.counterpart.aspiration import aspiration_at
from negotrain.feedback.critical import CriticalTurn
from negotrain.feedback.rollouts import Action, analyze_session, estimate_turn_values
from negotrain.llm import ScriptedLLM
from negotrain.schemas import Session, Turn, TurnTags


def setup(case, focus, tier=3):
    profile = TIERS[tier].model_copy(update={"focus": focus})
    session = Session(
        case_id=case.id,
        user_role_id="candidate",
        counterpart_role_id="recruiter",
        counterpart_profile=profile,
    )
    return session, RuleBasedCounterpart(case, "recruiter", profile)


def wait(session, case, tags=None):
    session.add_turn(
        Turn(index=len(session.turns), speaker="user", text="I am considering it.", tags=tags), case
    )


def test_every_tier_has_independent_monotone_deadline_schedule(case):
    for n in range(20):
        levels = [aspiration_at(case, "recruiter", TIERS[t], n) for t in range(1, 6)]
        assert levels == sorted(levels)
    p = TIERS[3]
    rv = case.role("recruiter").reservation_value
    span = best_points(case, "recruiter") - rv
    for rate in (0.01, 0.2):
        changed = p.model_copy(update={"concession_rate": rate})
        assert aspiration_at(case, "recruiter", changed, 19) == pytest.approx(
            rv + p.concession_floor * span
        )


def test_conceding_first_hook_waits_six_turns_without_conceding(case):
    s, bot = setup(case, "error:1")
    values = []
    for _ in range(7):
        reply = bot.respond(s)
        values.append(points(case, "recruiter", reply.offer))
        s.add_turn(reply, case)
        wait(s, case)
    assert all(b >= a for a, b in zip(values[:5], values[1:6], strict=True))
    assert values[6] < values[5]


def test_anchor_hook_opens_at_counterpart_maximum(case):
    s, bot = setup(case, "error:3", tier=1)
    assert points(case, "recruiter", bot.respond(s).offer) == best_points(case, "recruiter")


def test_accepting_low_hook_offers_low_positive_surplus_and_holds(case):
    s, bot = setup(case, "error:4")
    offers = []
    for _ in range(3):
        reply = bot.respond(s)
        assert reply.hook_applied
        assert points(case, "recruiter", reply.offer) >= bot.minimum(s)
        offers.append(reply.offer)
        s.add_turn(reply, case)
        wait(s, case)
    assert offers[0] == offers[1] == offers[2]
    assert 0 <= surplus_share(case, "candidate", points(case, "candidate", offers[0])) < 0.25


def test_ignored_issue_and_two_package_hooks(case):
    s, bot = setup(case, "error:5")
    issue = bot.ignored_issue()
    worst = min(case.role("recruiter").points[issue], key=case.role("recruiter").points[issue].get)
    for _ in range(4):
        reply = bot.respond(s)
        assert reply.hook_applied and reply.offer.terms[issue] == worst
        assert case.issue(issue).name.lower() not in reply.text.lower()
        s.add_turn(reply, case)
        wait(s, case)
    s, bot = setup(case, "error:6")
    first = bot.respond(s)
    s.add_turn(first, case)
    wait(s, case)
    second = bot.respond(s)
    assert second.hook_applied and second.offer != first.offer


def test_unreciprocated_hook_is_seeded_and_roughly_half_of_new_concessions(case):
    s, bot = setup(case, "error:2")
    offers = sorted(listed_packages(case, "candidate"), key=lambda item: -item[1])
    distinct = []
    for offer, value, _ in offers:
        if not distinct or value < points(case, "candidate", distinct[-1]):
            distinct.append(offer)
        if len(distinct) == 3:
            break
    for i, offer in enumerate(distinct):
        if i:
            s.add_turn(
                Turn(
                    index=len(s.turns),
                    speaker="counterpart",
                    text="",
                    offer=best_offer_for(case, "recruiter"),
                ),
                case,
            )
        s.add_turn(Turn(index=len(s.turns), speaker="user", text="", offer=offer), case)
    held = 0
    for seed in range(1000):
        s.seed = seed
        level = bot.minimum(s)
        assert bot.minimum(s) == level
        held += level == best_points(case, "recruiter")
    assert 400 < held < 600


def test_rapport_hook_uses_observed_tag_not_unobservable_user_state(case):
    s, bot = setup(case, "rapport")
    s.add_turn(bot.respond(s), case)
    wait(s, case, TurnTags(source="human", rapport=False))
    baseline = bot.minimum(s)
    s.turns[-1].tags.rapport = True
    assert bot.minimum(s) < baseline


def test_llm_cannot_replace_the_controller_move_or_read_users_sheet(case):
    s, bot = setup(case, "error:3")
    llm = ScriptedLLM([{"message": "Here is my proposal.", "accept": True, "offer": []}])
    agent = CounterpartAgent(case, "recruiter", s.counterpart_profile, llm)
    expected, actual = bot.respond(s), agent.respond(s)
    assert actual.offer == expected.offer and not actual.accept
    assert case.role("candidate").confidential_brief not in str(llm.calls)


def test_credit_selects_on_one_batch_and_scores_on_fresh_data(case, monkeypatch):
    import negotrain.feedback.rollouts as engine

    s, bot = setup(case, None)
    s.add_turn(
        Turn(index=0, speaker="user", text="offer", offer=best_offer_for(case, "candidate")), case
    )
    s.status = "impasse"
    monkeypatch.setattr(engine, "alternatives", lambda *a: [Action(label="Alternative", text="x")])
    observed = []
    # Selection favors the alternative. Fresh scoring reverses that noisy ranking.
    results = iter([0.2] * 4 + [0.9] * 4 + [0.8] * 4 + [0.4] * 4)

    def rollout(*args, **kw):
        observed.append(kw["seed"])
        return next(results), True

    monkeypatch.setattr(engine, "rollout", rollout)
    estimate = estimate_turn_values(
        s, case, CriticalTurn(turn_index=0, kind="offer", description="test"), lambda: bot, n=4
    )
    assert estimate.selected_index == 1
    assert estimate.delta == pytest.approx(-0.4)  # never clip negative fresh-batch credit
    assert set(observed[:8]).isdisjoint(observed[8:])
    assert estimate.delta_interval == pytest.approx((-0.4, -0.4))


def test_counterfactuals_reject_active_sessions(case):
    s, bot = setup(case, None)
    with pytest.raises(ValueError, match="only after"):
        analyze_session(s, case, lambda: bot)


def test_sampled_focus_schedules_never_cross_walkaway(case):
    rng = random.Random(29)
    for _ in range(100):
        tier = rng.randint(1, 5)
        s, bot = setup(case, rng.choice([None, "error:1", "error:3", "error:4", "error:5"]), tier)
        for _ in range(5):
            reply = bot.respond(s)
            if reply.offer:
                assert points(case, "recruiter", reply.offer) >= bot.minimum(s)
            s.add_turn(reply, case)
            if s.status != "active":
                break
            wait(s, case)
