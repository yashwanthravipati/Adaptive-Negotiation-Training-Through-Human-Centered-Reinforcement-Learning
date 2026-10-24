---
id: T-003
title: Confirm LLM provider, API credits, and budget
status: todo
milestone: M0
workstream: infra
owner: unassigned
depends_on: []
---

## Goal
Settle which models we use and how much we can spend, so experiments and the study are not blocked or surprised by cost.

## Context
Decision 0001 proposes Claude through negotrain.llm. HW0 may have used another provider; check whether the course provides credits. Counterfactual rollouts (T-021) are the main cost driver.

## Acceptance criteria
- [ ] Decision 0001 accepted or amended
- [ ] Each teammate has a key in their local .env (never committed)
- [ ] Budget and cost-estimate rule written in PLAN.md §Budget
- [ ] Decide whether rollouts and simulated users use a cheaper model than the counterpart; record in 0001

## Log
