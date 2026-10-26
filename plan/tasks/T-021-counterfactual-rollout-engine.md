---
id: T-021
title: Counterfactual rollout engine
status: in-progress
milestone: M2
workstream: feedback
owner: mahdi
depends_on: [T-016, T-020]
---

## Goal
Estimate how much each critical decision changed the expected outcome.

## Context
At each critical turn, propose K alternative user actions (firmer, softer, logroll, ask a question, hold); for the actual action and each alternative, run N rollouts from the fork (counterpart vs a simulated user conditioned on this user's style) to agreement, impasse, or a turn cap. Report E[score] per action with bootstrap CIs. Runs after the session, never live.

## Acceptance criteria
- [x] estimate_turn_values(session, case, turn_index, k, n) -> TurnEstimate
- [x] Parallel rollouts; cost and latency reported per session
- [x] Deterministic offline tests with ScriptedLLM
- [x] Results saved next to the session

## Log
- 2026-10-25: MVP branch: feedback/rollouts.py; code-built alternatives; LLM counterpart for `horizon` turns then rule-based finisher; threaded; cost/latency shown in app; saved to data/sessions/feedback/. Default 3 turns x 3 actions x 2 rollouts x 2 LLM turns = 36 calls. Not validated (T-022).
