"""Negotiator profile (T-025): per-skill scores across sessions, with uncertainty.

Each skill maps a session's features to a score in [0, 1]. Scores are averaged and shrunk
toward a neutral prior (0.5) with weight ``PRIOR_WEIGHT`` sessions, so one lucky or unlucky
session does not define a person; ``confidence`` grows with the number of observations.
Rebuilt from all sessions each time (idempotent) rather than updated incrementally.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

from pydantic import BaseModel

from negotrain.profiling.features import Features, extract_features, flags
from negotrain.schemas import Case, Session

PRIOR = 0.5
PRIOR_WEIGHT = 2.0


def _clip(x: float) -> float:
    return min(1.0, max(0.0, x))


def _concession_discipline(f: Features) -> float | None:
    if not f["n_offers"]:
        return None
    early = f["early_concession"] or 0.0
    step = f["mean_concession"] or 0.0
    return 0.5 * (1 - early) + 0.5 * _clip(1 - 3 * step)


SKILLS: dict[str, tuple[str, str, Callable[[Features], float | None]]] = {
    "anchoring": (
        "Anchoring",
        "How ambitious and well-placed your first offer is",
        lambda f: f["first_offer_claim"],
    ),
    "concession_discipline": (
        "Concession discipline",
        "Conceding slowly, in small steps, and in exchange for something",
        _concession_discipline,
    ),
    "information_gathering": (
        "Information gathering",
        "Asking questions to learn the other side's priorities",
        lambda f: None if f["question_rate"] is None else _clip(2 * f["question_rate"]),
    ),
    "value_creation": (
        "Value creation",
        "Trading across issues to grow the joint outcome",
        lambda f: f["efficiency"],
    ),
    "value_claiming": (
        "Value claiming",
        "Capturing surplus over your walk-away value",
        lambda f: None if f["surplus_share"] is None else _clip(f["surplus_share"]),
    ),
    "closing": (
        "Closing",
        "Reaching agreement when a good deal is available",
        lambda f: f["agreement"],
    ),
}


class SkillEstimate(BaseModel):
    skill: str
    label: str
    description: str
    score: float  # shrunk mean in [0, 1]
    raw_mean: float | None
    n: int
    confidence: float  # n / (n + PRIOR_WEIGHT)


class NegotiatorProfile(BaseModel):
    participant_id: str
    n_sessions: int
    skills: list[SkillEstimate]
    strengths: list[str]
    weaknesses: list[str]  # skill keys, weakest first
    flag_counts: dict[str, int]

    def skill(self, key: str) -> SkillEstimate:
        return next(s for s in self.skills if s.skill == key)


def build_profile(participant_id: str, history: list[tuple[Session, Case]]) -> NegotiatorProfile:
    """Profile from finished sessions (rehearsals and logged real negotiations)."""
    finished = [(s, c) for s, c in history if s.status in ("agreed", "impasse")]
    observations: dict[str, list[float]] = {k: [] for k in SKILLS}
    flag_counts: Counter[str] = Counter()
    for session, case in finished:
        f = extract_features(session, case)
        for key, (_, _, fn) in SKILLS.items():
            value = fn(f)
            if value is not None:
                observations[key].append(value)
        flag_counts.update(flags(session, case, f))

    skills = []
    for key, (label, description, _) in SKILLS.items():
        obs = observations[key]
        n = len(obs)
        skills.append(
            SkillEstimate(
                skill=key,
                label=label,
                description=description,
                score=(sum(obs) + PRIOR * PRIOR_WEIGHT) / (n + PRIOR_WEIGHT),
                raw_mean=sum(obs) / n if n else None,
                n=n,
                confidence=n / (n + PRIOR_WEIGHT),
            )
        )
    observed = [s for s in skills if s.n]
    weaknesses = [s.skill for s in sorted(observed, key=lambda s: s.score) if s.score < 0.45]
    strengths = [s.skill for s in sorted(observed, key=lambda s: -s.score) if s.score >= 0.6]
    return NegotiatorProfile(
        participant_id=participant_id,
        n_sessions=len(finished),
        skills=skills,
        strengths=strengths,
        weaknesses=weaknesses,
        flag_counts=dict(flag_counts),
    )
