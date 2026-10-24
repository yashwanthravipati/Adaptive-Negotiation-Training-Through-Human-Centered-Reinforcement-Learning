# 0002: Feedback after the session only; no live move recommendations

- **Status:** accepted
- **Date:** 2026-10-24
- **Deciders:** Yash, Mahdi, Vincent (from the proposal)

## Context
The proposal's central concern: AI negotiation support that recommends moves in the moment
builds dependence rather than skill. Our claim is that rehearsal plus turn-level feedback
builds skill.

## Decision
During a rehearsal or real negotiation, the tool shows the user's own confidential sheet,
the conversation, and the scores of offers on the table, and nothing else. Coaching,
counterfactual analysis, and profile insights appear only after the session ends.

## Consequences
- The UI must not show hints, suggested replies, or "best next offer" during a session.
- Counterfactual rollouts can run asynchronously after the session (and slower).
- Prep-time rehearsal is the place for practice, not live support.
