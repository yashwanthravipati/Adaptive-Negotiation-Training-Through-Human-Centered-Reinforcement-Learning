# Project Plan

*Adaptive Negotiation Training Through Human-Centered RL. CS2822r, Fall 2026.
Yash Ravipati, Mahdi Nassereddine, Vincent Song.*

This is the strategy document: what we are building, how we will know it works, and the
order we will do it in. Day-to-day work lives in [`tasks/`](tasks/) (see
[`README.md`](README.md) for the workflow). Change this file when the strategy changes,
and record why in [`decisions/`](decisions/).

---

## 1. Goal and deliverables

**One line:** an LLM-driven rehearsal environment that trains *people* to negotiate. It plays
the other side with controllable behavior, adapts to the negotiator, and gives turn-level
feedback via counterfactual credit assignment.

What "done" means for the class:

1. **A working system** that covers the five workflow stages (onboarding, personalization,
   strength and weakness analysis, coaching and feedback, tailored scenario generation), at
   least at MVP depth.
2. **Two ML results:**
   - **ML-Q1, adaptive difficulty:** evidence that counterpart behavior (difficulty,
     cooperativeness, aggression, anchoring, concession) is controllable, measured with
     agent-vs-agent experiments.
   - **ML-Q2, user profiling:** evidence that inferred strengths and weaknesses are accurate
     and meaningful, measured with synthetic negotiators that have known weaknesses, plus
     reliability checks on human data.
3. **A pilot human study** addressing RQ1 (does practice with move-level feedback improve
   real outcomes?) and RQ2 (what limits sim-to-real transfer?), with sustained behavior
   change across five trials.
4. **Checkpoint 2, final report, final presentation.**

## 2. Assumptions to confirm this week

These shape the whole schedule. Each one has a task.

| Assumption | If wrong | Task |
|---|---|---|
| Checkpoint 2 is around Nov 13; final deadline around Dec 10 | Re-plan milestones; walk the descoping ladder (§9) | T-002 |
| We use Claude (`claude-opus-5-5`) through `negotrain.llm`, with enough credits | Swap the provider in `llm.py` only; re-estimate costs | T-003 |
| We can recruit classmates or friends, and no full IRB review is needed for a class project | Shrink to a within-team or friends pilot; frame human results as formative | T-007 |
| "Real" trials can be human-vs-human negotiations we run in the app (or class exercises whose outcomes we can collect) | Collect outcomes through a form; behavior analysis then needs transcripts by another route | T-007, T-015 |
| Class case materials are licensed for class use only | Keep them in `data/cases/private/` (gitignored); commit synthetic cases only | T-005 |

## 3. Scope: MVP vs stretch

| Workflow stage | MVP (must have) | Stretch |
|---|---|---|
| 1. Onboarding | Participant id, consent, pre-survey, a baseline negotiation | Short skills self-assessment |
| 2. Personalization | Assigned case and role; counterpart tier chosen from the profile | Free-form user goals |
| 3. Strengths and weaknesses | Behavioral features, then a profile with uncertainty (T-024, T-025) | Learned profile model |
| 4. Coaching and feedback | Post-session report with counterfactual "moments that mattered" (T-021, T-023) | Natural-language what-if exploration |
| 5. Scenario generation | Rule-based selection of case, tier, and dial emphasis (T-027) | LLM-generated case variants |
| Counterpart | Hybrid: prompt plus code-enforced concession schedule (T-010 to T-012) | Calibrated to human data (T-018) |
| Real trials | Human-vs-human mode in the app (T-015) | Rehearsal-vs-real debrief (T-028) |

**Product principle (decision 0002):** no live move recommendations during a negotiation.
Feedback comes after the session. The project argues for building skill rather than
dependence, so the tool must not do the negotiating for the user.

## 4. System overview

```
case text --parser--> Case (issues, options, points, reservation values)
                        |
   profile -> curriculum picks (case, role, counterpart tier + dials)
                        |
   user <--> Streamlit UI <--> CounterpartAgent (hidden sheet + behavior profile,
                        |                         code-enforced concession schedule)
                        v
                    Session (turns + structured offers) --> SessionStore
                        |
          +-------------+---------------+
          v                             v
   feedback: critical turns ->    profiling: features ->
   counterfactual rollouts ->     negotiator profile ----> curriculum (next scenario)
   coaching report
```

