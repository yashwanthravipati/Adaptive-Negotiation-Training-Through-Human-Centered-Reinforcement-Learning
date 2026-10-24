---
id: T-020
title: Critical-turn detection
status: todo
milestone: M2
workstream: feedback
owner: unassigned
depends_on: []
---

## Goal
Find the user turns worth counterfactual analysis.

## Context
Candidates: first offers, concessions (own score drops from the previous offer), information disclosures (LLM-tagged), accept and walk-away decisions, responses to an anchor.

## Acceptance criteria
- [ ] critical_turns(session, case) -> list of (turn_index, kind)
- [ ] Rules for offers and concessions; LLM tagging for disclosures
- [ ] Unit tests on synthetic transcripts; cap per session

## Log
