"""Post-session feedback: critical-turn detection, counterfactual credit assignment, coaching.

At each important user turn, fork the transcript, simulate alternative user actions several
times each, and estimate how much the actual choice changed the expected outcome.
Feedback is shown after the session only, never as live move recommendations.
Tasks: T-020 (critical.py), T-021 (rollouts.py), T-022 (validation), T-023 (coaching.py).
"""

from negotrain.feedback.coaching import (
    CoachingReport,
    Debrief,
    OutcomeSummary,
    build_report,
    outcome_summary,
    transcript,
)
from negotrain.feedback.critical import CriticalTurn, critical_turns
from negotrain.feedback.rollouts import (
    CounterfactualReport,
    TurnEstimate,
    alternatives,
    analyze_session,
    estimate_calls,
)

__all__ = [
    "CoachingReport",
    "CounterfactualReport",
    "CriticalTurn",
    "Debrief",
    "OutcomeSummary",
    "TurnEstimate",
    "alternatives",
    "analyze_session",
    "build_report",
    "critical_turns",
    "estimate_calls",
    "outcome_summary",
    "transcript",
]
