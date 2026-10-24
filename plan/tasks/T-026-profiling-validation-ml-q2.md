---
id: T-026
title: Profiling validation (ML-Q2)
status: todo
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
- [ ] Split-half reliability
- [ ] docs/results/profiling.md

## Log
