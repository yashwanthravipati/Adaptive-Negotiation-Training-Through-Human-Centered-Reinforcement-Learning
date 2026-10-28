# Checkpoint 2: Adaptive Negotiation Training Through Human-Centered RL

Oct 27, 2026 · @Mahdi Nassereddine

*Yash Ravipati, Mahdi Nassereddine, Vincent Song. CS2822r, Fall 2026.*

## 1. Research question

Our core question is unchanged: **can rehearsing against an adaptive LLM counterpart, followed by move-level feedback, improve how people negotiate in real negotiations?** Building the MVP and the Checkpoint 1 feedback sharpened it in four ways:

- **Scenario-specific rehearsal.** Users upload the materials for the negotiation they are about to have. The system builds the case, a prep brief, and a training plan for it.
- **Hybrid control.** The LLM writes the dialogue. Code enforces the economics, meaning the walk-away value and a concession schedule, because LLM counterparts concede too easily.
- **Counterfactual feedback, after the session only.** We replay the turns that mattered with alternative moves to estimate their value. There are no live move suggestions.
- **The user's state is what we plan over.** We model the user as a structured state with uncertainty (facts known, rapport, errors) and choose where to focus from it (Section 2).

The sub-questions are now:

- **ML-Q1, steering:** do tiers move user score monotonically, and does a chosen focus reliably create the situations it targets (for example, more chances to make a given error)?
- **ML-Q2, user-state inference:** does the belief over facts, rapport, and errors recover traits planted in synthetic negotiators, with calibrated uncertainty?
- **ML-Q3, planning:** does choosing the focus from the belief state fix a user's errors in fewer sessions than greedy, random, or no-focus baselines?
- **RQ1, transfer:** does rehearsal with counterfactual feedback raise real-negotiation scores (z-scored within case and role) against a materials-only control?
- **RQ2, sim-to-real gap:** where does rehearsal behavior differ from real behavior, and is the counterpart's concession curve human-like?

## 2. Formal model: user state, steering, and planning

We keep a belief over a structured user state, pick a focus from it, steer the system toward that focus, and update the belief from what happens. Today's profile (six skill scores shrunk toward neutral) is a coarse first version, and this model replaces it.

**Notation.** There are three nested levels, and each has its own index:

- Turn n inside a rehearsal.
- Session t inside a training run of K = 5 sessions.
- Rollout m inside a credit estimate.

Every symbol used in this section is defined below, and each has one meaning: τ is always a transcript, and a critical turn is written n. A case, a tier, and a focus are concrete data, not descriptions. A case is the record the parser builds. A tier is an index into a fixed table of counterpart settings. A focus is a label that selects entries from fixed lookup tables.

*Case, tier, focus (the setting)*

