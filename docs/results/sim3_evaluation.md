# sim3 virtual-user evaluation

2026-10-28. This experiment evaluates the reimplemented coach on the supplied sim3
negotiation. It does **not establish that the coach improves human negotiation**.

## Main finding

The economic controller produces monotonically harder tiers and obeys its schedule in
all 7,960 primary offline sessions. The adaptive planner does **not** improve held-out
negotiation score in the grounded scripted population: mean gain −0.0059, 95% user-bootstrap
interval [−0.0163, 0.0046]. Abstract Binomial learning experiments improve their own
true-state error-cost objective. These objectives and populations must not be conflated.

All eight live Anthropic personas completed 280 episodes. Adaptive practice improved
held-out G by 0.0871 [0.0606, 0.1117], but its advantage over the no-focus coaching
control was only 0.0085 [−0.0303, 0.0436]. Thus this exploratory cohort does **not**
establish an advantage from adaptive targeting. It does show a positive paired difference
against random focus, under the limitations below.

![Evaluation](../../results/sim3/evaluation.svg)

## Case and assumptions

Source: `data/cases/sim3`, containing 28 supplied Word documents. The local projection
is `data/cases/private/sim3_inferred.json`; both originals and that projection remain
untracked. The user role is the Border Authority Officer. There is no supplied official
point table, numeric walk-away value, or private Mayor sheet. We therefore use an explicitly
inferred finite approximation: six issues, three options each, 729 complete packages.
The Mayor's briefing is inferred from public material only. Each live actor receives only
its own role sheet and the public brief; post-session feedback can label hindsight advice.

**Every numeric utility and both walk-away values are analyst assumptions.** They are not
class grading criteria or a judgment about the value of people. Legal/institutional and
cross-issue feasibility are simplified; the case has no modeled stochastic enforcement
or factual resolution of contradictory public claims. Numerical performance is conditional
on this approximation. The sensitivity analysis changes the assumptions without claiming
to resolve these limits.

[The numeric surrogate](../../results/sim3/numeric_case.json) exposes only invented
utilities and generic option labels, without source text. It reproduces the scripted
experiment's economics; two users × four policies were checked for exact equality to
the primary results. It is **not** a substitute for the source brief in live evaluation.
The private manifest records source hashes; each experiment records its case/source hash.

## Design

| Split / experiment | Independent users | Purpose |
| --- | ---: | --- |
| Cost calibration | 8 | Population costs and focused opportunity rates |
| Development | 64 | Choose forgetting λ and uncertainty bonus κ |
| Exact Binomial test | 512 | Known-state learning and posterior diagnostics |
| Steering | 32 | Paired tier and focus comparisons |
| Grounded recovery | 64 | Five sessions, then 30 independent reference sessions |
| Grounded learning | 128 | Four policies, five rehearsals each |
| Utility sensitivity | 64 per variant | Four alternative inferred score tables |
| Live LLM test | 8 completed | Same four-policy training/probe design; 280 episodes |

Random errors, awareness and rapport start from Beta(2,2). Each error response δ has a
15% mass at zero; otherwise it is uniform on [0.2,0.65]. For scripted learners, a focused
error's propensity is multiplied by 1−δ. Fact or rapport practice removes 30% of the
corresponding deficit; this is an experimental assumption. LLM personas instead receive
actual preparation callouts and previous coaching: their tendencies are not manually
improved. Neither population is calibrated to human behavior.

Training uses tiers (2,2,4,4,4). G is the average terminal surplus share over held-out
tiers (1,3,5), with no focus, hook or new feedback during the probes. Both before and
after probes use the same fixed seed per scripted user. The case is shared with training:
this is **tier generalization within sim3**, not held-out-case generalization. Prior
coaching remains in LLM users' memory during post-training probes. No-focus still receives
a post-session report; it is a no-targeting control, not a no-feedback control.

All comparisons pair the same sampled user across policies. Intervals use 2,000 bootstrap
resamples of users, not independent resamples of their turns. LLM sampling is not seedable;
paired personas reduce heterogeneity but do not supply identical model randomness.
Development selected λ=0.5 and κ=0. Thus the tuned adaptive rule **equals greedy** on the
same observations. This experiment cannot establish an advantage from an uncertainty bonus.
The grid was tuned on the error-only oracle; the full-action diagnostic and grounded/live
tests retain that tuning without inspecting their test results.

## ML-Q1: steering

