"""Seeded experiments for steering, state inference, and five-session learning.

Raw case/transcript artifacts stay private. Public results contain synthetic-user parameters,
numeric metrics, configuration, and case/source hashes only.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from negotrain.cases.offers import points
from negotrain.counterpart import TIERS, CounterpartAgent, RuleBasedCounterpart
from negotrain.feedback import analyze_session, build_report
from negotrain.profiling.belief import BeliefState, BetaBelief, CostModel, choose_focus
from negotrain.profiling.observations import ERRORS, Count, Observations, case_facts, observe
from negotrain.profiling.tagging import tag_session
from negotrain.schemas import Case, Session
from negotrain.simulation import episode_score
from negotrain.virtual_users import LLMUser, VirtualTraits, VirtualUser

POLICIES = ("ucb", "greedy", "random", "none")
TRAINING_TIERS = (2, 2, 4, 4, 4)
PROBE_TIERS = (1, 3, 5)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False))
    temporary.replace(path)


def interval(values, seed=1) -> dict:
    values = np.asarray(values, dtype=float)
    if not len(values):
        return {"n": 0, "mean": None, "ci95": None}
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(2000, len(values)), replace=True).mean(axis=1)
    return {
        "n": len(values),
        "mean": float(values.mean()),
        "ci95": np.quantile(means, [0.025, 0.975]).tolist(),
    }


def correlation(x, y) -> float | None:
    if len(x) < 3 or len(set(x)) < 2 or len(set(y)) < 2:
        return None
    return float(spearmanr(x, y).statistic)


def initial_belief(case, role, forgetting=0.8, discount_prior=False):
    keys = [*ERRORS, *(f.id for f in case_facts(case, role)), "rapport"]
    return BeliefState(
        components={key: BetaBelief() for key in keys},
        forgetting=forgetting,
        discount_prior=discount_prior,
    )


class Experiment:
    def __init__(
        self, case: Case, role: str, root: Path, config: dict, counterpart_llm=None, user_llm=None
    ):
        self.case, self.role, self.root = case, role, root
        self.counterpart_llm, self.user_llm = counterpart_llm, user_llm
        self.raw = root / "raw"
        self.raw.mkdir(parents=True, exist_ok=True)
        config = {
            **config,
            "case_sha256": hashlib.sha256(case.model_dump_json().encode()).hexdigest(),
            "role": role,
            "training_tiers": TRAINING_TIERS,
            "probe_tiers": PROBE_TIERS,
            "K": 5,
            "reward": "surplus_share",
            "scoring": "inferred sim3 utilities",
        }
        # JSON normalizes tuples so resumed runs compare exactly.
        config = json.loads(json.dumps(config))
        path = root / "config.json"
        if path.exists() and json.loads(path.read_text()) != config:
            raise ValueError("experiment config changed; use a new output directory")
        write_json(path, config)

    def episode(
        self,
        key: str,
        traits: VirtualTraits,
        tier: int,
        focus: str | None,
        seed: int,
        feedback: list[str] | None = None,
    ) -> Session:
        path = self.raw / f"{key}.json"
        saved = None
        if path.exists():
            record = json.loads(path.read_text())
            if record["complete"]:
                return Session.model_validate(record["session"])
            saved = record
        profile = TIERS[tier].model_copy(update={"focus": focus})
        s = Session(
            id=key,
            participant_id=key.split("_")[0],
            case_id=self.case.id,
            user_role_id=self.role,
            counterpart_role_id=self.case.other_role(self.role).id,
            counterpart_profile=profile,
            seed=seed,
        )
        if self.user_llm:
            user = LLMUser(self.case, self.role, traits, self.user_llm, feedback)
        else:
            user = VirtualUser(self.case, self.role, traits, seed + 17)
        if saved:
            restored = Session.model_validate(saved["session"])
            if self.user_llm is None:
                # Reconstruct the scripted RNG and concession memory from visible history.
                for turn in restored.turns:
                    if turn.speaker == "user":
                        user.respond(s)
                    s.add_turn(turn, self.case)
            else:
                s = restored
        bot = (
            CounterpartAgent(self.case, s.counterpart_role_id, profile, self.counterpart_llm)
            if self.counterpart_llm
            else RuleBasedCounterpart(self.case, s.counterpart_role_id, profile)
        )
        guards = RuleBasedCounterpart(self.case, s.counterpart_role_id, profile)
        violations = saved["schedule_violations"] if saved else 0
        user_next = (
            s.turns[-1].speaker == "counterpart"
            if s.turns
            else focus != "error:3" and random.Random(seed).random() < 0.5
        )
        while s.status == "active":
            if user_next:
                turn = user.respond(s)
            else:
                if self.user_llm and focus == "rapport" and s.turns:
                    tag_session(s, self.case, self.user_llm)
                minimum = guards.minimum(s)
                turn = bot.respond(s)
                package = turn.offer or (s.latest_offer_from("user") if turn.accept else None)
                if package and not package.custom_terms:
                    violations += points(self.case, s.counterpart_role_id, package) < minimum
            s.add_turn(turn, self.case)
            write_json(
                path,
                {
                    "complete": False,  # final annotations must be durable too
                    "session": s.model_dump(mode="json"),
                    "schedule_violations": violations,
                },
            )
            user_next = not user_next
        if self.user_llm:
            tag_session(s, self.case, self.user_llm)
        write_json(
            path,
            {
                "complete": True,
                "session": s.model_dump(mode="json"),
                "schedule_violations": violations,
            },
        )
        return s

    def feedback(self, session: Session, *, cap: int | None = 3, n: int = 4):
        from negotrain.feedback.coaching import Debrief

        path = self.raw / f"{session.id}.feedback.json"
        if path.exists():
            return Debrief.model_validate_json(path.read_text())
        profile = session.counterpart_profile

        # Economic policy is identical to the hybrid controller. This explicitly uses
        # scripted continuation, rather than claiming to predict this particular LLM user.
        def factory():
            return RuleBasedCounterpart(self.case, session.counterpart_role_id, profile)

        credit = analyze_session(
            session, self.case, factory, opponent="rule-based", cap=cap, n=n, max_workers=1
        )
        report = build_report(session, self.case, credit, self.counterpart_llm)
        artifact = Debrief(counterfactuals=credit, report=report)
        write_json(path, artifact.model_dump(mode="json"))
        return artifact

    def probe(self, key, traits, seed, feedback=None):
        sessions = [
            self.episode(f"{key}_t{tier}", traits, tier, None, seed + tier, feedback)
            for tier in PROBE_TIERS
        ]
        return float(np.mean([episode_score(self.case, s) for s in sessions]))


def metrics(session, case):
    observation = observe(session, case)
    cp = [t for t in session.turns if t.speaker == "counterpart" and t.offer]
    applied = [t.hook_applied for t in session.turns if t.hook_applied is not None]
    return {
        "R": episode_score(case, session),
        "agreement": session.status == "agreed",
        "user_turns": session.user_turns,
        "hook_applied": sum(applied),
        "hook_attempts": len(applied),
        "counterpart_points": [points(case, session.counterpart_role_id, t.offer) for t in cp],
        "counts": {
            k: {"o": c.opportunities, "x": c.occurrences} for k, c in observation.counts.items()
        },
    }


def steering(experiment: Experiment, users: int, seed: int):
    rng = random.Random(seed)
    records = []
    keys = list(initial_belief(experiment.case, experiment.role).components)
    for uid in range(users):
        traits = VirtualTraits.sample(rng)
        common_seed = seed + uid * 1009
        for tier in range(1, 6):
            s = experiment.episode(f"steer{uid}_tier{tier}", traits, tier, None, common_seed)
            records.append(
                {"user": uid, "tier": tier, "focus": None, **metrics(s, experiment.case)}
            )
        for j, focus in enumerate(keys):
            s = experiment.episode(f"steer{uid}_focus{j}", traits, 3, focus, common_seed)
            records.append({"user": uid, "tier": 3, "focus": focus, **metrics(s, experiment.case)})
        if uid % 4 == 0:
            print(f"steering {uid + 1}/{users}", flush=True)
    tiers = {
        str(t): {
            "R": interval([r["R"] for r in records if r["tier"] == t and r["focus"] is None]),
            "agreement_rate": float(
                np.mean([r["agreement"] for r in records if r["tier"] == t and r["focus"] is None])
            ),
        }
        for t in range(1, 6)
    }
    baseline = {r["user"]: r for r in records if r["tier"] == 3 and r["focus"] is None}
    effects = {}
    for key in keys:
        subset = [r for r in records if r["focus"] == key]
        effects[key] = {
            "opportunity_difference": interval(
                [r["counts"][key]["o"] - baseline[r["user"]]["counts"][key]["o"] for r in subset]
            ),
            "mean_focused_opportunities": float(np.mean([r["counts"][key]["o"] for r in subset])),
            "hook_application_rate": (
                sum(r["hook_applied"] for r in subset)
                / max(1, sum(r["hook_attempts"] for r in subset))
            ),
        }
    summary = {
        "tiers": tiers,
        "focus_effects": effects,
        "tier_R_spearman": correlation(
            list(range(1, 6)), [tiers[str(t)]["R"]["mean"] for t in range(1, 6)]
        ),
    }
    write_json(experiment.root / "steering_rows.json", records)
    write_json(experiment.root / "steering.json", summary)
    return summary


def failure_turns(session, observation, key):
    count = observation.counts[key]
    if key in ERRORS:
        return set(count.turns)
    eligible = {t.index for t in session.turns if t.speaker == "user" and t.tags is not None}
    if key.endswith(":walkaway"):
        eligible = {t.index for t in session.turns if t.speaker == "user" and (t.offer or t.accept)}
    return eligible - set(count.turns)


def calibrate(experiment: Experiment, users: int, seed: int):
    rng = random.Random(seed)
    keys = list(initial_belief(experiment.case, experiment.role).components)
    sums, counts = dict.fromkeys(keys, 0.0), dict.fromkeys(keys, 0)
    opportunities = {key: [] for key in keys}
    for uid in range(users):
        traits = VirtualTraits.sample(rng)
        for j, focus in enumerate(keys):
            session = experiment.episode(
                f"calib{uid}_f{j}", traits, 3, focus, seed + 1009 * uid + j
            )
            obs = observe(session, experiment.case)
            opportunities[focus].append(obs.counts[focus].opportunities)
            debrief = experiment.feedback(session, cap=3)
            for estimate in debrief.counterfactuals.estimates:
                for key in keys:
                    if estimate.delta is not None and estimate.turn_index in failure_turns(
                        session, obs, key
                    ):
                        sums[key] += estimate.delta
                        counts[key] += 1
        print(f"cost calibration {uid + 1}/{users}", flush=True)
    costs = CostModel(
        population={k: sums[k] / counts[k] if counts[k] else 0.0 for k in keys},
        opportunities={k: float(np.mean(opportunities[k])) for k in keys},
    )
    write_json(experiment.root / "costs.json", costs.model_dump())
    write_json(
        experiment.root / "cost_calibration.json",
        {
            "credit_occurrences": counts,
            "missing_costs": [k for k in keys if not counts[k]],
            "users": users,
            "M": 4,
            "critical_turn_cap": 3,
            "population": "independent calibration users",
        },
    )
    return costs


def oracle_trial(traits, costs, policy, seed, forgetting, kappa, discount_prior=False):
    """Exact specification-only Binomial experiment; never presented as a transcript run."""
    rng = np.random.default_rng(seed)
    planner_rng = random.Random(seed)
    state = traits.model_copy(deep=True)
    belief = BeliefState(
        components={k: BetaBelief() for k in ERRORS},
        forgetting=forgetting,
        discount_prior=discount_prior,
    )
    start = dict(state.errors)
    mastered = 0 if max(start.values()) < 0.25 else 6
    coverage, squared_error = [], []
    for t in range(5):
        focus = choose_focus(belief, costs, policy=policy, kappa=kappa, rng=planner_rng)
        counts = {}
        for key in ERRORS:
            o = int(rng.poisson(costs.opportunities.get(key, 1)))
            x = int(rng.binomial(o, state.errors[key]))
            counts[key] = Count(opportunities=o, occurrences=x)
        belief.update(Observations(counts=counts, score=None))
        for key, b in belief.components.items():
            lo, hi = b.interval()
            coverage.append(lo <= state.errors[key] <= hi)
            squared_error.append((b.mean - state.errors[key]) ** 2)
        state.learn(focus)
        if mastered == 6 and max(state.errors.values()) < 0.25:
            mastered = t + 1
    reward = sum(costs.cost(k) * (start[k] - state.errors[k]) for k in ERRORS)
    return {
        "true_error_cost_reduction": reward,
        "sessions_to_threshold_censored": mastered,
        "mastered": mastered <= 5,
        "posterior_mse": float(np.mean(squared_error)),
        "posterior_coverage": float(np.mean(coverage)),
    }


def tune_oracle(costs, seed, users=128):
    rng = random.Random(seed)
    traits = [VirtualTraits.sample(rng) for _ in range(users)]
    rows = []
    for forgetting in (0.5, 0.8, 1.0):
        for kappa in (0.0, 0.5, 1.0, 2.0):
            trials = [
                oracle_trial(u, costs, "ucb", seed + i, forgetting, kappa)
                for i, u in enumerate(traits)
            ]
            rows.append(
                {
                    "forgetting": forgetting,
                    "kappa": kappa,
                    "reward": float(np.mean([r["true_error_cost_reduction"] for r in trials])),
                    "mse": float(np.mean([r["posterior_mse"] for r in trials])),
                }
            )
    # Joint choices made on development users only. The held-out test population is new.
    best = max(rows, key=lambda r: (r["reward"], -r["mse"]))
    return {"selected": best, "grid": rows, "users": users, "seed": seed}


def oracle_evaluate(costs, tuning, users, seed):
    rng = random.Random(seed)
    chosen = tuning["selected"]
    rows = []
    for uid in range(users):
        traits = VirtualTraits.sample(rng)
        for policy in POLICIES:
            for discount_prior in (False, True):
                trial = oracle_trial(
                    traits,
                    costs,
                    policy,
                    seed + uid,
                    chosen["forgetting"],
                    chosen["kappa"],
                    discount_prior,
                )
                rows.append(
                    {"user": uid, "policy": policy, "discount_prior": discount_prior, **trial}
                )
    summary = {}
    for policy in POLICIES:
        for mode in (False, True):
            selected = [r for r in rows if r["policy"] == policy and r["discount_prior"] == mode]
            summary[f"{policy}:discount_prior={mode}"] = {
                metric: interval([r[metric] for r in selected])
                for metric in (
                    "true_error_cost_reduction",
                    "sessions_to_threshold_censored",
                    "mastered",
                    "posterior_mse",
                    "posterior_coverage",
                )
            }
    return rows, summary


def grounded_training(experiment, costs, tuning, users, seed):
    rng = random.Random(seed)
    rows = []
    for uid in range(users):
        original = VirtualTraits.sample(rng)
        baseline = experiment.probe(f"user{uid}_baseline", original, seed + 1009 * uid)
        for policy in POLICIES:
            traits = original.model_copy(deep=True)
            personal = costs.model_copy(deep=True)
            belief = initial_belief(
                experiment.case, experiment.role, tuning["selected"]["forgetting"]
            )
            feedback = []
            focuses = []
            for t, tier in enumerate(TRAINING_TIERS):
                focus = choose_focus(
                    belief,
                    personal,
                    policy=policy,
                    kappa=tuning["selected"]["kappa"],
                    rng=random.Random(seed + uid * 1009 + t),
                )
                focuses.append(focus)
                s = experiment.episode(
                    f"user{uid}_{policy}_train{t}",
                    traits,
                    tier,
                    focus,
                    seed + uid * 1009 + t,
                    feedback,
                )
                obs = observe(s, experiment.case)
                debrief = experiment.feedback(s)
                feedback.append(debrief.report.model_dump_json())
                for e in debrief.counterfactuals.estimates:
                    for key in belief.components:
                        if e.delta is not None and e.turn_index in failure_turns(s, obs, key):
                            personal.add(key, e.delta)
                belief.update(obs)
                if experiment.user_llm is None:
                    traits.learn(focus)
            after = experiment.probe(
                f"user{uid}_{policy}_after", traits, seed + uid * 1009, feedback
            )
            rows.append(
                {
                    "user": uid,
                    "policy": policy,
                    "baseline_G": baseline,
                    "final_G": after,
                    "competence_gain": after - baseline,
                    "focuses": focuses,
                    "initial_traits": original.model_dump(),
                    "population": "LLM persona" if experiment.user_llm else "grounded scripted",
                }
            )
            write_json(experiment.root / "training_rows.json", rows)
        print(f"training user {uid + 1}/{users}", flush=True)
    by_policy = {p: [r for r in rows if r["policy"] == p] for p in POLICIES}
    summary = {
        p: {
            key: interval([r[key] for r in data])
            for key in ("baseline_G", "final_G", "competence_gain")
        }
        for p, data in by_policy.items()
    }
    for p in POLICIES[1:]:
        summary["ucb_minus_" + p] = interval(
            [
                a["competence_gain"] - b["competence_gain"]
                for a, b in zip(by_policy["ucb"], by_policy[p], strict=True)
            ]
        )
    write_json(experiment.root / "training.json", summary)
    return summary


def recovery(experiment, users, seed, forgetting=0.8, reference_sessions=30):
    rng = random.Random(seed)
    rows = []
    for uid in range(users):
        traits = VirtualTraits.sample(rng)
        b = initial_belief(experiment.case, experiment.role, forgetting)
        train_counts = {k: [0, 0] for k in ERRORS}
        for t in range(5):
            s = experiment.episode(f"recover{uid}_train{t}", traits, 3, None, seed + uid * 1009 + t)
            obs = observe(s, experiment.case)
            b.update(obs)
            for k in ERRORS:
                train_counts[k][0] += obs.counts[k].occurrences
                train_counts[k][1] += obs.counts[k].opportunities
        reference = {k: [0, 0] for k in ERRORS}
        for t in range(reference_sessions):
            s = experiment.episode(
                f"recover{uid}_reference{t}", traits, 3, None, seed + uid * 1009 + 100 + t
            )
            obs = observe(s, experiment.case)
            for k in ERRORS:
                reference[k][0] += obs.counts[k].occurrences
                reference[k][1] += obs.counts[k].opportunities
        for k in ERRORS:
            x, o = reference[k]
            actual = x / o if o else None
            lo, hi = b.components[k].interval()
            rows.append(
                {
                    "user": uid,
                    "error": k,
                    "policy_propensity": traits.errors[k],
                    "reference_rate": actual,
                    "reference_opportunities": o,
                    "posterior_mean": b.components[k].mean,
                    "ci95": [lo, hi],
                    "covered_reference": lo <= actual <= hi if actual is not None else None,
                }
            )
        if uid % 8 == 0:
            print(f"recovery {uid + 1}/{users}", flush=True)
    summary = {}
    for key in ERRORS:
        data = [r for r in rows if r["error"] == key and r["reference_rate"] is not None]
        summary[key] = {
            "users_with_reference_opportunities": len(data),
            "rmse_vs_reference": float(
                np.sqrt(np.mean([(r["posterior_mean"] - r["reference_rate"]) ** 2 for r in data]))
            )
            if data
            else None,
            "coverage_of_mc_reference": float(np.mean([r["covered_reference"] for r in data]))
            if data
            else None,
            "propensity_vs_realized_spearman": correlation(
                [r["policy_propensity"] for r in data], [r["reference_rate"] for r in data]
            ),
        }
    write_json(experiment.root / "recovery_rows.json", rows)
    write_json(experiment.root / "recovery.json", summary)
    return summary
