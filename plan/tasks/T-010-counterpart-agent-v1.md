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
- [x] Measure latency per turn (target under 10 s); try effort=low for chat turns
- [ ] One @pytest.mark.live smoke test

## Log
- 2026-10-24: Scaffold landed with T-001.
- 2026-10-25: MVP branch: after 3 invalid moves the agent makes a code counteroffer at its current minimum instead of raising (agent.fallbacks); per-turn private note states the minimum. Live sessions still to do.
- 2026-10-26: First live run (Vincent; claude-opus-5-5, effort=low, schedule on; cloudline_hiring, counterpart = recruiter, vs ScriptedUser open_share=0.9 step=0.08 asking a question each turn; 16-turn cap). Tier 1: agreed in 10 turns, user 7300 pts, 6.0 s mean / 6.7 s max per counterpart turn, $0.11. Tier 3: agreed in 14 turns, user 6700, 6.5 / 7.6 s, $0.17. Tier 5: no deal by the cap, best offer on the table 4700, 6.5 / 7.3 s, $0.20. User points fall with tier. 0 fallbacks, no retry failures. No leaks of points or reservation value in 4 sessions (a keyword check plus reading the transcripts). Stays in character; tier 5 is firm but plausible (calls out repeated proposals, small concessions, answers questions), and its formal offers match its text. Opponent was scripted, not a human, so this counts as 4 of the 5 live sessions only loosely; no live pytest yet.
