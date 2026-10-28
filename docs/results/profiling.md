# Profiling validation

The [sim3 evaluation report](sim3_evaluation.md#ml-q2-inference) describes the design,
per-error recovery and calibration failures. Machine-readable diagnostics for all 27
components are in [recovery_all.json](../../results/sim3/validation/recovery_all.json),
including class counts for AUC and split-half Spearman correlations.

Ignoring-issue recovery is the strongest result (RMSE 0.095, split-half correlation 0.867).
Unreciprocated-concession coverage is 65.6%, and its split-half correlation is only 0.282.
AUC refers to independent Monte Carlo reference rates, not to the scripted action knobs;
they are not interchangeable. Human predictive validity and teammate tag agreement have
not been evaluated.
