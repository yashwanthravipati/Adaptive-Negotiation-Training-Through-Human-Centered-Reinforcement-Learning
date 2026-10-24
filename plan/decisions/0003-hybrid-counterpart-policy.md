# 0003: Hybrid counterpart: LLM dialogue, code-enforced concession schedule

- **Status:** proposed (implement in T-011, evaluate in T-017)
- **Date:** 2026-10-24
- **Deciders:**

## Context
LLM counterparts tend to be more agreeable and concede more readily than people. A prompt
alone ("concede slowly") gives weak, unreliable control over difficulty, and difficulty
control is ML-Q1.

## Decision
The LLM writes the dialogue and chooses offers. Code enforces the economics:
- never accept, or propose a complete deal, below the reservation value (already in v1);
- each turn, an aspiration level (starting from `anchoring`, decaying toward the
  reservation value at a rate set by `concession_rate`, optionally reciprocating) bounds
  which offers the counterpart may make or accept. Invalid moves are sent back to the
  model with an explanation.

## Consequences
- Difficulty becomes measurable and reproducible; T-017 compares prompt-only with hybrid.
- More retries per turn, so latency goes up; keep the explanation short.
- The schedule must allow logrolling (trading across issues), not only uniform concession.
