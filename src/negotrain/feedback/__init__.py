"""Post-session feedback: critical-turn detection, counterfactual credit assignment, coaching.

At each important user turn, fork the transcript, simulate alternative user actions several
times each, and estimate how much the actual choice changed the expected outcome.
Feedback is shown after the session only, never as live move recommendations.
Tasks: T-020 (critical turns), T-021 (rollouts), T-022 (validation), T-023 (coaching report).
"""
