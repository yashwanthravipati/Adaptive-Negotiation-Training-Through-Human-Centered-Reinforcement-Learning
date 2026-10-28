---
id: T-020
title: Critical-turn detection
status: in-progress
milestone: M2
workstream: feedback
owner: mahdi
depends_on: []
---

## Goal
Find the user turns worth counterfactual analysis.

## Context
Candidates: first offers, concessions (own score drops from the previous offer), information disclosures (LLM-tagged), accept and walk-away decisions, responses to an anchor.

## Acceptance criteria
- [x] critical_turns(session, case) -> list of (turn_index, kind)
- [ ] Rules for offers and concessions; LLM tagging for disclosures
- [x] Unit tests on synthetic transcripts; cap per session

## Log
- 2026-10-25: MVP branch: feedback/critical.py, rule-based kinds with priority cap. No LLM disclosure tagging yet.
- 2026-10-28: Reimplementation milestone: independent tier floors/rates, visible deadline,
  code-selected hybrid formal actions, all focus hooks with feasibility tracking; terminal-R
  counterfactuals, M=4 defaults, disjoint selection/scoring seeds, paired bootstrap intervals,
  explicit hindsight labels, focus-first prep/feedback and personal credit fed into UCB.
  131 offline tests passed, including randomized walk-away invariants and a noisy ranking
  reversal test. API spend remains $0. Population calibration and sim3 evaluation pending.
