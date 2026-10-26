import pytest

from negotrain.counterpart import TIERS, CounterpartAgent, RuleBasedCounterpart
from negotrain.feedback import (
    alternatives,
    analyze_session,
    build_report,
    critical_turns,
    estimate_calls,
)
from negotrain.llm import ScriptedLLM
from negotrain.schemas import Offer, Session, Turn
from negotrain.simulation import ScriptedUser, episode_value, run_episode


def finished_session(case, tier=3):
    s = Session(
        case_id=case.id,
        user_role_id="candidate",
        counterpart_role_id="recruiter",
        counterpart_profile=TIERS[tier],
    )
    run_episode(
        case,
        s,
        RuleBasedCounterpart(case, "recruiter", TIERS[tier]),
        ScriptedUser(case, "candidate", step=0.1),
        max_turns=40,
    )
    return s


def test_episode_ends_in_a_deal_at_or_above_both_walkaways(case):
    s = finished_session(case)
    assert s.status == "agreed"
    assert episode_value(case, s) >= case.role("candidate").reservation_value


def test_critical_turns_find_offers_concessions_and_accept(case):
    s = finished_session(case)
    found = critical_turns(s, case, cap=10)
    kinds = {c.kind for c in found}
    assert {"anchor_response", "concession", "accept"} <= kinds
    assert len(critical_turns(s, case, cap=2)) == 2
    assert all(s.turns[c.turn_index].speaker == "user" for c in found)


def test_alternatives_differ_from_actual_move(case):
    s = finished_session(case)
    for c in critical_turns(s, case):
        actual = s.turns[c.turn_index]
        alts = alternatives(s, case, c.turn_index, k=3)
        assert 1 <= len(alts) <= 3
        assert all(a.offer is None or a.offer != actual.offer for a in alts)


def test_analysis_with_rule_based_opponent_is_deterministic(case):
    s = finished_session(case)

    def make():
        return RuleBasedCounterpart(case, "recruiter", TIERS[3])

    a = analyze_session(s, case, make, opponent="rule-based", n=1, k=2)
    b = analyze_session(s, case, make, opponent="rule-based", n=1, k=2)
    assert [e.model_dump() for e in a.estimates] == [e.model_dump() for e in b.estimates]
    for e in a.estimates:
        assert e.values[0].action.actual
        assert all(v.mean is not None for v in e.values)
        # Replaying what the user actually did reproduces the real outcome's neighborhood.
        assert e.actual.mean >= case.role("candidate").reservation_value


def test_analysis_with_llm_counterpart_uses_scripted_moves(case):
    s = Session(
        case_id=case.id,
        user_role_id="candidate",
        counterpart_role_id="recruiter",
        counterpart_profile=TIERS[3],
    )
    offer = {"salary": "s150", "bonus": "b20", "remote": "r4", "start": "w4", "vacation": "v25"}
    s.add_turn(Turn(index=0, speaker="user", text="Hello", offer=Offer(terms=offer)), case)

    def counter(system, messages):
        return {"message": "Too rich.", "offer": [], "accept": False, "walk_away": False}

    llm = ScriptedLLM([counter] * 50)
    report = analyze_session(
        s,
        case,
        lambda: CounterpartAgent(case, "recruiter", TIERS[3], llm),
        n=1,
        k=1,
        horizon=2,
        max_workers=1,
    )
    assert len(report.estimates) == 1
    assert len(llm.calls) == 2  # actual + 1 alternative, one LLM turn each before finishing
    assert all(v.errors == 0 for v in report.estimates[0].values)


def test_estimate_calls():
    assert estimate_calls(3, 2, 2, 4) == 36


def test_template_report_without_llm(case):
    s = finished_session(case, tier=5)
    report = build_report(
        s,
        case,
        analyze_session(s, case, lambda: RuleBasedCounterpart(case, "recruiter", TIERS[5]), n=1),
    )
    assert report.source == "template"
    assert report.headline and report.improvements


def test_llm_report_and_fallback_on_error(case):
    s = finished_session(case)
    canned = {
        "headline": "Solid.",
        "strengths": ["a"],
        "improvements": ["b"],
        "moments": [],
        "next_focus": "anchoring",
    }
    llm = ScriptedLLM([canned])
    report = build_report(s, case, None, llm)
    assert report.source == "llm" and report.headline == "Solid."
    system, messages = llm.calls[0]
    assert "Never" in system or "never" in system
    assert "Transcript" in messages[0]["content"]

    def boom(system, messages):
        raise RuntimeError("api down")

    assert build_report(s, case, None, ScriptedLLM([boom])).source == "template"


@pytest.mark.parametrize("tier", [1, 5])
def test_harder_counterparts_leave_the_user_less(case, tier):
    easy = episode_value(case, finished_session(case, tier=1))
    assert episode_value(case, finished_session(case, tier=tier)) <= easy
