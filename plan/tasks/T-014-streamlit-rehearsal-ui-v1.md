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
Put it in src/negotrain/app/. Offers come from a per-issue builder with listed suggestions and user-written custom terms. Both remain structured by issue; custom terms retain their wording without invented point values. Must run offline against ScriptedLLM for UI work.

## Acceptance criteria
- [x] `streamlit run src/negotrain/app/main.py` works
- [x] Sessions saved through SessionStore with a participant id
- [x] API key stays server-side; counterpart's sheet hidden until debrief
- [x] Offline mode (ScriptedLLM) via an environment flag
- [x] Each issue accepts a listed suggestion or custom text; custom offers survive negotiation, acceptance, persistence, and real-outcome logging without invented point scores

## Log
- 2026-10-25: MVP branch: src/negotrain/app (main.py + views.py): Start/onboarding, Rehearse (offer builder, accept, walk away), Feedback, My profile, Real negotiation, Case library. Offline mode via NEGOTRAIN_OFFLINE or no key. AppTest smoke tests incl. info hiding. Not yet tried live with Claude.
- 2026-10-25: UI polish: theme (.streamlit/config.toml), app/style.py components, grouped navigation, logo, chat bubbles with offer cards, stat cards, point pills, two-column offer builder; fixed $ amounts rendering as LaTeX (style.md). Checked visually in a browser (offline mode).
- 2026-10-26: Added open-ended issue proposals in isolated worktree on t-014-open-ended-offers, preserving the earlier ZIP work and leaving localhost:8501 unchanged. Editable suggestion fields save Offer.custom_terms verbatim; counterpart prompts and responses support custom proposals and acceptance. Custom agreements have null numeric scores; qualitative coaching remains available, while numeric rollouts/concession metrics and unsupported numeric comparisons are skipped. Decision 0006 documents the schema and economic-check limitation. Regression tests cover saved offers, information hiding, known hard constraints, profile/curriculum handling, and AppTest rehearsal/debrief/real-outcome flows. Live API behavior is not tested.
- 2026-10-26: Validation: all 84 offline tests pass; ruff lint and formatting, task validation (38 tasks), and git diff whitespace checks pass.
- 2026-10-26: API key can now be replaced or removed any time (Settings); pasted keys are checked with a free models.list call (llm.check_api_key) before use.
