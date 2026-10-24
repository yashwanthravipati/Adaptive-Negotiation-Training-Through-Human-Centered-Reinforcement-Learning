---
id: T-011
title: Code-enforced concession schedule (hybrid counterpart)
status: todo
milestone: M1
workstream: counterpart
owner: unassigned
depends_on: [T-010]
---

## Goal
Make difficulty controllable in code rather than by prompt alone: the counterpart may only propose or accept deals at or above a per-turn aspiration level.

## Context
Decision 0003. Aspiration starts at a level set by `anchoring` and decays toward the reservation value at a rate set by `concession_rate`, optionally reciprocating the user's concessions. LLM counterparts concede too easily (the RQ2 concern); this is the main defense.

## Acceptance criteria
- [ ] aspiration(profile, turn, history) with unit tests
- [ ] CounterpartAgent validation rejects moves below aspiration
- [ ] Agent-vs-agent runs show counterpart offers stay on schedule
- [ ] Flag to disable it, for the prompt-only vs hybrid comparison in T-017

## Log
