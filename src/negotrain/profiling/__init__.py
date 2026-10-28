"""Negotiator profiling: behavioral features per session and a profile across sessions.

Features (T-024, features.py) are things like first-offer claim, concession timing and size,
questions asked, and surplus over walk-away value. The profile (T-025, profile.py)
aggregates them into skill scores with uncertainty; T-026 validates it against synthetic
negotiators with known, injected weaknesses (simulation.ScriptedUser).
"""

from negotrain.profiling.features import FLAG_DESCRIPTIONS, extract_features, flags
from negotrain.profiling.profile import NegotiatorProfile, build_profile

__all__ = [
    "FLAG_DESCRIPTIONS",
    "NegotiatorProfile",
    "build_profile",
    "extract_features",
    "flags",
]
