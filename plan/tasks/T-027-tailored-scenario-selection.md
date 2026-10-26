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
