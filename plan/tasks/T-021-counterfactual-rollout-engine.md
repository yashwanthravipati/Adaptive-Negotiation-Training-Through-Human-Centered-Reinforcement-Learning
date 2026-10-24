---
id: T-021
title: Counterfactual rollout engine
status: todo
milestone: M2
workstream: feedback
owner: unassigned
depends_on: [T-016, T-020]
---

## Goal
Estimate how much each critical decision changed the expected outcome.

## Context
At each critical turn, propose K alternative user actions (firmer, softer, logroll, ask a question, hold); for the actual action and each alternative, run N rollouts from the fork (counterpart vs a simulated user conditioned on this user's style) to agreement, impasse, or a turn cap. Report E[score] per action with bootstrap CIs. Runs after the session, never live.

## Acceptance criteria
- [ ] estimate_turn_values(session, case, turn_index, k, n) -> TurnEstimate
- [ ] Parallel rollouts; cost and latency reported per session
- [ ] Deterministic offline tests with ScriptedLLM
- [ ] Results saved next to the session

## Log
