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