| Tier | Mean R | 95% interval | Agreement rate |
| --- | ---: | --- | ---: |
| 1 | 0.559 | [0.478, 0.638] | 100% |
| 2 | 0.501 | [0.425, 0.576] | 100% |
| 3 | 0.415 | [0.328, 0.503] | 100% |
| 4 | 0.266 | [0.212, 0.335] | 100% |
| 5 | 0.224 | [0.183, 0.278] | 100% |

Spearman correlation between tier and mean R is −1. This demonstrates tier ordering in
this population, not human realism. All 7,960 primary offline episodes had zero counted
schedule violations. A high agreement rate alone does not show that bargaining is realistic.

Focus steering is mixed. Accepting-low opportunities increased by 0.188/user
[0.031, 0.344], while logical-error opportunities decreased by 2.156 [−3.781, −0.875].
Conceding-first, unreciprocated-concession and anchoring opportunity differences included
zero. Ignoring-issue opportunities are six per completed annotated session by definition;
the hook cannot increase that fixed count. Fact/rapport opportunities count turns, so
revealing information does not necessarily increase their opportunity count either.

These are failures/limits of the proposed opportunity-uplift criterion, not grounds to
change detector definitions after seeing results. The package hooks log availability;
`hook_application_rate=0` in the original steering artifact for other hooks means **no
package-hook telemetry**, not a 0% implementation rate. New runs report null for that case.

## ML-Q2: inference

The scripted policy's Bernoulli knobs attempt actions but are **not** guaranteed to equal
conditional detector probabilities. Overlap, acceptance, feasibility and observed opponent
movement couple behavior. Grounded recovery therefore compares posteriors with empirical
rates from 30 additional no-focus sessions per user, not with the knobs as if they were θ.

| Error | RMSE vs reference | 95% interval coverage of reference | Knob vs realized Spearman |
| --- | ---: | ---: | ---: |
| Conceding first | 0.249 | 92.2% | 0.115 |
| Unreciprocated concession | 0.331 | 65.6% | 0.279 |
| Anchoring | 0.239 | 90.6% | 0.879 |
| Accepting low | 0.237 | 93.8% | 0.789 |
| Ignoring an issue | 0.095 | 98.4% | 0.987 |
| Dominated offer | 0.159 | 82.8% | 0.341 |

The unreciprocated-concession posterior is especially poorly calibrated. Ignoring-issue
estimates are more informative. Rapport coverage of the Monte Carlo reference is 78.1%,
with RMSE 0.135. Asking about interests also counts as rapport, so the raw rapport knob
cannot be interpreted independently of awareness in this policy.

[Expanded diagnostics](../../results/sim3/validation/recovery_all.json) include every fact,
rapport, split-half correlations, and AUC against reference rate ≥0.5. AUC can be undefined
or unstable when one class is absent/rare; it is not evidence of accuracy in that case.
Reference rates themselves have Monte Carlo error, so the coverage numbers are diagnostics,
not exact frequentist coverage against known truth. Human tagging agreement is unmeasured.

In the separate error-only Binomial oracle, the adaptive posterior has MSE 0.0311 and
96.8% empirical coverage. Discounting the prior as in report.tex instead gives MSE 0.0456
and 95.2% coverage. This supports separating the two recursions, not claiming universally
calibrated uncertainty from synthetic oracle success.

## ML-Q3: planning and held-out competence

| Policy | Grounded G gain, 128 users | 95% interval |
| --- | ---: | --- |
| Adaptive (κ=0) | −0.00592 | [−0.01634, 0.00462] |
| Greedy | −0.00592 | [−0.01634, 0.00462] |
| Random focus | 0.00391 | [−0.00456, 0.01296] |
| No focus | 0 | [0, 0] |

Adaptive minus random is −0.00982 [−0.02243, 0.00219]. Baseline G is 0.3677. The zero
no-focus gain is expected from the stipulated synthetic Learn rule and paired seeds; it
is not an empirical estimate of how real users learn without targeting. The adaptive
policy spent 347/640 rehearsals on the welfare-priority fact. Estimated fact costs and
opportunity frequency can dominate error-focused practice. Credit is associated with all
co-occurring deficits, so these costs must not be interpreted as isolated causal effects.

