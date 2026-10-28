---
id: T-027
title: Tailored scenario selection
status: in-progress
milestone: M2
workstream: counterpart
owner: mahdi
depends_on: [T-012, T-025]
---

## Goal
Choose the next practice scenario to target the user's top weakness while raising difficulty gradually.

## Context
Start rule-based: for example, an early conceder faces high-anchoring, slow-conceding counterparts; step the tier up after two strong results and down after an impasse. LLM-generated case variants are a stretch goal.

## Acceptance criteria
- [x] next_scenario(profile, history) -> ScenarioSpec
- [x] Policy documented and unit tested

## Log
- 2026-10-25: MVP branch: rule-based next_scenario (tier steps, focus dials, least-played case); default on Rehearse page.
- 2026-10-28: Reimplementation in progress against new-spec/report: exact feasible
  surplus reward, six opportunity detectors, case-scoped facts, fixed tagging rubric,
  discounted Beta beliefs, cost-weighted UCB/baselines, profile UI with credible intervals,
  and visible 20-user-move deadline. Replaces heuristic skill scores. Source-document
  discrepancies and remaining integration are recorded in decision 0008.
- 2026-10-28: Reimplementation milestone: independent tier floors/rates, visible deadline,
  code-selected hybrid formal actions, all focus hooks with feasibility tracking; terminal-R
  counterfactuals, M=4 defaults, disjoint selection/scoring seeds, paired bootstrap intervals,
  explicit hindsight labels, focus-first prep/feedback and personal credit fed into UCB.
  131 offline tests passed, including randomized walk-away invariants and a noisy ranking
  reversal test. API spend remains $0. Population calibration and sim3 evaluation pending.
