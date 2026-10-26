# 0006: Open-ended terms alongside listed options

- **Status:** proposed
- **Date:** 2026-10-26
- **Context:** User requested typing open-ended solutions for each issue instead of being
  restricted to the parser's predefined options. Implementation remains in an isolated
  worktree while the existing app on port 8501 is in use.

## Decision

Store custom proposals in `Offer.custom_terms` (issue id to exact wording), alongside the
existing `terms` map of listed option ids. An issue can have one representation; either
counts toward offer completion. Both sides may propose custom terms, and either side can
accept the other's complete offer verbatim. Existing saved offers remain compatible.

The AI counterpart evaluates custom terms qualitatively using its own confidential role
and constraints. It must not reject a proposal solely because it is not a listed option,
silently substitute a listed option, or invent a numeric point value. Code still validates
issue ids and listed-option hard constraints. Numeric reservation and aspiration checks
continue for fully listed offers; they cannot be guaranteed for unscored custom terms.
This is the explicit limitation of extending decision 0003 to open-ended solutions.

The deterministic scorer returns null points and surplus for custom offers. Outcome
efficiency is also unknown. UI cards and transcripts show custom wording and "not scored".
For sessions involving custom proposals, coaching uses the full transcript but numeric
counterfactual rollouts and concession features are omitted. Profiles and sim-to-real
comparisons do not reinterpret missing values as zero or as evidence of strong performance.
The offline counterpart stays limited to listed options and states that limitation.

## Consequences

- Students can negotiate creative arrangements without being forced into the score table.
- Custom agreements can be saved for both rehearsals and real negotiations.
- Numeric benchmarks describe only the listed options, not an upper bound on new solutions.
- Open-ended evaluation is qualitative; it is not evidence that numeric walk-away or
  aspiration constraints were satisfied. Researchers must distinguish these sessions in
  quantitative analyses.
- No point tables, role sheets, or existing user sessions are rewritten.