| Symbol | Type | Meaning |
| --- | --- | --- |
| c | record | A case: every field below, as extracted by the case parser from one upload |
| ℒ\_c = {1, …, L} | finite set | Issues to be agreed, indexed by ℓ |
| 𝒪\_ℓ | finite set | Options for issue ℓ |
| d = (d\_ℓ)\_ℓ∈ℒ | element of 𝒟\_c = ∏\_ℓ 𝒪\_ℓ | A package: one option for every issue. A deal is a package both sides accept |
| Pᵁ\_ℓ, Pᶜ\_ℓ | 𝒪\_ℓ → ℝ | Points that the user's and the counterpart's sheets give each option of issue ℓ |
| Pᵁ(d), Pᶜ(d) | ℝ | Total points of package d: Pᵁ(d) = Σ\_ℓ Pᵁ\_ℓ(d\_ℓ), and likewise for Pᶜ |
| Wᵁ, Wᶜ | ℝ | Walk-away values in points: what each side gets with no deal |
| Pᵁ\_max | ℝ | max { Pᵁ(d) : Pᶜ(d) ≥ Wᶜ }, the most the user can get in a deal the counterpart can accept |
| Bˢʰ, Bᵁ, Bᶜ | text | The shared briefing, and each side's private briefing |
| ℐ\_c | finite set | Key facts of the case, indexed by i. Each fact has a type: own walk-away, own priority on an issue, the counterpart's likely priority on an issue, a tradeable issue, or the counterpart's alternative |
| μ ∈ {1, …, 5} | integer | Tier: an index into the counterpart's tier table |
| g(μ) = (gᵃ, gʳ, gᶠ) | \[0, 1\]³ | The tier's dials, as fractions of the counterpart's range Pᶜ\_max − Wᶜ: opening offer gᵃ, concession per turn gʳ, and the floor gᶠ it never concedes below. Values are set in the counterpart code |
| ℱ\_c = {1, …, J} ∪ ℐ\_c ∪ {ρ} | finite set of labels | Possible focuses: an error type j, a fact i, or rapport |
| f ∈ ℱ\_c | label | Focus. It is a label, not a number. It acts only through the lookup tables η, the feedback order, and the prep callout |
| η(f) | (dial override, rule) | Counterpart hook for focus f: a change to g(μ) from FOCUS\_DIALS plus a behavior rule (hook table below) |
| σ = (c, μ, f) | tuple | Setting. Given σ, the counterpart's seed, and the user's moves, the rehearsal is fully determined |

*Rehearsal*

| Symbol | Type | Meaning |
| --- | --- | --- |
| n = 0, …, N | integer | Turn; N ≤ 20 is the turn on which the rehearsal ends |
| aₙ | (text, formal action) | User move: a message plus at most one formal action, which is to offer a package d ∈ 𝒟\_c, accept the counterpart's standing offer, or walk away |
| rₙ | (text, formal action) | Counterpart reply, in the same form |
| ψₙ | ℝ | Counterpart's schedule state: the lowest Pᶜ it will accept at turn n, computed by code from g(μ), η(f), and n |
| ξₙ = (σ, a₀:ₙ₋₁, r₀:ₙ₋₁, ψₙ) | tuple | Full state at turn n |
| cᵁ = (ℒ\_c, 𝒪, Pᵁ, Wᵁ, Bˢʰ, Bᵁ) | record | The user's half of the case |
| hₙ = (cᵁ, a₀:ₙ₋₁, r₀:ₙ₋₁) | tuple | The user's view at turn n |
| πᵁ\_s(a ∣ h) | distribution | The user's behavior given state s. For a person it is unknown. For a synthetic negotiator it is the scripted user |
| πᶜ\_σ(r ∣ ξ) | distribution | The counterpart: Claude writes the text, and code chooses the formal action so that Pᶜ never falls below ψₙ |
| τ = (a₀, r₀, …, a\_N, r\_N, d\*) | sequence | Transcript. d\* is the agreed package, or ∅ for no deal |
| R(τ) | ℝ, at most 1 | (Pᵁ(d\*) − Wᵁ) / (Pᵁ\_max − Wᵁ) for a deal, and 0 for no deal. It is negative if the user accepts below their walk-away |

*User, belief, planning*

