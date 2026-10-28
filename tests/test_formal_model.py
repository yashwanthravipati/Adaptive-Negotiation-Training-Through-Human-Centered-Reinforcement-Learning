import itertools
import random

import pytest

from negotrain.cases.offers import feasible_best_points, points, surplus_share
from negotrain.llm import ScriptedLLM
from negotrain.profiling.belief import BeliefState, BetaBelief, CostModel, choose_focus
from negotrain.profiling.observations import Count, Observations, case_facts, observe
from negotrain.profiling.tagging import tag_session
from negotrain.schemas import Case, Issue, Offer, Option, RoleSheet, Session, Turn, TurnTags
from negotrain.simulation import episode_score, episode_value


@pytest.fixture
def tiny():
    opts = list("abcdef")
    return Case(
        id="tiny",
        title="Finite test",
        public_brief="Choose a package",
        issues=[Issue(id="x", name="X", options=[Option(id=o, label=o) for o in opts])],
        roles=[
            RoleSheet(
                id="u",
                name="User",
                confidential_brief="USER SECRET",
                points={"x": dict(zip(opts, [100, 80, 60, 40, 20, 0], strict=True))},
                reservation_value=20,
            ),
            RoleSheet(
                id="c",
                name="Counterpart",
                confidential_brief="COUNTERPART SECRET",
                points={"x": dict(zip(opts, [0, 20, 40, 60, 60, 100], strict=True))},
                reservation_value=20,
            ),
        ],
    )


def new_session(case):
    return Session(case_id=case.id, user_role_id="u", counterpart_role_id="c")


def put(session, case, who, option=None, **kw):
    session.add_turn(
        Turn(
            index=len(session.turns),
            speaker=who,
            text="",
            offer=Offer(terms={"x": option}) if option else None,
            **kw,
        ),
        case,
    )


def test_reward_uses_counterpart_feasible_optimum_and_preserves_losses(tiny):
    assert feasible_best_points(tiny, "u") == 80
    assert surplus_share(tiny, "u", 80) == 1
    assert surplus_share(tiny, "u", 0) == pytest.approx(-1 / 3)
    s = new_session(tiny)
    put(s, tiny, "counterpart", "b")
    assert episode_score(tiny, s) == 0  # an unaccepted standing offer is not a deal
    assert episode_value(tiny, s) == 20
    put(s, tiny, "user", accept=True)
    assert episode_score(tiny, s) == 1


def test_exact_frontier_matches_enumeration_after_point_table_changes(case):
    rng = random.Random(42)
    for _ in range(5):
        for role in case.roles:
            role.reservation_value = 0
            for table in role.points.values():
                for option in table:
                    table[option] = rng.randint(-10, 10)
        offers = [
            Offer(terms=dict(zip([i.id for i in case.issues], combo, strict=True)))
            for combo in itertools.product(*(i.option_ids() for i in case.issues))
        ]
        expected = max(
            points(case, "candidate", d) for d in offers if points(case, "recruiter", d) >= 0
        )
        assert feasible_best_points(case, "candidate") == expected


def test_all_numeric_detectors_count_opportunities_and_occurrences(tiny):
    s = new_session(tiny)
    for who, option in [
        ("counterpart", "f"),
        ("user", "b"),
        ("counterpart", "f"),
        ("user", "c"),
        ("counterpart", "f"),
        ("user", "d"),
        ("counterpart", "d"),
        ("user", "e"),
        ("counterpart", "f"),
    ]:
        put(s, tiny, who, option, tags=TurnTags(source="human"))
    put(s, tiny, "user", accept=True, tags=TurnTags(source="human"))
    obs = observe(s, tiny)
    expected = {
        "error:1": (3, 2),
        "error:2": (2, 1),
        "error:3": (1, 0),
        "error:4": (1, 1),
        "error:5": (1, 0),
        "error:6": (4, 1),
    }
    for key, (o, x) in expected.items():
        assert (obs.counts[key].opportunities, obs.counts[key].occurrences) == (o, x)
    assert obs.counts["error:6"].turns == [7]
    assert obs.counts[case_facts(tiny, "u")[0].id].occurrences == 4
    assert obs.score == pytest.approx(-1 / 3)


