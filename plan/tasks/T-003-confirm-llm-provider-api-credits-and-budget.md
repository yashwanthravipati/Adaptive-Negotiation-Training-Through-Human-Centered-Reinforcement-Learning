---
id: T-003
title: Confirm LLM provider, API credits, and budget
status: in-progress
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
- 2026-10-28: Persistent SQLite SpendLedger now atomically reserves the full 1M
  context at maximum cache/input price plus max output before each request. No SDK
  retries or server-side fallback; crashes/timeouts retain reserves. Verified official
  pricing: Opus 5.5 $4/$20, Sonnet 5.5 $2/$10 per MTok input/output at
  https://platform.claude.com/docs/en/about-claude/pricing. Overall hard cap $150.
  Planned 2,000–4,000 short calls (roughly 2k input + 250 output each), approximately
  $25–$70 at mixed Opus/Sonnet prices before cache savings, subject to the ledger.
  Automatic approval review rejected exporting private sim3 materials to Anthropic;
  explicit destination permission requested asynchronously. No API calls made yet.
  A local-only inferred sim3 projection allows offline evaluation to proceed.

- 2026-10-28: User explicitly authorized sending sim3 private materials to
  Anthropic within the $150 cap. Live pilot succeeded (7 calls, about $0.134).
  API rejects an empty fallbacks list; omitted the opt-in parameter instead.
  Its rejected request retains $8.01024 conservatively in the ledger.
  Planned live test: 8 random users, 4 policies, K=5, 3 held-out tier probes before
  and after, 280 episodes total. At 7–12 calls/episode, approximately 2k–3.5k
  calls × roughly $0.019/call = $40–$70, plus feedback. Eight independent workers;
  atomic full-context reservations enforce the $150 total across all workers.
  User's budget authorization covers the sweep; no repeat approval requested.

- 2026-10-28: Live structured-response failures exposed SDK validation before usage accounting. The gateway now reads and settles raw provider usage before parsing generated JSON, with one explicitly budgeted retry for known truncation. Raised dialogue/persona output limits; preserved all earlier uncertain reservations and recorded the runtime revision. Cohort resumed from saved turns.
