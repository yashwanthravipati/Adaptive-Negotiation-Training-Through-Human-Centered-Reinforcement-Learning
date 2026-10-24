---
id: T-014
title: Streamlit rehearsal UI v1
status: todo
milestone: M1
workstream: app
owner: unassigned
depends_on: []
---

## Goal
The participant-facing app: prep screen, chat with the counterpart, offer builder, accept and walk-away buttons, end screen with score.

## Context
Put it in src/negotrain/app/. Offers come from a per-issue dropdown builder so they are always structured. Must run offline against ScriptedLLM for UI work.

## Acceptance criteria
- [ ] `streamlit run src/negotrain/app/main.py` works
- [ ] Sessions saved through SessionStore with a participant id
- [ ] API key stays server-side; counterpart's sheet hidden until debrief
- [ ] Offline mode (ScriptedLLM) via an environment flag

## Log
