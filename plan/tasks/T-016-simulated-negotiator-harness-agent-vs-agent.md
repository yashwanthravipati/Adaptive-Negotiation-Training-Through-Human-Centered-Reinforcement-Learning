---
id: T-016
title: Simulated-negotiator harness (agent vs agent)
status: in-progress
milestone: M1
workstream: counterpart
owner: mahdi
depends_on: []
---

## Goal
Batch-run the counterpart against simulated users for experiments, including users with injected traits (concedes early, anchors weakly, never asks questions, aggressive).

## Context
Shared by T-017, T-018, T-021, and T-026. Use concurrent.futures for parallel episodes.

## Acceptance criteria
- [x] run_episode(case, user_policy, counterpart, max_turns) -> Session
- [ ] Scripted and LLM-persona user policies
- [ ] Outputs to results/<experiment>/ with config.json; seeded
- [ ] Prints an estimated cost and asks before large runs

## Log
- 2026-10-25: MVP branch: simulation.py ScriptedUser + run_episode(case, session, counterpart, user, max_turns) (signature differs from spec). No LLM persona, results/ output, or cost prompt yet.