| Symbol | Type | Meaning |
| --- | --- | --- |
| t = 0, …, K−1 | integer | Session; K = 5 |
| j ∈ {1, …, J} | integer | Error type, J = 6, each defined by a detector (detector table below) |
| θⱼ,ₜ | \[0, 1\] | Probability the user makes error j at one opportunity during session t |
| kᵢ,ₜ | \[0, 1\] | Probability the user acts on fact i at one opportunity |
| ρₜ | \[0, 1\] | Probability a user turn builds rapport |
| sₜ = (kₜ, ρₜ, θₜ) | \[0, 1\]^(∣ℐ\_c∣+1+J) | The user's hidden state during session t |
| oⱼ,ₜ, xⱼ,ₜ | integers, x ≤ o | Opportunities for error j in τₜ and occurrences of it, from its detector. Facts and rapport have their own counts oᵏᵢ,ₜ, xᵏᵢ,ₜ and oᵖₜ, xᵖₜ |
| yₜ | tuple | Everything observed from session t: all counts and R(τₜ) |
| Fₜ | text | Feedback report shown after session t |
| Learn | unknown map | How the user changes between sessions: sₜ₊₁ \~ Learn(sₜ, fₜ, Fₜ) |
| δⱼ | \[0, 1\] | Synthetic negotiators only: the fraction of θⱼ that one session focused on j removes |
| α₀, β₀ | > 0 | Prior pseudo-counts of occurrences and non-occurrences |
| λ | (0, 1\] | Forgetting factor applied once per session |
| Xⱼ,ₜ, Oⱼ,ₜ | ≥ 0 | Discounted occurrence and opportunity counts from sessions before t |
| bₜ | parameters | The belief: a Beta(α, β) for every component of sₜ |
| E\_b\[θⱼ\], sd\_b\[θⱼ\] | \[0, 1\] | Mean α/(α+β) and standard deviation √(αβ / ((α+β)²(α+β+1))) of that Beta |
| critical turn | turn index n | A turn where a detector fired or a formal action was taken; the feedback engine replays these |
| M | integer | Rollouts per candidate move (4–5) |
| π̂ᵁ | distribution | User policy inside rollouts (default: the scripted user) |
| Q̂(ξₙ, a), Q̂′(ξₙ, a) | ℝ | Mean R over M rollouts after playing a at turn n; Q̂′ uses fresh seeds |
| Δₙ | ℝ | Points lost at critical turn n relative to the best alternative |
| 𝒞ⱼ | set of turns | Critical turns, over this user's sessions, where error j occurred |
| wⱼ | ℝ | Mean of Δₙ over 𝒞ⱼ: the cost of one occurrence |
| ōⱼ | ≥ 0 | Mean oⱼ,ₜ in sessions focused on j, across users |
| κ | ≥ 0 | Weight on uncertainty in the planner |
| rₜ, V(π) | ℝ | Reward for session t, and its expected sum over K sessions for planner π |

**Rehearsal.** A rehearsal is a partially observed game between the user and the counterpart:

- At turn n the user sees hₙ and plays aₙ \~ πᵁ\_sₜ(· | hₙ).
- The counterpart replies from ξₙ under πᶜ\_σₜ. Code enforces its walk-away value and concession schedule.
- The rehearsal ends with a deal, a walk-away, or at n = 20.

Its score is the user's surplus share, the same `surplus_share` the MVP computes:

```latex
R(\tau) = \begin{cases} \dfrac{P^{U}(d^{*}) - W^{U}}{P^{U}_{\max} - W^{U}} & \text{deal } d^{*} \\[4pt] 0 & \text{no deal} \end{cases}
```

No deal scores 0. Deals with custom terms have no points, so they are left out. R is the only reward inside a rehearsal; there is no judge-based shaping.

**State.** During session *t*, the user's state sₜ has three parts. Each part is a probability. The state is hidden, and we see it only through the transcript τₜ.

| Component | What it captures | Observed from |
| --- | --- | --- |
| Awareness of fact *i*, kᵢ | Own walk-away and priorities, the counterpart's likely priorities, tradeable issues, the counterpart's alternatives | Code (offers below walk-away, issues never raised) and LLM tags on messages |
| Rapport, ρ | Acknowledging the other side, asking about interests, constructive tone | LLM tags per turn, checked against teammate labels |
| Error rate *j*, θⱼ | Conceding first, unreciprocated concessions, anchoring on their number, accepting low, ignoring an issue, logical errors (a package worse for both sides than one already on the table) | Code-detected events per opportunity |

**Detectors.** Each error type is defined by code on the transcript, not by its name.

- A user **concession** is a user offer d with Pᵁ(d) lower than the user's previous offer. Its size is the drop divided by Pᵁ\_max − Wᵁ.
- A counterpart concession is defined the same way, using Pᶜ.

