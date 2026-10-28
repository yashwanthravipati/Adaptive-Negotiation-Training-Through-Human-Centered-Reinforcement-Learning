---
id: T-022
title: Validate credit assignment
status: in-progress
milestone: M2
workstream: feedback
owner: unassigned
depends_on: [T-021]
---

## Goal
Evidence that the moments we flag actually mattered.

## Context
Stability: variance of estimates vs N. Planted blunders: insert known bad moves (accept the first offer, reveal the reservation value, a big early concession) into good transcripts and check they rank at the top. Face validity: two teammates rate the top flagged moments on 10 sessions.

## Acceptance criteria
- [ ] docs/results/credit_assignment.md with all three analyses
- [ ] Chosen K and N justified by stability and cost

## Log

- 2026-10-28: Offline sim3 validation: 12 sessions, 26 critical estimates. M=4 vs M=16 rank rho=.839, mean absolute delta difference=.0198 R, 96.2% sign agreement. All 12 planted acceptances show positive loss; 9/9 multi-turn cases rank first. docs/results/credit_assignment.md records limitations; teammate ratings remain pending.
