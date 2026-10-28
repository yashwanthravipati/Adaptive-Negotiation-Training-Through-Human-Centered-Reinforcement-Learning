"""Post-session credit in units of R, with separate selection and scoring batches.

The fixed rollout user is ScriptedUser, with the prefix-derived concession pace and
seeded ±2.5% aspiration noise. Full transcript prefixes, setting, tags, deadline and
counterpart seed are restored. Every rollout continues to agreement or the deadline
against the selected counterpart; no standing-offer credit or cheaper tail policy.
"""

from __future__ import annotations

import random
import statistics
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel

from negotrain.cases.offers import (
    best_joint_offer,
    best_offer_for,
    best_points,
    closest_offer,
    complete_with,
    points,
)
from negotrain.cases.scoring import score_offer
from negotrain.counterpart.rule_based import Counterpart
from negotrain.feedback.critical import CriticalTurn, critical_turns
from negotrain.profiling.features import extract_features
from negotrain.schemas import Case, Offer, Session, Turn, TurnTags
from negotrain.simulation import ScriptedUser, episode_score, run_episode

CounterpartFactory = Callable[[], Counterpart]


class Action(BaseModel):
    label: str
    text: str
    offer: Offer | None = None
    accept: bool = False
    walk_away: bool = False
    actual: bool = False
    hindsight: bool = False
    tags: TurnTags | None = None


class ActionValue(BaseModel):
    action: Action
    outcomes: list[float]
    agreements: int
    errors: int = 0

    @property
    def mean(self) -> float | None:
        return sum(self.outcomes) / len(self.outcomes) if self.outcomes else None


class TurnEstimate(BaseModel):
    turn_index: int
    kind: str
    description: str
    errors: list[str] = []
    values: list[ActionValue]  # Q estimates used only for candidate selection
    selected_index: int = 0
    scored_actual: ActionValue | None = None
    scored_selected: ActionValue | None = None
    selection_seeds: list[int] = []
    scoring_seeds: list[int] = []
    delta_interval: tuple[float, float] | None = None

    @property
    def actual(self) -> ActionValue:
        return self.scored_actual or self.values[0]

    @property
    def best_alternative(self) -> ActionValue | None:
        return self.scored_selected

    @property
    def delta(self) -> float | None:
        if self.scored_selected is None or self.scored_actual is None:
            return None
        if self.scored_selected.mean is None or self.scored_actual.mean is None:
            return None
        return self.scored_selected.mean - self.scored_actual.mean


class CounterfactualReport(BaseModel):
    session_id: str
    opponent: str
    n_rollouts: int
    estimates: list[TurnEstimate]
    seconds: float
    reward: Literal["points", "surplus_share"] = "points"  # old artifacts used raw points
    rollout_policy: str = "scripted-prefix-pace; seeded aspiration noise +/-0.025 own span"
    skipped_reason: str | None = None


def estimate_calls(n_turns: int, k: int, n: int, remaining_user_turns: int = 20) -> int:
    """Worst-case calls: actual+k selection candidates, then two fresh scoring batches."""
    return n_turns * (k + 3) * n * (remaining_user_turns + 1)


def _actual_action(turn: Turn) -> Action:
    return Action(
        label="What you did",
        text=turn.text,
        offer=turn.offer,
        accept=turn.accept,
        walk_away=turn.walk_away,
        actual=True,
        tags=turn.tags,
    )


def alternatives(session: Session, case: Case, turn_index: int, k: int = 3) -> list[Action]:
    """Up to ``k`` plausible alternatives to the user's action at ``turn_index``.

    Built in code from the user's own point table, so they are concrete offers rather than
    advice. "Trade across issues" uses both sheets: it is hindsight, shown only after the
    session when the other sheet is revealed anyway.
    """
    if session.has_custom_terms:
        return []
    me = session.user_role_id
    turn = session.turns[turn_index]
    prefix = session.turns[:turn_index]
    rv = case.role(me).reservation_value
    span = max(1.0, best_points(case, me) - rv)
    theirs = next(
        (t.offer for t in reversed(prefix) if t.speaker == "counterpart" and t.offer), None
    )
    mine_before = next((t.offer for t in reversed(prefix) if t.speaker == "user" and t.offer), None)
    reference = turn.offer or (theirs if turn.accept else None) or mine_before
    ref = complete_with(case, reference, theirs or best_offer_for(case, me))
    ref_pts = points(case, me, ref)

    out: list[Action] = []

    def add(label: str, text: str, offer: Offer | None, **flags: bool) -> None:
        if offer is None and not flags.pop("no_offer", False) and not flags.get("accept"):
            return  # no offer satisfies this alternative (e.g. already at the maximum)
        if offer is not None and turn.offer is not None and offer == turn.offer:
            return
        if any(a.offer == offer and offer is not None for a in out):
            return
        out.append(Action(label=label, text=text, offer=offer, **flags))

    if turn.walk_away:
        if theirs is not None and theirs.is_complete(case):
            surplus = score_offer(case, me, theirs).surplus
            if surplus is not None and surplus >= 0:
                add("Accept their last offer", "Okay, we have a deal.", None, accept=True)
        add(
            "Make a final offer instead",
            "This is my final offer.",
            closest_offer(case, me, rv + 0.15 * span, theirs),
        )
    else:
        add(
            "Firmer offer",
            "Here's what I'd need to make this work.",
            closest_offer(case, me, ref_pts + 0.15 * span, ref),
        )
        add(
            "Trade across issues",
            "What if we trade: I give ground where it matters to you, you give where it "
            "matters to me?",
            best_joint_offer(case, me, ref_pts),
            hindsight=True,
        )
        if turn.accept:
            add(
                "Counter instead of accepting",
                "We're close. Could you do this instead?",
                closest_offer(case, me, ref_pts + 0.08 * span, ref),
            )
        else:
            add(
                "Softer offer",
                "Let me meet you partway.",
                closest_offer(case, me, max(rv, ref_pts - 0.15 * span), theirs or ref),
            )
            if turn.offer is not None:
                add(
                    "Ask before offering",
                    "Before I put numbers down, what matters most to you here?",
                    None,
                    no_offer=True,
                )
    return out[:k]