| j | Error | Opportunity (adds 1 to oⱼ,ₜ) | Occurrence (adds 1 to xⱼ,ₜ) |
| --- | --- | --- | --- |
| 1 | Conceding first | Each user concession | The counterpart has made no concession yet |
| 2 | Unreciprocated concession | Each user concession after the user's first | The counterpart has not conceded since the user's previous concession |
| 3 | Anchoring on their number | The user's first offer, if the counterpart has already offered some dᶜ | Pᵁ(user's offer) < ½ (Pᵁ(dᶜ) + Pᵁ\_max) |
| 4 | Accepting low | Each acceptance by the user | R(τ) < 0.25 |
| 5 | Ignoring an issue | Each issue ℓ whose options the user's sheet scores differently, once per rehearsal | The user never changes d\_ℓ across their offers and is never tagged as raising ℓ |
| 6 | Logical error | Each user offer d | Some package already offered by either side gives both sides at least as many points as d, and one side strictly more |

Thresholds for j = 3 and j = 4 are proposals and need team agreement.

Facts and rapport are counted by fact type:

- **Own walk-away.** Every user offer or acceptance is an opportunity. It counts as acted on when Pᵁ ≥ Wᵁ.
- **Other fact types.** Every user turn is an opportunity. It counts as acted on when Claude tags the turn as using the fact.
- **Rapport.** Every user turn is an opportunity. It counts when Claude tags the turn as building rapport.

The tagging prompt uses a fixed rubric, checked against teammate labels on 20 transcripts.

**Hooks.** The focus acts only through the lookup η(f). The table below is proposed; only the dial overrides already exist in FOCUS\_DIALS.

| Focus f | Counterpart behavior rule |
| --- | --- |
| 1, conceding first | Makes no concession until the user has conceded or 6 turns have passed |
| 2, unreciprocated concession | Answers the user's second and later concessions with no concession, half the time |
| 3, anchoring on their number | Opens at gᵃ = 1, its most extreme offer, before the user offers |
| 4, accepting low | Offers a package with R between 0 and 0.25 early, then holds it for two turns |
| 5, ignoring an issue ℓ | Never raises ℓ itself, and holds its least-preferred option on ℓ fixed |
| 6, logical error | Puts two multi-issue packages on the table early, so dominated offers are possible |
| fact i | Reveals the information behind i only when the user asks about it |
| ρ, rapport | Its per-turn concession gʳ doubles on the turn after a rapport-tagged user turn |

Facts come from the parsed case, so each upload gets its own list. Each detector defines an opportunity event and an occurrence event on a transcript. Given the state, occurrences of error *j* are binomial in its opportunities:

```latex
x_{j,t} \mid o_{j,t},\, \theta_{j,t} \;\sim\; \mathrm{Binomial}\left(o_{j,t},\; \theta_{j,t}\right)
```

**Belief.** The belief bₜ has one Beta posterior per component. It is built from counts summed over past sessions, with a forgetting factor λ:

```latex
\theta_j \mid y_{0:t-1} \;\approx\; \mathrm{Beta}\left(\alpha_0 + X_{j,t},\; \beta_0 + O_{j,t} - X_{j,t}\right), \qquad X_{j,t} = \sum_{t' < t} \lambda^{\,t-1-t'} x_{j,t'}, \quad O_{j,t} = \sum_{t' < t} \lambda^{\,t-1-t'} o_{j,t'}
```

The mean says how likely the problem is, and the spread says how sure we are.

- **Forgetting.** With λ = 1 this is the exact posterior for a fixed θⱼ. But the plan assumes θⱼ falls with practice, and λ < 1 lets the belief follow that. We choose λ on synthetic negotiators (ML-Q2).
- **Awareness and rapport** use the same form. For fact *i* and rapport, opportunities and occurrences are counted as described under Detectors.

