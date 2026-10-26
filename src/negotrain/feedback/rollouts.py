"""Counterfactual credit assignment (T-021).

At each critical turn, fork the transcript, try the actual action and up to K alternatives
(firmer, softer, trade across issues, ask instead of offering, ...), and play each forward N
times against the counterpart with a simulated user (simulation.ScriptedUser) whose
concession step is taken from this user's own behavior. LLM calls are capped at ``horizon``
turns per rollout; an unfinished rollout is then played to the end by the rule-based
counterpart with the same profile and schedule, which is free. The value of an action is the
user's mean points over its rollouts; the gap between the best alternative and the actual
action says how much that decision mattered. Runs after the session, never live
(decision 0002).
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

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
from negotrain.counterpart.profiles import TIERS
from negotrain.counterpart.rule_based import Counterpart, RuleBasedCounterpart
from negotrain.feedback.critical import CriticalTurn, critical_turns
from negotrain.profiling.features import extract_features
from negotrain.schemas import Case, Offer, Session, Turn
from negotrain.simulation import ScriptedUser, episode_value, run_episode

CounterpartFactory = Callable[[], Counterpart]
FINISH_TURNS = 40


class Action(BaseModel):
    label: str
    text: str
    offer: Offer | None = None
    accept: bool = False
    walk_away: bool = False
    actual: bool = False


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
    values: list[ActionValue]  # values[0] is the actual action

    @property
    def actual(self) -> ActionValue:
        return self.values[0]

    @property
    def best_alternative(self) -> ActionValue | None:
        alts = [v for v in self.values[1:] if v.mean is not None]
        return max(alts, key=lambda v: v.mean) if alts else None

    @property
    def delta(self) -> float | None:
        """Best alternative minus actual, in the user's points (positive = room to improve)."""
        best = self.best_alternative
        if best is None or self.actual.mean is None:
            return None
        return best.mean - self.actual.mean


class CounterfactualReport(BaseModel):
    session_id: str
    opponent: str
    n_rollouts: int
    horizon: int
    estimates: list[TurnEstimate]
    seconds: float


def estimate_calls(n_turns: int, k: int, n: int, horizon: int) -> int:
    """Upper-ish bound on counterpart LLM calls for an analysis (retries excluded)."""
    return n_turns * (k + 1) * n * math.ceil(horizon / 2)


def _actual_action(turn: Turn) -> Action:
    return Action(
        label="What you did",
        text=turn.text,
        offer=turn.offer,
        accept=turn.accept,
        walk_away=turn.walk_away,
        actual=True,
    )


def alternatives(session: Session, case: Case, turn_index: int, k: int = 3) -> list[Action]:
    """Up to ``k`` plausible alternatives to the user's action at ``turn_index``.

    Built in code from the user's own point table, so they are concrete offers rather than
    advice. "Trade across issues" uses both sheets: it is hindsight, shown only after the
    session when the other sheet is revealed anyway.
    """
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
            if score_offer(case, me, theirs).surplus >= 0:
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
    horizon: int,
    step: float,
) -> tuple[float, bool]:
    """Play ``action`` at ``turn_index`` and continue; returns (user points, agreed)."""
    fork = _fork(session, case, turn_index)
    fork.add_turn(
        Turn(
            index=turn_index,
            speaker="user",
            text=action.text,
            offer=action.offer,
            accept=action.accept,
            walk_away=action.walk_away,
        ),
        case,
    )
    me = session.user_role_id
    start = None
    latest = fork.latest_offer_from("user")
    if latest is not None and latest.is_complete(case):
        start = points(case, me, latest)
    user = ScriptedUser(case, me, step=step, start_points=start)
    user.turns_taken = 1  # it has just made its move at `start`
    run_episode(case, fork, make_counterpart(), user, max_turns=horizon)
    if fork.status == "active":
        profile = session.counterpart_profile or TIERS[3]
        finisher = RuleBasedCounterpart(case, session.counterpart_role_id, profile)
        run_episode(case, fork, finisher, user, max_turns=FINISH_TURNS)
    return episode_value(case, fork), fork.status == "agreed"


def estimate_turn_values(
    session: Session,
    case: Case,
    critical: CriticalTurn,
    make_counterpart: CounterpartFactory,
    *,
    k: int = 2,
    n: int = 2,
    horizon: int = 4,
    executor: ThreadPoolExecutor | None = None,
) -> TurnEstimate:
    actions = [_actual_action(session.turns[critical.turn_index])]
    actions += alternatives(session, case, critical.turn_index, k)
    step = _user_step(session, case)

    def run(action: Action) -> tuple[float, bool] | None:
        try:
            return rollout(
                session,
                case,
                critical.turn_index,
                action,
                make_counterpart,
                horizon=horizon,
                step=step,
            )
        except Exception:  # noqa: BLE001 - one failed rollout (refusal, API error) shouldn't sink the report
            return None

    jobs = [(a, i) for a in actions for i in range(n)]
    results = (
        list(executor.map(lambda job: run(job[0]), jobs)) if executor else [run(a) for a, _ in jobs]
    )
    values = []
    for a in actions:
        mine = [r for (b, _), r in zip(jobs, results, strict=False) if b is a]
        ok = [r for r in mine if r is not None]
        values.append(
            ActionValue(
                action=a,
                outcomes=[v for v, _ in ok],
                agreements=sum(1 for _, agreed in ok if agreed),
                errors=len(mine) - len(ok),
            )
        )
    return TurnEstimate(
        turn_index=critical.turn_index,
        kind=critical.kind,
        description=critical.description,
        values=values,
    )


def analyze_session(
    session: Session,
    case: Case,
    make_counterpart: CounterpartFactory,
    *,
    opponent: str = "llm",
    cap: int = 3,
    k: int = 2,
    n: int = 2,
    horizon: int = 4,
    max_workers: int = 8,
) -> CounterfactualReport:
    start = time.monotonic()
    turns = critical_turns(session, case, cap=cap)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        estimates = [
            estimate_turn_values(
                session, case, c, make_counterpart, k=k, n=n, horizon=horizon, executor=pool
            )
            for c in turns
        ]
    return CounterfactualReport(
        session_id=session.id,
        opponent=opponent,
        n_rollouts=n,
        horizon=horizon,
        estimates=estimates,
        seconds=time.monotonic() - start,
    )
