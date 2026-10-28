"""Counterpart behavioral profiles, curriculum tiers, and profile sampling.

Tiers run from transparent/cooperative (1) to hardball (5). ``sample_profile`` perturbs a
tier's preset so a user rehearses against a spread of plausible opponents rather than one
fixed guess (domain randomization). ``describe`` turns dials into prompt instructions; how
well those instructions actually control behavior is the ML-Q1 experiment (T-012, T-017).
"""

from __future__ import annotations

import random

from negotrain.schemas import CounterpartProfile

DIALS = (
    "cooperativeness",
    "aggression",
    "anchoring",
    "concession_rate",
    "disclosure",
    "bluffing",
    "concession_floor",
)

TIERS: dict[int, CounterpartProfile] = {
    1: CounterpartProfile(
        name="transparent-cooperative",
        tier=1,
        cooperativeness=0.9,
        aggression=0.1,
        anchoring=0.65,
        concession_rate=0.08,
        concession_floor=0.0,
        disclosure=0.9,
        bluffing=0.0,
    ),
    2: CounterpartProfile(
        name="collaborative-but-firm",
        tier=2,
        cooperativeness=0.7,
        aggression=0.2,
        anchoring=0.75,
        concession_rate=0.065,
        concession_floor=0.025,
        disclosure=0.6,
        bluffing=0.1,
    ),
    3: CounterpartProfile(
        name="guarded-realist",
        tier=3,
        cooperativeness=0.5,
        aggression=0.4,
        anchoring=0.85,
        concession_rate=0.05,
        concession_floor=0.05,
        disclosure=0.4,
        bluffing=0.3,
    ),
    4: CounterpartProfile(
        name="tough-anchorer",
        tier=4,
        cooperativeness=0.3,
        aggression=0.6,
        anchoring=0.93,
        concession_rate=0.035,
        concession_floor=0.075,
        disclosure=0.2,
        bluffing=0.5,
    ),
    5: CounterpartProfile(
        name="hardball",
        tier=5,
        cooperativeness=0.1,
        aggression=0.9,
        anchoring=1.0,
        concession_rate=0.025,
        concession_floor=0.1,
        disclosure=0.05,
        bluffing=0.8,
    ),
}

FOCUS_DIALS: dict[str, tuple[dict[str, float], str]] = {
    "error:1": ({}, "hold until you concede or six turns pass"),
    "error:2": ({}, "sometimes withhold reciprocal concessions"),
    "error:3": ({"anchoring": 1.0}, "open at its most extreme package"),
    "error:4": ({"anchoring": 0.6}, "hold an early low-surplus offer for two turns"),
    "error:5": ({"anchoring": 0.6}, "leave an issue for you to raise"),
    "error:6": ({}, "put two packages on the table early"),
    "rapport": ({}, "respond to constructive engagement with a faster concession"),
}


def focused_profile(profile: CounterpartProfile) -> CounterpartProfile:
    overrides, _ = FOCUS_DIALS.get(profile.focus, ({}, ""))
    return profile.model_copy(update=overrides)


def sample_profile(tier: int, rng: random.Random, jitter: float = 0.1) -> CounterpartProfile:
    """The tier's preset with each dial perturbed uniformly by up to ``jitter``."""
    base = TIERS[tier]
    dials = {d: min(1.0, max(0.0, getattr(base, d) + rng.uniform(-jitter, jitter))) for d in DIALS}
    return base.model_copy(update={"name": f"{base.name}~", **dials})


def _band(value: float, low: str, mid: str, high: str) -> str:
    return low if value < 1 / 3 else mid if value < 2 / 3 else high


def describe(profile: CounterpartProfile) -> str:
    """Natural-language behavior instructions for the counterpart's system prompt."""
    p = profile
    lines = [
        _band(
            p.anchoring,
            "Open with a reasonable offer close to what you think is fair.",
            "Open with a moderately favorable offer that leaves room to move.",
            "Open with an ambitious offer close to your best possible outcome.",
        ),
        _band(
            min(1.0, p.concession_rate / 0.1),
            "Concede rarely and in small steps; make the other side work for every move.",
            "Concede gradually in modest steps, and ask for something in return.",
            "Concede readily when the other side gives reasons.",
        ),
        _band(
            p.cooperativeness,
            "Treat this as a competition over a fixed pie.",
            "Be open to trades across issues, but protect your own interests first.",
            "Look for mutually beneficial trades across issues; treat it as joint problem-solving.",
        ),
        _band(
            p.aggression,
            "Be warm and polite throughout.",
            "Be assertive but civil.",
            "Be forceful: challenge their claims, show impatience, and apply pressure.",
        ),
        _band(
            p.disclosure,
            "Reveal as little as possible about your priorities; deflect direct questions.",
            "Share some priorities when the other side reciprocates.",
            "Share your priorities and reasons openly when asked.",
        ),
        _band(
            p.bluffing,
            "Be truthful; never misstate facts.",
            "You may be strategically vague, but do not state outright falsehoods.",
            "You may exaggerate your alternatives and how much particular issues matter to you.",
        ),
        "Never reveal your exact point values or your reservation value.",
    ]
    return "\n".join(f"- {line}" for line in lines)
