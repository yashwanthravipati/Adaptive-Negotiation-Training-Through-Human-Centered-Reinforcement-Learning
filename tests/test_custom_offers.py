import pytest

from negotrain.cases.offers import claim
from negotrain.cases.scoring import efficiency, score_offer
from negotrain.counterpart import TIERS, RuleBasedCounterpart
from negotrain.counterpart.aspiration import user_concessions
from negotrain.curriculum import next_scenario
from negotrain.feedback import analyze_session, build_report, outcome_summary
from negotrain.feedback.coaching import transcript
from negotrain.llm import ScriptedLLM
from negotrain.profiling import build_profile, extract_features, flags
from negotrain.schemas import Constraint, Offer, Session, Turn
from negotrain.sessions import SessionStore
from test_counterpart import FULL, move, setup

CUSTOM = "Remote during the harvest; on-site for quarterly planning with travel covered."


def custom_offer():
    return Offer(
        terms={k: v for k, v in FULL.items() if k != "remote"},
        custom_terms={"remote": CUSTOM},
    )


def custom_session(case):
    session = Session(
        case_id=case.id,
        user_role_id="candidate",
        counterpart_role_id="recruiter",
        counterpart_profile=TIERS[3],
    )
    session.add_turn(
        Turn(index=0, speaker="user", text="Would this work?", offer=custom_offer()), case
    )
    return session


def test_labels_support_listed_custom_and_unsettled_issues(case):
    offer = Offer.from_labels(
        case, {"salary": "$150,000", "remote": CUSTOM, "bonus": "  ", "start": None}
    )
    assert offer.terms == {"salary": "s150"}
    assert offer.custom_terms == {"remote": CUSTOM}
    assert not offer.is_complete(case)
    assert CUSTOM in offer.describe(case)
    assert Offer.model_validate_json(offer.model_dump_json()) == offer
    assert Offer.model_validate({"terms": FULL}).custom_terms == {}


@pytest.mark.parametrize(
    "data",
    [
        {"terms": {"remote": "r4"}, "custom_terms": {"remote": CUSTOM}},
        {"custom_terms": {"remote": "  "}},
    ],
)
def test_conflicting_or_blank_custom_terms_are_invalid(data):
    with pytest.raises(ValueError):
        Offer.model_validate(data)


def test_custom_terms_are_complete_but_have_no_invented_points(case):
    offer = custom_offer()
    assert offer.is_complete(case)
    for role in case.roles:
        score = score_offer(case, role.id, offer)
        assert score.valid
        assert score.points is None and score.surplus is None
        assert claim(case, role.id, offer) is None
    assert efficiency(case, offer) is None


def test_custom_agreement_persists_exact_wording(case, tmp_path):
    session = custom_session(case)
    session.add_turn(Turn(index=1, speaker="counterpart", text="Agreed", accept=True), case)
    store = SessionStore(tmp_path)
    store.save(session)
    restored = store.load(session.id)
    assert restored == session
    assert restored.status == "agreed" and restored.agreement == custom_offer()


def test_partial_custom_offer_cannot_be_accepted_or_mutate_session(case):
    session = Session(case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter")
    session.add_turn(
        Turn(index=0, speaker="user", text="", offer=Offer(custom_terms={"remote": CUSTOM})), case
    )
    with pytest.raises(ValueError, match="complete offer"):
        session.add_turn(Turn(index=1, speaker="counterpart", text="Deal", accept=True), case)
    assert session.status == "active" and len(session.turns) == 1


def test_counterpart_can_accept_custom_terms_without_substitution_or_private_leaks(case):
    agent, _, llm = setup(case, [move(accept=True)], enforce=True)
    session = custom_session(case)
    reply = agent.respond(session)
    assert reply.accept and agent.fallbacks == 0
    session.add_turn(reply, case)
    assert session.agreement.custom_terms["remote"] == CUSTOM
    system, messages = llm.calls[0]
    assert CUSTOM in str(messages)
    assert case.role("candidate").confidential_brief not in system + str(messages)


def test_counterpart_custom_counteroffer_survives_in_its_history(case):
    response = move("I propose this combination.", {k: v for k, v in FULL.items() if k != "remote"})
    response["offer"].append({"issue_id": "remote", "custom_text": CUSTOM})
    agent, session, llm = setup(case, [response, move("Any thoughts?")], enforce=True)
    reply = agent.respond(session)
    assert reply.offer == custom_offer()
    session.add_turn(reply, case)
    session.add_turn(Turn(index=1, speaker="user", text="Can we discuss travel?"), case)
    agent.respond(session)
    assert CUSTOM in str(llm.calls[-1][1])


def test_custom_offer_does_not_bypass_a_known_hard_constraint(case):
    case.role("recruiter").constraints.append(
        Constraint(description="A bonus is required", disallowed={"bonus": ["b0"]})
    )
    agent, _, llm = setup(case, [move(accept=True), move("We need a bonus.")])
    reply = agent.respond(custom_session(case))
    assert not reply.accept
    assert "A bonus is required" in str(llm.calls[-1][1])


def test_custom_and_listed_turns_do_not_create_false_concessions(case):
    session = custom_session(case)
    session.turns.insert(0, Turn(index=0, speaker="user", text="", offer=Offer(terms=FULL)))
    session.turns[-1].index = 1
    assert user_concessions(case, session) == 0
    reply = RuleBasedCounterpart(case, "recruiter", TIERS[3]).respond(session)
    assert not reply.accept
    assert reply.offer and not reply.offer.custom_terms
    assert "offline" in reply.text


def test_custom_debrief_preserves_unknown_metrics_and_does_not_penalize_profile(case):
    session = custom_session(case)
    session.add_turn(Turn(index=1, speaker="counterpart", text="Agreed", accept=True), case)
    outcome = outcome_summary(session, case)
    assert outcome.points is None and outcome.surplus is None and outcome.efficiency is None
    assert CUSTOM in transcript(session, case)
    features = extract_features(session, case)
    for key in ("points", "surplus_share", "efficiency", "first_offer_claim", "mean_concession"):
        assert features[key] is None
    assert features["agreement"] == 1
    assert not flags(session, case)
    profile = build_profile("local", [(session, case)])
    for key in ("anchoring", "concession_discipline", "value_creation", "value_claiming"):
        assert profile.skill(key).n == 0
    assert next_scenario(profile, [(session, case)]).tier == 3
    report = build_report(session, case)
    assert "no defined point score" in report.headline
    assert not any("opened ambitiously" in strength for strength in report.strengths)


def test_custom_feedback_skips_numeric_simulations_but_coach_sees_full_terms(case):
    session = custom_session(case)
    session.add_turn(Turn(index=1, speaker="counterpart", text="Agreed", accept=True), case)

    def must_not_simulate():
        pytest.fail("custom terms must not be silently mapped to listed options in rollouts")

    counterfactuals = analyze_session(session, case, must_not_simulate)
    assert counterfactuals.estimates == [] and counterfactuals.skipped_reason
    llm = ScriptedLLM(
        [
            {
                "headline": "Creative trade.",
                "strengths": [],
                "improvements": [],
                "moments": [],
                "next_focus": "Feasibility",
            }
        ]
    )
    report = build_report(session, case, counterfactuals, llm)
    assert report.source == "llm"
    assert CUSTOM in llm.calls[0][1][0]["content"]
    assert '"points": null' in llm.calls[0][1][0]["content"]
