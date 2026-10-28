---
id: T-011
title: Code-enforced concession schedule (hybrid counterpart)
status: in-progress
milestone: M1
workstream: counterpart
owner: mahdi
depends_on: [T-010]
---

## Goal
Make difficulty controllable in code rather than by prompt alone: the counterpart may only propose or accept deals at or above a per-turn aspiration level.

## Context
Decision 0003. Aspiration starts at a level set by `anchoring` and decays toward the reservation value at a rate set by `concession_rate`, optionally reciprocating the user's concessions. LLM counterparts concede too easily (the RQ2 concern); this is the main defense.

## Acceptance criteria
- [x] aspiration(profile, turn, history) with unit tests
- [x] CounterpartAgent validation rejects moves below aspiration
- [ ] Agent-vs-agent runs show counterpart offers stay on schedule
- [x] Flag to disable it, for the prompt-only vs hybrid comparison in T-017

## Log
- 2026-10-25: MVP branch: counterpart/aspiration.py (start from anchoring, decay from concession_rate, reciprocity weighted by cooperativeness, floor above RV); agent rejects moves below it; enforce_schedule flag (+ app toggle). Verified with rule-based agent-vs-agent runs only.
- 2026-10-28: Reimplementation milestone: independent tier floors/rates, visible deadline,
  code-selected hybrid formal actions, all focus hooks with feasibility tracking; terminal-R
  counterfactuals, M=4 defaults, disjoint selection/scoring seeds, paired bootstrap intervals,
  explicit hindsight labels, focus-first prep/feedback and personal credit fed into UCB.
  131 offline tests passed, including randomized walk-away invariants and a noisy ranking
  reversal test. API spend remains $0. Population calibration and sim3 evaluation pending.
