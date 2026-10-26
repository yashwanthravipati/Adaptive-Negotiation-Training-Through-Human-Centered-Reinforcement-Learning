---
id: T-010
title: Counterpart agent v1
status: in-progress
milestone: M1
workstream: counterpart
owner: unassigned
depends_on: []
---

## Goal
A counterpart that plays its hidden role believably, uses formal offers, and never leaks its points or reservation value.

## Context
A scaffold exists in src/negotrain/counterpart/agent.py: prompt-driven, structured moves, guards on ids and reservation value, retries on invalid moves. Try it with `negotrain play data/cases/cloudline_hiring.json --role candidate --tier 3`.

## Acceptance criteria
- [x] Structured move schema, guards, retry loop, offline tests
- [ ] Play at least 5 live sessions across tiers 1, 3, and 5; note failure modes in this file
- [ ] Prompt iteration: stays in character, makes regular formal offers, no leaks
- [ ] Measure latency per turn (target under 10 s); try effort=low for chat turns
- [ ] One @pytest.mark.live smoke test

## Log
- 2026-10-24: Scaffold landed with T-001.
- 2026-10-25: MVP branch: after 3 invalid moves the agent makes a code counteroffer at its current minimum instead of raising (agent.fallbacks); per-turn private note states the minimum. Live sessions still to do.