The error-only exact oracle produces true weighted error-cost reductions of 0.5893
[0.5604,0.6157] for adaptive/greedy versus 0.3238 [0.3044,0.3435] for random. With all
27 error/fact/rapport actions available, the corresponding reductions are 0.4240
[0.3960,0.4499] versus 0.0864 [0.0746,0.0979]. No-focus is zero. Oracle rewards use
actual planted probabilities, never posterior changes, and are **not G gains**.

No error-only oracle user reached the all-six-errors-below-0.25 threshold within five
rehearsals. Sessions-to-threshold is right-censored at 6 for all users; therefore this
study provides no evidence for faster complete mastery under that demanding endpoint.

### Diagnostic: error-only action space

An exploratory ablation keeps the same 128 users, costs, tuning and tier schedule but
restricts practice targets to the six errors. Adaptive G gain is −0.02492
[−0.04712, −0.00212], and adaptive minus random is −0.03829
[−0.06031, −0.01663]. This does not rescue competence gain: fact-focused attention alone
is not an adequate explanation. The scripted learning transitions and counterfactual
costs do not reliably align error reduction with terminal negotiation return. These are
unadjusted diagnostic comparisons, not a new tuned production policy.

### Sensitivity to inferred economics

Costs and tuning remain fixed at primary calibration; 64 matched users per variant.
Walk-away shifts are ±10% of each role's own range. Two independent log-normal issue
weight perturbations (σ=0.2) preserve each role's maximum points.

| Assumption change | Adaptive G gain | 95% interval |
| --- | ---: | --- |
| Lower walk-aways | −0.00900 | [−0.02197, 0.00322] |
| Higher walk-aways | 0.00258 | [−0.01131, 0.01645] |
| Issue weights, draw 1 | −0.00647 | [−0.02440, 0.00924] |
| Issue weights, draw 2 | −0.02184 | [−0.04394, −0.00106] |

There is no demonstrated adaptive gain under these changes, and one variant is harmful.
These are exploratory, unadjusted intervals; they do not cover every plausible scoring
model or establish robustness beyond the tested perturbations.

## Live LLM personas

All eight originally sampled users finished all four policies: 24 shared baseline probes,
160 training episodes and 96 post-training probes. None were replaced after a failed
request. Opus 5.5 supplies counterpart dialogue and coaching; Sonnet 5.5 supplies user
dialogue and annotations. Numeric counterpart actions remain code controlled, and
counterfactual rollouts use the free rule-based simulator with M=4 and at most three
critical turns. There were zero schedule violations across all 280 live episodes.
Baseline mean R fell from 0.506 at tier 1 to 0.438 at tier 3 and 0.199 at tier 5
(Spearman −1); each policy's 40 training episodes had 100% agreement.

| Policy | Baseline G | Final G | G gain | 95% interval for gain |
| --- | ---: | ---: | ---: | --- |
| Adaptive (κ=0) | 0.38068 | 0.46780 | 0.08712 | [0.06061, 0.11174] |
| Greedy | 0.38068 | 0.44792 | 0.06723 | [0.03693, 0.09754] |
| Random focus | 0.38068 | 0.43561 | 0.05492 | [0.02652, 0.08428] |
| No focus | 0.38068 | 0.45928 | 0.07860 | [0.04640, 0.12027] |

Adaptive minus random gain is 0.03220 [0.01799, 0.04830]; adaptive minus no focus is
0.00852 [−0.03030, 0.04356]. Adaptive minus greedy is 0.01989 [−0.00189, 0.04072].
Because κ=0, the latter compares two stochastic runs of the same selection rule; it
cannot support an uncertainty-bonus benefit. These are exploratory, unadjusted comparisons
with only eight independent personas. The no-focus group also receives coaching, so the
positive before/after gains cannot isolate coaching from practice, model variation or
retained feedback. They do not measure human learning or generalization to another case.

The live cohort resumed from saved turns after API/structured-output failures. Output
bounds, explicit system-prefix caching and annotation correction were repaired during the
run; source hashes and recovery records preserve this history. No saved completed episodes
were regenerated or personas resampled. This mixed runtime history is an additional
limitation, not a clean fixed-version replication. The final aggregation reused all saved
episodes and feedback and made zero API calls.

Numeric [policy results](../../results/sim3/live-v1/training.json),
[paired user rows](../../results/sim3/live-v1/training_rows.json), and
[episode diagnostics](../../results/sim3/live-v1/sessions.json) are public. Source materials,
private briefs, full dialogue and coaching text remain in ignored local files.

## Token caching and final cost