def test_ignore_issue_uses_whole_session_and_missing_tags_are_missing(tiny):
    s = new_session(tiny)
    put(s, tiny, "user", "b")
    put(s, tiny, "counterpart", accept=True)
    obs = observe(s, tiny)
    assert obs.counts["error:5"].opportunities == 0
    assert obs.counts["rapport"].opportunities == 0
    s.turns[0].tags = TurnTags(source="human")
    assert observe(s, tiny).counts["error:5"].occurrences == 1
    s.turns[0].tags.raised_issues = ["x"]
    assert observe(s, tiny).counts["error:5"].occurrences == 0


def test_no_counterpart_offer_means_no_anchor_opportunity(tiny):
    s = new_session(tiny)
    put(s, tiny, "user", "f")
    put(s, tiny, "counterpart", accept=True)
    assert observe(s, tiny).counts["error:3"].opportunities == 0


def test_discounted_beta_matches_explicit_pseudocounts():
    b = BetaBelief()
    b.update(2, 4, 0.5)
    b.update(1, 3, 0.5)
    assert (b.alpha, b.beta) == (3, 4)
    assert b.mean == 3 / 7
    lo, hi = b.interval()
    assert lo < b.mean < hi
    b.update(0, 0, 0.5)
    assert (b.alpha, b.beta) == (2, 2.5)
    report = BetaBelief()
    report.update(2, 4, 0.5, discount_prior=True)
    assert (report.alpha, report.beta) == (2.5, 2.5)
    with pytest.raises(ValueError):
        b.update(2, 1, 0.5)


def test_filter_discounts_once_per_session_including_unobserved_components():
    b = BeliefState(components={"error:1": BetaBelief(alpha=5, beta=3)}, forgetting=0.5)
    b.update(Observations(counts={"rapport": Count(opportunities=2, occurrences=1)}, score=0))
    assert (b.components["error:1"].alpha, b.components["error:1"].beta) == (3, 2)
    assert b.components["rapport"].mean == 0.5


def test_ucb_weights_uncertainty_in_cost_units_and_inverts_positive_traits():
    b = BeliefState(
        components={
            "error:1": BetaBelief(alpha=40, beta=60),
            "error:2": BetaBelief(),
            "rapport": BetaBelief(alpha=1, beta=9),
        }
    )
    costs = CostModel(population={"error:1": 10, "error:2": 0.01, "rapport": 1})
    assert choose_focus(b, costs) == "error:1"
    costs.population["rapport"] = 10
    assert choose_focus(b, costs, policy="greedy") == "rapport"
    assert choose_focus(b, costs, policy="none") is None
    assert choose_focus(b, costs, policy="random", rng=random.Random(8)) == choose_focus(
        b, costs, policy="random", rng=random.Random(8)
    )
    costs.add("error:1", -0.2)
    costs.add("error:1", 0.4)
    assert costs.weight("error:1") == pytest.approx(0.1)


def test_tagger_is_role_scoped_and_validates_before_mutation(tiny):
    s = new_session(tiny)
    put(s, tiny, "user", "b")
    llm = ScriptedLLM(
        [{"turns": [{"index": 0, "fact_ids": [], "raised_issues": ["x"], "rapport": True}]}]
    )
    tag_session(s, tiny, llm)
    assert s.turns[0].tags.rapport
    assert "COUNTERPART SECRET" not in str(llm.calls)
    bad = ScriptedLLM(
        [{"turns": [{"index": 0, "fact_ids": ["bogus"], "raised_issues": [], "rapport": False}]}]
        * 2
    )
    with pytest.raises(ValueError):
        tag_session(s, tiny, bad)
    assert s.turns[0].tags.rapport
    corrected = ScriptedLLM(
        [
            {"turns": []},
            {"turns": [{"index": 0, "fact_ids": [], "raised_issues": ["x"], "rapport": True}]},
        ]
    )
    tag_session(s, tiny, corrected)
    assert len(corrected.calls) == 2
    assert s.turns[0].tags.rapport


def test_deadline_allows_final_counterpart_response_and_expires(tiny):
    s = new_session(tiny)
    for _ in range(20):
        put(s, tiny, "user")
        assert s.status == "active"
        put(s, tiny, "counterpart")
    assert s.status == "impasse"
    with pytest.raises(ValueError):
        put(s, tiny, "user")


def test_invalid_actions_fail_without_mutating_transcript(tiny):
    s = new_session(tiny)
    for kw in ({"accept": True, "walk_away": True}, {"offer": Offer(terms={"x": "bad"})}):
        with pytest.raises(ValueError):
            s.add_turn(Turn(index=0, speaker="user", text="", **kw), tiny)
        assert not s.turns
