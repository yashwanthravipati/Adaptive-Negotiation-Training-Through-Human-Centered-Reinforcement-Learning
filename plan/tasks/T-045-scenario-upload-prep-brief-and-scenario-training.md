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
- [x] Upload ZIP bundles alongside individual files; preserve document paths, skip metadata, and report unreadable members
- [x] Preserve original extracted source text and whole-document role visibility for the personal assistant
- [x] parse_documents(files, llm) works out which file is which and infers a missing sheet
- [x] Prep brief: code-computed numbers (walk-away, target, best deal, issue priorities) plus LLM brief with template fallback; never sees the other side's sheet
- [x] Training plan on the Prepare page (tiers 2, 3, 4, plus the curriculum's pick) that starts rehearsals on the scenario; prep checklist visible while rehearsing
- [x] Offline tests incl. AppTest upload flow
- [ ] Tried live on a real class case (parse quality, brief quality, latency)

## Log
- 2026-10-25: Built on branch MVP: cases/documents.py, parser.parse_documents, prep.py, Prepare page in app/views.py. 59 offline tests pass. Not yet run against the API (no key in the dev environment).
- 2026-10-25: Flow simplified per user: no sign-in/onboarding (local single user, config.participant_id); upload page is the only screen until a scenario (case+role) is active; then Prepare (auto brief + plan), Rehearse, Feedback, My profile, Real negotiation work on it. 59 tests pass.
- 2026-10-26: Added ZIP uploads on t-045-zip-uploads in a separate worktree, leaving the user's running app on port 8501 and its source/data untouched. Reads PDF/DOCX/TXT/MD members in memory, preserves archive paths and duplicate names, skips hidden/macOS metadata, and reports corrupt, unsupported, or encrypted members. Limits bundles to 200 entries and 50 MB of uncompressed documents. All 70 offline tests pass, including mixed ZIP/loose-file AppTest uploads; ruff lint/format and task validation pass. Not applied to the running app.
- 2026-10-26: Personal assistant source access: Case.source_documents retains exact extracted text; parser classifications determine whole-file role access, with mixed/unknown/ambiguous files withheld. Pasted instructions preserve declared public/role mappings. Legacy cases default to no originals and can attach sources in the assistant. Source retention and confidentiality are covered in the 100-test offline suite.
