---
id: T-026
title: Profiling validation (ML-Q2)
status: in-progress
milestone: M2
workstream: profiling
owner: unassigned
depends_on: [T-016, T-025]
---

## Goal
Show that the profile measures something real.

## Context
Synthetic recovery: simulated users with injected traits, 5 sessions each; does the profiler find the traits? Then reliability (split-half) and, on human data, predictive validity (sessions 1-3 predict 4-5) and agreement with teammate labels (Cohen's kappa).

## Acceptance criteria
- [ ] Per-trait AUC or precision and recall on synthetic users
- [x] Split-half reliability
- [x] docs/results/profiling.md

## Log

- 2026-10-28: Evaluated 64 grounded users with 5 training and 30 reference sessions each, all 27 state components, AUC and split-half diagnostics; separately 512 exact Binomial oracle users. Error-2 MC-reference coverage only 65.6%; no claim of uniformly calibrated inference. See docs/results/profiling.md. Human label agreement and prediction remain pending.
