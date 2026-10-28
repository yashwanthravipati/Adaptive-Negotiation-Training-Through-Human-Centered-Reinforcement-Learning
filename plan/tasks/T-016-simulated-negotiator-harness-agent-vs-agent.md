---
id: T-016
title: Simulated-negotiator harness (agent vs agent)
status: in-progress
milestone: M1
workstream: counterpart
owner: mahdi
depends_on: []
---

## Goal
Batch-run the counterpart against simulated users for experiments, including users with injected traits (concedes early, anchors weakly, never asks questions, aggressive).

## Context
Shared by T-017, T-018, T-021, and T-026. Use concurrent.futures for parallel episodes.

## Acceptance criteria
- [x] run_episode(case, user_policy, counterpart, max_turns) -> Session
- [x] Scripted and LLM-persona user policies
- [x] Outputs to results/<experiment>/ with config.json; seeded
- [ ] Prints an estimated cost and asks before large runs

## Log
- 2026-10-25: MVP branch: simulation.py ScriptedUser + run_episode(case, session, counterpart, user, max_turns) (signature differs from spec). No LLM persona, results/ output, or cost prompt yet.
- 2026-10-28: Added randomly sampled grounded scripted users, role-projected LLM
  personas, restartable episode checkpoints, paired policy comparisons, and exact
  Binomial-oracle experiments. Grounded behavior propensities are NOT falsely labeled
  true conditional detector rates; recovery compares to independent Monte Carlo reference
  rates. LLM users receive prior feedback; only the synthetic model imposes Learn.
  scripts/evaluate.py separates calibration/development/test seeds and preserves raw
  transcripts privately. Pending: execute sim3 suite and live suite after export approval.

- 2026-10-28: Offline sim3 suite complete: 8 calibration, 64 development,
  512 oracle test, 32 steering, 64 recovery, 128 grounded-learning users.
  Tier R decreases monotonically (rho=-1). Adaptive held-out G gain -0.00592,
  95% user-bootstrap CI [-0.01634, 0.00462]; no demonstrated transfer improvement.
  Development selected lambda=.5, kappa=0, so the tuned UCB policy equals greedy.
  Added deterministic parallel users, pre-session focus instructions for LLM users,
  and exact-case/role calibration loading in the app. Human tagging validation and
  human transfer remain unmeasured.
