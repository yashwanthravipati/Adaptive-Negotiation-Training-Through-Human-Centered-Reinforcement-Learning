# Opportunity beliefs and evaluation contract

Status: proposed; implementation follows the user-requested new specification.
Date: 2026-10-28
Tasks: T-011, T-016, T-017, T-021, T-024, T-025, T-026, T-027.

The user requested reimplementation against docs/new-spec.md and docs/report.tex,
randomly sampled virtual-user evaluation with at most $150 API spend, and incremental
commits/pushes to origin/MVP. They subsequently selected data/cases/sim3 for evaluations.
Existing uploads, prep, persistence, custom-offer handling, and Streamlit flows are reused.

2026-10-28 amendment: the user explicitly authorized sim3 role-material export to
Anthropic, concurrent completion, and an increased cumulative cap of $200. The ledger
records the cap amendment without releasing prior uncertain reservations. Final results
and runtime-repair limitations are in docs/results/sim3_evaluation.md.

The documents disagree in two material places. The default Beta filter preserves the
prior and discounts evidence, as explicitly defined in new-spec.md. The discount_prior
option implements report.tex's recursion, for sensitivity analysis. Report both the
report's held-out no-focus competence gain G(s_K)-G(s_0) and the spec's true-state
weighted error reduction sum_j w_j o_bar_j (theta_before-theta_after). Never substitute
posterior improvement for actual user improvement. K=5; evaluation probes use no focus.

R uses the exact best user package that satisfies the counterpart's walk-away, respecting
explicit hard constraints. Unaccepted offers earn nothing; no deal earns zero; below-
walkaway agreements retain negative rewards; custom agreements are unscored. A nonpositive
feasible surplus denominator is explicitly unsupported, rather than silently scored zero.
The deadline is 20 user moves, each with a counterpart response, following new-spec's
paired-turn convention. Transcript indices remain individual message indices.

Fact/rapport annotations have explicit provenance. Missing annotations are excluded,
not treated as negative observations; ignoring-issue failures likewise require complete
message annotation. These are observation limitations, not changes to the target rubric.
The fixed tagging rubric still needs the specified teammate validation on 20 transcripts;
synthetic checks cannot stand in for human inter-rater agreement.

CounterpartProfile gains focus, focus_issue, and a concession_floor independent of rate.
Session gains seed and max_user_turns; Turn gains optional observed tags. Defaults load
old persisted sessions. The six heuristic skill scores are removed, replaced with a Beta
per error/fact/rapport component. CostModel supports population and per-user credit means;
unit cost/opportunity defaults are explicitly uncalibrated until evaluation calibrates them.

The sim3 documents are licensed class materials and are ignored by git, as are private
case projections and raw transcripts. The supplied role is Border Authority; no official
point table or Mayor private role was found on initial inspection. Numeric scoring must
be labeled synthetic/inferred if such materials are unavailable. Do not claim measured
human transfer or official case performance from simulation under inferred utilities.