**Learning.** Between sessions the user changes: sₜ₊₁ \~ Learn(sₜ, fₜ, Fₜ). We never observe Learn directly. Synthetic negotiators implement it as θⱼ,ₜ₊₁ = θⱼ,ₜ (1 − δⱼ · 𝟙\[fₜ = j\]), where δⱼ is each negotiator's own response to focused practice and can be zero.

**Credit assignment (feedback engine).** At a critical turn *n* of τₜ, the rollout engine restarts from the full state ξₙ, not the user's view hₙ, because the counterpart's replies depend on its private sheet. It plays an alternative move *a* in place of aₙ. It then continues to the end with a fixed rollout user policy π̂ᵁ against πᶜ\_σ. Alternatives are drawn from the moves open to the user at hₙ, and each gets *M* rollouts:

```latex
\hat{Q}(\xi_n, a) = \frac{1}{M} \sum_{m=1}^{M} R\left(\mathrm{rollout}_m(\xi_n, a;\, \hat{\pi}^{U}, \pi^{C}_{\sigma})\right), \qquad \hat{a} = \arg\max_{a} \hat{Q}(\xi_n, a), \qquad \Delta_n = \hat{Q}'(\xi_n, \hat{a}) - \hat{Q}'(\xi_n, a_n)
```

- **Q̂ depends on the rollout policy.** It is a value under π̂ᵁ, not under optimal play, so each experiment states which π̂ᵁ it uses. The default is the scripted user.
- **Fresh rollouts for scoring.** One batch picks the best move â, and a fresh batch Q̂′ scores both â and aₙ. Reusing the first batch would inflate Δₙ, because the max picks whichever estimate got lucky.
- **Hindsight labels.** An alternative that is good only given the counterpart's private sheet is labeled hindsight in the feedback.

Averaging Δₙ over the critical turns where error *j* occurred, across this user's sessions, gives *w*ⱼ: the points each occurrence of that error costs. Until error *j* has been seen, *w*ⱼ is its population average. It tells the planner which errors are worth fixing.

**Actions (steering).** The planner's action in session *t* is a focus fₜ: one state component (an error θⱼ, a fact kᵢ, or rapport ρ). The focus sets the setting σₜ through three levers. Steering can be tested on its own (ML-Q1): under focus *f*, the expected opportunity count o\_f,ₜ should be higher than with no focus.

1. **Counterpart:** dials plus a hook that creates the situation. For example, it reveals its priorities only when asked, anchors hard, or concedes late.
2. **Feedback:** the report leads with the moments tied to *f*.
3. **Prep:** the brief calls out the related facts and errors.

**Planning.** The planner faces a POMDP, and bₜ is its approximate filter:

| Part | Here |
| --- | --- |
| Hidden state | sₜ |
| Action | the focus fₜ |
| Observation | yₜ |
| Transition | Learn |
| Horizon | K = 5 sessions |

The reward for session *t* is the drop in the user's true expected cost per session from errors. Each error's cost is weighted by *w*ⱼ and by ōⱼ, the expected number of opportunities per session:

```latex
r_t = \sum_j w_j\, \bar{o}_j \left(\theta_{j,t} - \theta_{j,t+1}\right), \qquad V(\pi) = \mathbb{E}\left[\sum_{t=0}^{K-1} r_t\right]
```

The reward uses the true θ, not the belief's mean. Paying for a drop in the mean would reward the planner for moving its own estimate rather than for the user improving. True θ is known only for synthetic negotiators, so rₜ is computed only there. For LLM and real users, we report the counts and R.

With about 5 sessions per user, solving the POMDP exactly is not justified. We start with an upper-confidence rule on each error's expected cost per session. The rule targets problems that are likely, costly, frequent, and still uncertain:

```latex
f_t = \arg\max_j \; w_j\, \bar{o}_j \left(\mathbb{E}_{b_t}[\theta_j] + \kappa\,\mathrm{sd}_{b_t}[\theta_j]\right)
```

