import json
import random

import pytest

from negotrain.cases.offers import best_offer_for
from negotrain.evaluation import Experiment, interval, oracle_trial
from negotrain.llm import ScriptedLLM
from negotrain.profiling.belief import CostModel
from negotrain.profiling.observations import ERRORS
from negotrain.schemas import Session, Turn
from negotrain.virtual_users import LLMUser, VirtualTraits, VirtualUser


def test_sampled_users_and_learning_are_reproducible_and_allow_nonresponders():
    a = VirtualTraits.sample(random.Random(3))
    assert a == VirtualTraits.sample(random.Random(3))
    before = a.errors.copy()
    a.response["error:1"] = 0
    a.learn("error:1")
    assert a.errors == before
    a.response["error:2"] = 0.4
    a.learn("error:2")
    assert a.errors["error:2"] == pytest.approx(before["error:2"] * 0.6)
    assert all(a.errors[k] == before[k] for k in ERRORS if k != "error:2")


def test_grounded_user_actions_do_not_depend_on_opponents_private_sheet(case):
    traits = VirtualTraits.sample(random.Random(9))
    original = VirtualUser(case, "candidate", traits, 10)
    changed = case.model_copy(deep=True)
    other = changed.role("recruiter")
    other.confidential_brief = "SECRET DIFFERENT"
    other.reservation_value = 100000
    for table in other.points.values():
        for option in table:
            table[option] *= -123
    alternative = VirtualUser(changed, "candidate", traits, 10)
    session = Session(case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter")
    session.add_turn(
        Turn(
            index=0,
            speaker="counterpart",
            text="My position",
            offer=best_offer_for(case, "recruiter"),
        ),
        case,
    )
    a, b = original.respond(session), alternative.respond(session)
    assert a.model_dump(exclude={"created_at"}) == b.model_dump(exclude={"created_at"})


def test_llm_persona_context_is_role_projected_and_uses_feedback(case):
    llm = ScriptedLLM(
        [{"message": "Let's discuss this", "offer": [], "accept": False, "walk_away": False}]
    )
    user = LLMUser(
        case, "candidate", VirtualTraits.sample(random.Random(1)), llm, ["Ask for reciprocity."]
    )
    s = Session(case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter")
    user.respond(s)
    system = llm.calls[0][0]
    assert case.role("candidate").confidential_brief in system
    assert case.role("recruiter").confidential_brief not in system
    assert "Ask for reciprocity." in system


def test_oracle_reward_depends_on_true_learning_not_posterior_changes():
    traits = VirtualTraits.sample(random.Random(2))
    traits.response = dict.fromkeys(ERRORS, 0)
    costs = CostModel(population=dict.fromkeys(ERRORS, 0.5), opportunities=dict.fromkeys(ERRORS, 4))
    result = oracle_trial(traits, costs, "ucb", 10, 0.8, 1)
    assert result["true_error_cost_reduction"] == 0
    traits.response = dict.fromkeys(ERRORS, 0.5)
    assert oracle_trial(traits, costs, "ucb", 10, 0.8, 1)["true_error_cost_reduction"] > 0
    assert oracle_trial(traits, costs, "none", 10, 0.8, 1)["true_error_cost_reduction"] == 0


def test_episode_checkpoint_reuses_complete_work_and_resumes_rng(case, tmp_path):
    traits = VirtualTraits.sample(random.Random(7))
    experiment = Experiment(case, "candidate", tmp_path, {"seed": 7})
    complete = experiment.episode("one", traits, 3, None, 7)
    assert experiment.episode("one", traits, 3, None, 7) == complete
    path = tmp_path / "raw" / "two.json"
    prefix = complete.model_copy(
        update={"id": "two", "status": "active", "agreement": None, "turns": complete.turns[:2]},
        deep=True,
    )
    path.write_text(
        json.dumps(
            {"complete": False, "session": prefix.model_dump(mode="json"), "schedule_violations": 0}
        )
    )
    resumed = experiment.episode("two", traits, 3, None, 7)
    assert resumed.status == complete.status
    assert resumed.agreement == complete.agreement
    assert [t.model_dump(exclude={"created_at"}) for t in resumed.turns] == [
        t.model_dump(exclude={"created_at"}) for t in complete.turns
    ]
    with pytest.raises(ValueError, match="config changed"):
        Experiment(case, "candidate", tmp_path, {"seed": 8})


def test_uncertainty_resamples_users_and_preserves_negative_outcomes():
    result = interval([-0.25] * 8)
    assert result == {"n": 8, "mean": -0.25, "ci95": [-0.25, -0.25]}


def test_parallel_users_produce_same_paired_results(case, tmp_path, monkeypatch):
    import negotrain.evaluation as evaluation

    monkeypatch.setattr(evaluation, "TRAINING_TIERS", (2,))
    monkeypatch.setattr(evaluation, "PROBE_TIERS", (3,))
    monkeypatch.setattr(evaluation, "POLICIES", ("ucb", "none"))
    tuning = {"selected": {"forgetting": 0.8, "kappa": 1}}
    summaries = []
    for workers in (1, 2):
        root = tmp_path / str(workers)
        exp = Experiment(case, "candidate", root, {"seed": 11})
        summaries.append(evaluation.grounded_training(exp, CostModel(), tuning, 2, 11, workers))
    assert summaries[0] == summaries[1]
    assert (tmp_path / "1" / "training_rows.json").read_text() == (
        tmp_path / "2" / "training_rows.json"
    ).read_text()


def test_calibration_matches_exact_case_and_initializes_fact_beliefs(case, tmp_path):
    import hashlib

    from negotrain.profiling.observations import case_facts
    from negotrain.profiling.profile import CaseCalibration, build_profile, load_calibration

    calibration = CaseCalibration(
        case_sha256=hashlib.sha256(case.model_dump_json().encode()).hexdigest(),
        role="candidate",
        costs=CostModel(population={"error:1": 0.2}),
        forgetting=0.5,
        kappa=0,
        source="independent calibration",
    )
    (tmp_path / "calibration.json").write_text(calibration.model_dump_json())
    loaded = load_calibration(case, "candidate", tmp_path)
    profile = build_profile("a", [], context=(case, "candidate"), calibration=loaded)
    assert profile.belief.forgetting == 0.5
    assert profile.planning_kappa == 0
    assert profile.costs.weight("error:1") == 0.2
    assert all(f.id in profile.belief.components for f in case_facts(case, "candidate"))
    assert load_calibration(case, "recruiter", tmp_path) is None
    altered = case.model_copy(deep=True)
    altered.role("candidate").reservation_value += 1
    assert load_calibration(altered, "candidate", tmp_path) is None
    with pytest.raises(ValueError, match="does not match"):
        build_profile("a", [], context=(altered, "candidate"), calibration=loaded)
