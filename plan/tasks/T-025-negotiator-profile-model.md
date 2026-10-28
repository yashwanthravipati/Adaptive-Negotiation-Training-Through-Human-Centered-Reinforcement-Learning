---
id: T-025
title: Negotiator profile model
status: in-progress
milestone: M2
workstream: profiling
owner: mahdi
depends_on: [T-024]
---

## Goal
Aggregate features across sessions into strengths and weaknesses, with uncertainty.

## Context
For example, per-feature z-scores against a reference population (simulated users or pooled participants), shrunk toward the mean when there are few sessions.

## Acceptance criteria
- [x] Profile schema and update(profile, session)
- [x] Top weaknesses with confidence
- [x] Shown in the UI

## Log
- 2026-10-25: MVP branch: profile.py, six skills, shrinkage to 0.5 (prior weight 2), confidence n/(n+2); rebuilt from all sessions; My profile page.
- 2026-10-28: Reimplementation in progress against new-spec/report: exact feasible
  surplus reward, six opportunity detectors, case-scoped facts, fixed tagging rubric,
  discounted Beta beliefs, cost-weighted UCB/baselines, profile UI with credible intervals,
  and visible 20-user-move deadline. Replaces heuristic skill scores. Source-document
  discrepancies and remaining integration are recorded in decision 0008.