The bonus sits inside the cost, so both terms are in points per session; κ is tuned on synthetic negotiators. Facts and rapport enter the same way: 1 − kᵢ and 1 − ρ replace θⱼ, each with its own w and ō.

ML-Q3 compares this rule with greedy-on-the-mean (today's curriculum), random focus, and no focus. The test uses synthetic negotiators with known states whose error rates fall after targeted practice. The metric is sessions until every planted error is below a threshold, measured on rehearsals with no focus or hook so that a planner cannot look good by choosing easy settings.

&#91;embedded content: Training loop: belief state, focus, steering, session, observations, update\]

The planner is the part we study in ML-Q3. Steering (ML-Q1) and belief updates (ML-Q2) are its inputs, and each can be tested on its own first.

## 3. What we have completed

We have a working MVP that covers all five workflow stages. It is a local Streamlit app (`negotrain`, branch `MVP`) with 93 offline tests. The flow is **upload case files → prep brief and plan → rehearse → post-session feedback → profile and next scenario → log the real outcome**. Everything is stored locally, with no sign-in.

| Component | What it does |
| --- | --- |
| Case parser | Builds a structured case (issues, options, points, walk-away values) from PDF, Word, text, or ZIP uploads. If the counterpart's sheet is missing, it infers a labeled estimate. |
| Prep brief and plan | Writes an overview, interests, walk-away, and a checklist, plus a warm-up → realistic → stretch training plan |
| Hybrid counterpart | LLM dialogue in character, a code-enforced concession schedule and walk-away, and five difficulty tiers |
| Rehearsal UI | Chat with formal offer cards, accept, walk away, and unscored custom terms |
| Counterfactual feedback | Replays critical turns with alternative moves and writes a coaching report after the session |
| Profiling and curriculum | Skill scores from behavioral features, and rule-based choice of tier and focus |
| Real-negotiation log | Records the real outcome and compares it with rehearsals |

It runs on the local Claude Code CLI, the Anthropic API, or fully offline with a rule-based counterpart.

## 4. How the tool has done

## 5. What we keep and what we change

We keep the architecture, recalibrate the counterpart, and replace the skill-score profile with the user state from Section 2.

**Keep**

- **Hybrid counterpart:** 0 walk-away violations offline, 0 leaks or fallbacks live, and tier controls difficulty.
- **Scenario-specific rehearsal:** uploads recover the case exactly, and the brief and plan are built on the user's own negotiation.
- **Post-session-only counterfactual feedback** and strict information hiding.

**Change**

| Change | Why | Target |
| --- | --- | --- |
| Belief over fact awareness, rapport, and error rates, counted per opportunity; LLM tags validated against teammate labels | Checkpoint 1 feedback; today's profile drops uncertainty | ML-Q2 |
| A counterpart hook for each focus; test steering by counting opportunities | Steering by focus is untested | ML-Q1 |
| Upper-confidence planner vs greedy, random, and no-focus baselines | The curriculum ignores uncertainty and cost | ML-Q3 |
| A visible deadline, with the counterpart conceding faster as it nears | Firm users reached 0% agreement at tiers 2–5 | Before the pilot |
| Gate tier 5, and aim feedback at early concessions | Soft users hit their walk-away at tier 5 | Before the pilot |
| Decouple concession rate from the concession floor, then re-sweep | Not monotone (ρ = 0.7) | ML-Q1 |
| 4–5 rollouts per alternative with confidence intervals, used to estimate error costs *w*ⱼ | n = 2 is too noisy | Feedback |
| A sweep with the LLM counterpart: about 400 calls, about $10 | The stress test was rule-based only | ML-Q1 |
| Human-vs-human mode for real trials | No human opponents yet | Pilot |

**Next steps.** First the belief-state profile and the counterpart fixes. Then the ML-Q1 to ML-Q3 simulation experiments, which need no recruiting. In parallel we finish the protocol and human-vs-human mode for a mid-November pilot: 12–20 participants, treatment vs a materials-only control, and 5 real negotiations each.
