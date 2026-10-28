---
id: T-024
title: Behavioral feature extraction
status: in-progress
milestone: M2
workstream: profiling
owner: mahdi
depends_on: []
---

## Goal
Per-session behavioral features shared by profiling, curriculum, and the study analysis.

## Context
First-offer extremity, who anchored first, concession count, size, and timing, reciprocity, questions asked, information disclosed, agreement efficiency (logrolling), surplus over walk-away value, impasse.

## Acceptance criteria
- [x] extract_features(session, case) -> dict
- [x] Works on human-vs-human sessions too
- [x] Unit tests

## Log
- 2026-10-25: MVP branch: profiling/features.py + error flags; real sessions without turns get outcome features only.
- 2026-10-28: Reimplementation in progress against new-spec/report: exact feasible
  surplus reward, six opportunity detectors, case-scoped facts, fixed tagging rubric,
  discounted Beta beliefs, cost-weighted UCB/baselines, profile UI with credible intervals,
  and visible 20-user-move deadline. Replaces heuristic skill scores. Source-document
  discrepancies and remaining integration are recorded in decision 0008.
