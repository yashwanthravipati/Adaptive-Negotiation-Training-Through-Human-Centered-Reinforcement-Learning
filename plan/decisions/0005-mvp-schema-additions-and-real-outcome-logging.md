# 0005: MVP schema additions, and logging real negotiations as sessions

- **Status:** proposed
- **Date:** 2026-10-25
- **Deciders:** Mahdi (proposed); needs Yash and Vincent

## Context
The MVP needs to (1) rehearse a class case when a student has only their own confidential
sheet, (2) record onboarding, and (3) compare a real negotiation with rehearsals (RQ2)
before the human-vs-human mode (T-015) exists.

## Decision
- `RoleSheet.inferred` marks a sheet the parser estimated. Sampling several counterpart
  profiles per case covers the uncertainty, in line with the proposal's domain
  randomization.
- A real negotiation is stored as a `Session` with `kind="real"`, the agreement, and the
  participant's ratings of the other side (`observed_counterpart`, the same dials as
  `CounterpartProfile`). It may have no turns. Feature extraction handles that (outcome
  features only), so profiling and the sim-to-real comparison use one code path.
- `Participant` (onboarding) lives in `schemas.py` and is stored under
  `data/participants/` (gitignored, decision 0004).
- All new fields have defaults; existing JSON still loads.

## Consequences
- T-015 (in-app human-vs-human) can reuse `kind="real"` with full transcripts later.
- Analysis code must filter on `kind` (rehearsal vs real).
- Observed dials are self-reports, not measurements; treat them as noisy in RQ2 analysis.
