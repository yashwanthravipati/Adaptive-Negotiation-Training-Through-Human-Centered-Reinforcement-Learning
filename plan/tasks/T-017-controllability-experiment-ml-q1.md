---
id: T-017
title: Controllability experiment (ML-Q1)
status: in-progress
milestone: M1
workstream: counterpart
owner: unassigned
depends_on: [T-012, T-016]
---

## Goal
Show whether, and how precisely, the dials and tiers control counterpart behavior.

## Context
Sweep each dial and each tier against fixed simulated users, at least 10 episodes per setting. Metrics: opening-offer extremity, concession per turn, turns to agreement, agreement rate, counterpart surplus, user score, disclosure (LLM-judged). Compare prompt-only with hybrid (T-011).

## Acceptance criteria
- [ ] Spearman correlation of dial to metric (monotonicity) and a cross-talk matrix
- [ ] Figures and summary in docs/results/controllability.md
- [ ] Headline result ready for Checkpoint 2

## Log

- 2026-10-28: sim3 primary offline sweep: 32 random users, tier mean R .559/.501/.415/.266/.224, rho=-1; zero schedule violations across 7960 primary episodes. Focus opportunity uplift mixed: error4 +.188, error6 -2.156; fixed per-issue opportunities cannot increase under error5. See docs/results/sim3_evaluation.md; no human-likeness claim.

- 2026-10-28: Live sim3 cohort complete: 280 episodes with zero schedule violations. Eight baseline personas at tiers 1/3/5 have mean R .50568/.43750/.19886, Spearman -1; all 160 training episodes agree. This is exploratory tier evidence, not the complete dial cross-talk/prompt-only comparison or human-likeness validation.
