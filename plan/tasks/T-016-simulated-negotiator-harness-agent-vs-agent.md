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

- 2026-10-28: Extracted independently recoverable train_user and immediate private error logging. Recoveries preserve original sampled users, seeds, completed turns and feedback; failed users are not replaced. The live cohort remains in progress.

- 2026-10-28: Added scripts/recover_user.py for auditable recovery of an inactive original user. Bounded tag-batch correction addresses missing user indices without silently accepting incomplete labels. Error-only grounded ablation (128 users) did not rescue G: adaptive gain -0.02492, CI [-0.04712,-0.00212].

- 2026-10-28: Completed all 8 original LLM personas and 280 live episodes; concurrent recoveries preserved all sampled users. Final cached aggregation made zero API calls. Published paired user rows, episode diagnostics, source/runtime history and figures. Offline suite: 146 passed, 1 live test deselected; lint/format/task checks clean. Full findings in docs/results/sim3_evaluation.md.
