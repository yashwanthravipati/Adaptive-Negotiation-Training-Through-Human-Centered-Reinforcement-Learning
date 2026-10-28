# Counterfactual credit validation

The [sim3 evaluation report](sim3_evaluation.md#counterfactual-validity) reports stability
against M=16 and planted early-acceptance interventions. Outputs are in
[credit.json](../../results/sim3/validation/credit.json), with per-turn rows alongside it.

M=4 has rank correlation 0.839 and mean absolute difference 0.0198 R against M=16.
All 12 planted acceptances have positive estimated loss; all nine cases with competing
critical turns rank the intervention first. M=16 remains a simulated-policy reference,
not true human action value. M=4 is an exploratory cost/latency setting, not a precision
guarantee. Teammate face-validity ratings on 10 sessions remain uncollected.
