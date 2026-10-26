---
id: T-045
title: Scenario upload, prep brief, and scenario training plan
status: in-progress
milestone: M1
workstream: app
owner: mahdi
depends_on: [T-004]
---

## Goal
A participant uploads all the materials for an upcoming negotiation and gets a practice scenario, a preparation brief from their side, and a training plan of rehearsals on that exact scenario: the proposal's "rehearse the specific case during prep time".

## Context
Requested 2026-10-25 for the class simulation. Builds on the parser (T-004), curriculum (T-027), and app (T-014). Preparation happens before the negotiation, so it is consistent with decision 0002 (no live recommendations during a negotiation). The prep prompt sees only the public info and the participant's own sheet (information hiding).

## Acceptance criteria
- [x] Upload PDF / Word / text files; text extracted (cases/documents.py); unreadable files reported
- [x] parse_documents(files, llm) works out which file is which and infers a missing sheet
- [x] Prep brief: code-computed numbers (walk-away, target, best deal, issue priorities) plus LLM brief with template fallback; never sees the other side's sheet
- [x] Training plan on the Prepare page (tiers 2, 3, 4, plus the curriculum's pick) that starts rehearsals on the scenario; prep checklist visible while rehearsing
- [x] Offline tests incl. AppTest upload flow
- [ ] Tried live on a real class case (parse quality, brief quality, latency)

## Log
- 2026-10-25: Built on branch MVP: cases/documents.py, parser.parse_documents, prep.py, Prepare page in app/views.py. 59 offline tests pass. Not yet run against the API (no key in the dev environment).
- 2026-10-25: Flow simplified per user: no sign-in/onboarding (local single user, config.participant_id); upload page is the only screen until a scenario (case+role) is active; then Prepare (auto brief + plan), Rehearse, Feedback, My profile, Real negotiation work on it. 59 tests pass.