def _fork(session: Session, case: Case, turn_index: int) -> Session:
    fork = session.model_copy(
        update={"turns": [], "status": "active", "agreement": None}, deep=True
    )
    for t in session.turns[:turn_index]:
        fork.add_turn(t.model_copy(), case)
    return fork


def _user_step(session: Session, case: Case) -> float:
    step = extract_features(session, case)["mean_concession"]
    return min(0.25, max(0.03, step)) if step else 0.08


def rollout(
    session: Session,
    case: Case,
    turn_index: int,
    action: Action,
    make_counterpart: CounterpartFactory,
    *,
    step: float,
    seed: int,
) -> tuple[float, bool]:
    """Play ``action`` at ``turn_index`` and continue; returns (terminal R, agreed)."""
    if session.has_custom_terms or (action.offer is not None and action.offer.custom_terms):
        raise ValueError("numeric rollouts cannot value custom terms")
    fork = _fork(session, case, turn_index)
    fork.add_turn(
        Turn(
            index=turn_index,
            speaker="user",
            text=action.text,
            offer=action.offer,
            accept=action.accept,
            walk_away=action.walk_away,
            tags=action.tags,
        ),
        case,
    )
    me = session.user_role_id
    start = None
    latest = fork.latest_offer_from("user")
    if latest is not None and latest.is_complete(case):
        start = points(case, me, latest)
    user = ScriptedUser(case, me, step=step, start_points=start, rng=random.Random(seed))
    user.turns_taken = 1
    run_episode(
        case,
        fork,
        make_counterpart(),
        user,
        max_turns=2 * (fork.max_user_turns - fork.user_turns) + 2,
    )
    if fork.status == "active":
        fork.status = "impasse"
    value = episode_score(case, fork)
    if value is None:
        raise ValueError("rollout produced an unscored custom agreement")
    return value, fork.status == "agreed"


def estimate_turn_values(
    session: Session,
    case: Case,
    critical: CriticalTurn,
    make_counterpart: CounterpartFactory,
    *,
    k: int = 2,
    n: int = 4,
    executor: ThreadPoolExecutor | None = None,
) -> TurnEstimate:
    if n < 1:
        raise ValueError("n must be positive")
    actions = [_actual_action(session.turns[critical.turn_index])]
    actions += alternatives(session, case, critical.turn_index, k)
    prefix = _fork(session, case, critical.turn_index)
    step = _user_step(prefix, case)  # never fit a rollout user on future transcript turns
    rng = random.Random(session.seed + 104729 * (critical.turn_index + 1))
    seeds = rng.sample(range(2**31), 2 * n)
    selection, scoring = seeds[:n], seeds[n:]

    def batch(action: Action, batch_seeds: list[int]) -> ActionValue:
        def run(seed: int) -> tuple[float, bool]:
            # Failed rollouts fail the estimate: silently dropping them biases Q.
            return rollout(
                session, case, critical.turn_index, action, make_counterpart, step=step, seed=seed
            )

        results = (
            list(executor.map(run, batch_seeds)) if executor else [run(s) for s in batch_seeds]
        )
        return ActionValue(
            action=action,
            outcomes=[v for v, _ in results],
            agreements=sum(agreed for _, agreed in results),
        )

    values = [batch(a, selection) for a in actions]
    selected = max(range(len(values)), key=lambda i: values[i].mean)
    actual = batch(actions[0], scoring)
    best = batch(actions[selected], scoring)
    differences = [b - a for a, b in zip(actual.outcomes, best.outcomes, strict=True)]
    interval = None
    if n >= 2:
        # Paired bootstrap with common random numbers within each fresh batch.
        bootstrap_rng = random.Random(seeds[-1])
        samples = sorted(
            statistics.mean(bootstrap_rng.choices(differences, k=n)) for _ in range(2000)
        )
        interval = (samples[49], samples[1949])
    return TurnEstimate(
        turn_index=critical.turn_index,
        kind=critical.kind,
        description=critical.description,
        errors=critical.errors,
        values=values,
        selected_index=selected,
        scored_actual=actual,
        scored_selected=best,
        selection_seeds=selection,
        scoring_seeds=scoring,
        delta_interval=interval,
    )


def analyze_session(
    session: Session,
    case: Case,
    make_counterpart: CounterpartFactory,
    *,
    opponent: str = "llm",
    cap: int | None = None,
    k: int = 2,
    n: int = 4,
    max_workers: int = 8,
) -> CounterfactualReport:
    if session.status not in ("agreed", "impasse"):
        raise ValueError("counterfactual coaching is available only after the session")
    if session.has_custom_terms:
        return CounterfactualReport(
            session_id=session.id,
            opponent=opponent,
            n_rollouts=0,
            reward="surplus_share",
            estimates=[],
            seconds=0.0,
            skipped_reason="Point-based simulations are unavailable for custom terms. "
            "Your full proposals are included in the qualitative coaching report.",
        )
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        estimates = [
            estimate_turn_values(session, case, c, make_counterpart, k=k, n=n, executor=pool)
            for c in critical_turns(session, case, cap=cap)
        ]
    return CounterfactualReport(
        session_id=session.id,
        opponent=opponent,
        n_rollouts=n,
        reward="surplus_share",
        estimates=estimates,
        seconds=time.monotonic() - start,
    )