Details and module ownership: [`docs/architecture.md`](../docs/architecture.md).

## 5. Research questions, experiments, and metrics

### ML-Q1: Can we steer the counterpart's behavior? (T-011, T-012, T-016, T-017, T-018)
- **Setup:** counterpart vs simulated users (scripted policies plus LLM personas), at least
  10 episodes per setting, sweeping each dial and each tier.
- **Metrics:** opening-offer extremity (% of the counterpart's range), mean concession per
  turn, turns to agreement, agreement rate, counterpart surplus, user score, disclosure
  (LLM-judged).
- **Success:** monotone dial-to-metric relationships (Spearman ρ), low cross-talk between
  dials, user score falling as tier rises. Compare prompt-only with hybrid control.
- **Human-likeness (RQ2):** compare concession curves and agreement rates with human data
  (our human-vs-human sessions; CaSiNo or CraigslistBargain if useful). Expect the
  prompt-only counterpart to concede more than people.

### ML-Q2: Can we infer a negotiator's strengths and weaknesses? (T-024 to T-026)
- **Synthetic recovery:** simulated negotiators with injected traits (concedes early, weak
  anchor, never asks questions, over-aggressive), 5 sessions each. Does the profiler
  recover the traits? Per-trait AUC or precision and recall.
- **Reliability:** split-half agreement of profiles across sessions.
- **Validity on humans:** profile from sessions 1-3 predicts behavior in sessions 4-5;
  agreement with teammate labels on 20 transcripts (Cohen's κ).

### Credit assignment validity (T-020 to T-022)
- **Method:** at each critical user turn, fork, try K alternative actions, run N rollouts
  each, and compare expected scores (bootstrap CIs).
- **Checks:** estimate stability vs N; planted blunders rank at the top; teammates agree
  the flagged moments matter.
- **Caveat to discuss in the report:** rollouts use a simulated user, so the estimates
  inherit its biases. We condition it on the user's own style to reduce this.

### RQ1 and RQ2 human study (T-030 to T-035, T-040, T-041); see §7.

## 6. Milestones and timeline

Dates are assumptions until T-002 lands. Today is Sat Oct 24; Thanksgiving break is about
Nov 25-29.

| Milestone | Dates | Exit criteria |
|---|---|---|
| **M0 Foundations** | Oct 24 - Oct 30 | Deadlines, provider, and study logistics confirmed (T-002, T-003, T-007); parser ported; 3+ cases with gold JSON |
| **M1 Core rehearsal loop** | Oct 31 - Nov 13 | Counterpart v1 plus hybrid schedule; Streamlit UI; human-vs-human mode; simulation harness; controllability results; **Checkpoint 2** |
| **M2 Feedback and profiling** | Nov 9 - Nov 25 | Counterfactual engine validated; coaching report in UI; features, profile, and profiling validation; scenario selection |
| **M3 Pilot study** | Protocol by Nov 6; pilot Nov 13-15; trials Nov 16 - Dec 4 | Study run; data exported and checked |
| **M4 Analysis and write-up** | Dec 1 - final deadline | Sim2real and behavior-change analyses; final report; presentation |

**Critical path:** T-007 (study logistics), then T-030 (protocol), then T-033 (recruiting),
then T-034 (five trials need about 3 weeks). The study must start by about Nov 16, which
means the UI (T-014) and human-vs-human mode (T-015) must be usable by Nov 13. The study
can begin with end-of-session feedback and switch on counterfactual feedback once T-022
passes; record the switch date and treat it as a covariate.

## 7. Human study design (pilot)

- **Participants:** 12-20 (classmates or friends), consented, pseudonymous ids.
- **Conditions (between subjects, randomized, counterbalanced by role):**
  - *Treatment:* rehearse the upcoming case with the tool (adaptive counterpart, then the
    coaching report), about 20 minutes.
  - *Control:* the same prep time with the case materials only.
- **Trials:** 5 real negotiations, about 2 per week, each a human-vs-human session on a
  case from the library. The treatment participant faces either a control participant or
  another treatment participant; analysis normalizes within case and role.
- **Primary outcome (RQ1):** real-negotiation points z-scored within case and role,
  treatment vs control.
- **Secondary outcomes:** agreement rate, efficiency (joint points / max), surplus over
  walk-away value.
- **Behavior change:** rate of flagged errors (early concession, weak anchor, accepting
  below aspiration, failing to trade across issues, over-aggression leading to impasse)
  across trials 1-5, treatment vs control.
- **RQ2 (sim-to-real gap):** per participant, rehearsal-predicted vs actual counterpart
  behavior and outcome; aggregate where simulation was too easy.
- **Surveys:** pre/post negotiation self-efficacy, perceived realism of the counterpart,
  usefulness of the feedback.
- **Analysis:** small N, so report effect sizes with bootstrap CIs, and mixed-effects
  models only if N allows. Frame as a pilot. Pre-register the primary outcome in
  `plan/study/protocol.md` before trials start.
- **Ethics and data:** consent mentions that transcripts go to the LLM API; no names in
  transcripts; data stays out of git (`data/sessions/` is gitignored); delete or archive
  per consent at the end (T-044).

## 8. Workstreams and ownership

Owners are to be agreed. Suggestion: each person owns one of A-C, and all three share D.

| Workstream | Scope | Tasks | Owner |
|---|---|---|---|
| **A. Cases and data** (`cases`, `analysis`) | Parser, case library, scoring, offer extraction, data export, analysis | T-004 to T-006, T-013, T-035, T-040, T-041 | TBD |
| **B. Counterpart and curriculum** (`counterpart`) | Agent, hybrid schedule, dials and tiers, simulation harness, ML-Q1, human-likeness, scenario selection | T-010 to T-012, T-016 to T-018, T-027 | TBD |
| **C. Feedback and profiling** (`feedback`, `profiling`) | Critical turns, rollouts, coaching, features, profile, ML-Q2 | T-020 to T-026 | TBD |
| **D. App and study** (`app`, `study`) | UI, human-vs-human mode, deployment, protocol, recruiting, running sessions | T-014, T-015, T-028, T-030 to T-034 | shared |

Weekly rhythm: a short sync (review `python scripts/tasks.py`, reassign, unblock), and
one integration day per week where everyone merges to `main`.

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Not enough time for 5 trials | Start recruiting in M0; run trials at 2 per week; fall back to 3 trials |
| Small N, so no significance | Pilot framing, effect sizes with CIs; lean on the ML-Q1 and ML-Q2 results, which use simulation and do not depend on N |
| LLM counterpart too agreeable, so it teaches bad habits | Code-enforced concession schedule (decision 0003); calibrate against human data (T-018) |
| Rollout cost and latency (K × N × turns × critical turns calls) | Cap critical turns and rollout length; run after the session; Batch API (50% off) for offline experiments; possibly a cheaper model for rollouts (T-003) |
| Parsed cases subtly wrong | Every case gets human review of its JSON (T-005, T-006) |
| API key leaked from a deployed app | Server-side secrets, access codes, spend cap (T-031) |
| Licensed case materials pushed to a public repo | `data/cases/private/` gitignored; CLAUDE.md rule |
| Schema changes break teammates | `schemas.py` changes announced in a PR, with tests updated in the same PR |

## 10. Descoping ladder (cut from the top)

1. LLM-generated case variants (keep rule-based scenario selection).
2. Human-likeness calibration against external datasets (keep internal human-vs-human comparisons).
3. Rehearsal-vs-real debrief view (keep the comparison in analysis only).
4. Counterfactuals at every critical turn (keep the top 3, smaller N).
5. Five trials (go to 3).
6. Hosted deployment (run sessions in person on our laptops).

**Never cut:** scoring and logging, controllability experiment, profiling validation on
synthetic users, a pilot study with real outcomes.

## 11. Budget

Fill in during T-003. Rule of thumb: before any experiment, `estimated calls × average
tokens per call × price` goes into its task file, and runs over the agreed threshold need a
teammate's OK. `ClaudeLLM.usage` tracks calls and tokens per run.