The gateway uses automatic message caching and an explicit ephemeral breakpoint on the
stable system prompt. The latter was added during recovery; earlier episodes used only
automatic caching. Provider usage confirms **4,036,684 cache-read input tokens**:
1,250,063 Opus and 2,786,621 Sonnet. Cache writes and reads are charged at their respective
rates and included in the ledger; enabling caching does not imply every prompt hits.

Across 2,679 requests, including pilot, failed and recovery calls, known token usage cost
is **$65.34272**. Nine earlier uncertain requests retain their entire **$68.09216** reserved
upper bound, giving a conservative total of **$133.43488**. This is not a claim that those
unknown requests were billed at their full bound. No active requests remain. The user
explicitly increased the cumulative cap from $150 to **$200** on 2026-10-28; the audited
change preserves all previous charges and reservations across process restarts. See the
complete [API and cache accounting](../../results/sim3/api_usage.json).

## Counterfactual validity

Twelve independent steering sessions supplied 26 critical-turn estimates. Compared with
M=16, M=4 had rank correlation 0.839, mean absolute difference 0.0198 R, and 96.2% sign
agreement; M=5 gave 0.863, 0.0177 R, and 96.2%. Both selection and scoring use separate
seeds; actual and selected moves share fresh scoring seeds. Negative deltas are retained.

All 12 planted early acceptances had positive estimated loss (mean 0.290 R,
[0.239,0.341]); all nine with competing critical turns ranked first. The three single-turn
cases provide no ranking discrimination. M=16 is still a model-based Monte Carlo reference,
not ground truth, and no teammate face-validity ratings have been collected. M=4 remains
an exploratory latency/cost choice rather than a precision guarantee.

## Reproduction

Run from the project directory with the existing virtual environment. These commands make
no API calls. The public numeric surrogate reproduces offline economics under a different
case hash and generates fresh local raw artifacts for the subsequent diagnostics:

```bash
python scripts/evaluate.py --case results/sim3/numeric_case.json \
  --output results/sim3/reproduction --users 128 --calibration-users 8 \
  --steering-users 32 --recovery-users 64 --reference-sessions 30 \
  --oracle-users 512 --development-users 64
python scripts/validate_evaluation.py --case results/sim3/numeric_case.json \
  --input results/sim3/reproduction --output results/sim3/reproduction-validation
```

The oracle and error-only diagnostic use the committed public calibration/numeric inputs.
Choose a new output directory when source code changes; existing experiments retain their
original configuration hashes.

```bash
python scripts/oracle_action_space.py
python scripts/ablate_focus_space.py --output results/sim3/reproduction-errors-only
```

`python scripts/report_evaluation.py` regenerates the original figures and episode
summaries. It requires the private case and ignored raw artifacts, which are deliberately
absent from a public checkout. Exact original case/source hashes also require that case.

The live command sends the private fictional role material to Anthropic and costs money;
the user explicitly authorized it for this evaluation:

```bash
python scripts/evaluate.py --live --stage training --users 8 --workers 4 \
  --calibration-from results/sim3/offline-v1 --output results/sim3/live-v1
```

Full-context reservations in `.api-budget.sqlite3` enforce the current cumulative $200 cap.
New ledgers default to $150; an explicit, recorded `set_authorized_limit` changes the cap.
Opening an existing ledger preserves its cap; request reservations cannot raise it. Never
delete/reset the ledger to resume. Raw private transcripts are checkpointed after every
turn in ignored `raw/` directories. Public outputs contain numeric observations, seeds,
configuration, model names and source hashes. Runtime repairs are recorded in
`live-v1/runtime_revisions.json`; an explicit `--resume-note` is required to preserve an
existing cohort across a source-code change. SDK retries/model fallback are disabled;
one separately reserved retry is allowed for a known truncated structured response.
An incomplete annotation batch gets one correction attempt before failing; labels are
applied atomically only after all supplied user indices and fact/issue IDs validate.
`api_usage.json` aggregates the entire durable ledger, including pilot, restart and failed
requests; individual `usage.json` files describe their own process only.

## What remains unestablished

Human transfer, a human-like concession curve, teammate tag agreement, broader case
transfer, an advantage of κ>0, and reliable mastery within five rehearsals are unestablished.
Human-vs-human study infrastructure/recruitment and participant studies remain future
project tasks. Simulation evidence cannot mark those tasks complete. The implementation
and experiment report preserve these negative and missing results rather than claiming
the research hypothesis has been proven.
