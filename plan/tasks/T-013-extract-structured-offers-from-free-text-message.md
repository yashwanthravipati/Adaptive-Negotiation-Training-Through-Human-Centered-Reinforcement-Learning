---
id: T-013
title: Extract structured offers from free-text messages
status: todo
milestone: M1
workstream: cases
owner: unassigned
depends_on: []
---

## Goal
When a user states an offer in prose instead of using the offer builder, detect it and turn it into an Offer (confirmed by the user in the UI).

## Context
Structured offers are what make outcomes and concessions measurable.

## Acceptance criteria
- [ ] extract_offer(text, case, llm) -> Offer | None
- [ ] Precision and recall on 30 hand-written utterances
- [ ] UI asks the user to confirm an extracted offer

## Log
