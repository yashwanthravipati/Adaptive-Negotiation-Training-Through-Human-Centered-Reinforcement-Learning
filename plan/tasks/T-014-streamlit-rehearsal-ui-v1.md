---
id: T-014
title: Streamlit rehearsal UI v1
status: in-progress
milestone: M1
workstream: app
owner: mahdi
depends_on: []
---

## Goal
The participant-facing app: prep screen, chat with the counterpart, offer builder, accept and walk-away buttons, end screen with score.

## Context
Put it in src/negotrain/app/. Offers come from a per-issue dropdown builder so they are always structured. Must run offline against ScriptedLLM for UI work.

## Acceptance criteria
- [x] `streamlit run src/negotrain/app/main.py` works
- [x] Sessions saved through SessionStore with a participant id
- [x] API key stays server-side; counterpart's sheet hidden until debrief
- [x] Offline mode (ScriptedLLM) via an environment flag

## Log
- 2026-10-25: MVP branch: src/negotrain/app (main.py + views.py): Start/onboarding, Rehearse (offer builder, accept, walk away), Feedback, My profile, Real negotiation, Case library. Offline mode via NEGOTRAIN_OFFLINE or no key. AppTest smoke tests incl. info hiding. Not yet tried live with Claude.
- 2026-10-25: UI polish: theme (.streamlit/config.toml), app/style.py components, grouped navigation, logo, chat bubbles with offer cards, stat cards, point pills, two-column offer builder; fixed $ amounts rendering as LaTeX (style.md). Checked visually in a browser (offline mode).
