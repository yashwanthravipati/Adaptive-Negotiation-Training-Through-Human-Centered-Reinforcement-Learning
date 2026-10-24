---
id: T-017
title: Controllability experiment (ML-Q1)
status: todo
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
