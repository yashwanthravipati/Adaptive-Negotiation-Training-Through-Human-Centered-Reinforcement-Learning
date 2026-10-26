# Architecture

## Data flow

1. **Case.** A negotiation case (`schemas.Case`) has issues with options, and per-role
   confidential sheets (`RoleSheet`) with point tables, a reservation value (BATNA), and
   optional hard constraints. Cases come from hand-written JSON or from the LLM parser
   (`cases/parser.py`, T-004), always followed by human review.
2. **Session setup.** The curriculum (`curriculum/`, T-027) picks a case, a role, and a
   `CounterpartProfile` (tier plus dials). `counterpart.sample_profile` jitters the tier's
   preset (domain randomization).
3. **Negotiation.** The UI (`app/`, T-014) or the CLI (`cli.py`) appends `Turn`s to a
   `Session`. Each turn has free text plus an optional structured `Offer`
   (issue → option), `accept`, or `walk_away`. `Session.add_turn` enforces turn order and
   the agreement rules: you can only accept the other side's latest *complete* offer.
4. **Counterpart.** `CounterpartAgent.respond(session)` builds a system prompt from the
   public brief, its own role sheet, and behavior instructions (`profiles.describe`); it
   replays the transcript and asks the LLM for a structured `CounterpartMove`. Code-level
   guards reject invalid ids, deals below the reservation value, and (T-011) deals below
   the current aspiration level (`counterpart/aspiration.py`), and ask the model again; a
   private per-turn note tells the model its current minimum. After three invalid
   attempts, code makes a counteroffer at the minimum (`agent.fallbacks` counts these).
   `RuleBasedCounterpart` follows the same schedule with canned dialogue: it is the
   offline-mode opponent and the cheap finisher for rollouts.
5. **Storage.** `SessionStore` writes `data/sessions/<id>.json` after every turn;
   per-session artifacts (the feedback `Debrief`) go to `data/sessions/<kind>/<id>.json`;
   onboarding records (`Participant`) to `data/participants/`.
6. **Afterwards.** `feedback/` reads a finished session: `critical_turns` picks up to 3
   user decisions (first offer, concessions, accept, walk-away); `alternatives` builds
   concrete alternative moves in code; `analyze_session` replays each from a fork N times
   (LLM counterpart for `horizon` turns, then the rule-based finisher) against a
   `simulation.ScriptedUser` that concedes at this user's observed pace; `build_report`
   turns the numbers into a coaching report (LLM, with a template fallback).
   `profiling/` turns sessions into features, error flags, and skill scores shrunk toward
   0.5; `curriculum.next_scenario` uses them to pick the next tier and dial emphasis.
7. **Real negotiations** are logged as `Session(kind="real")` with the agreement and the
   participant's ratings of the other side (`observed_counterpart`), so the same feature
   code and the rehearsal-vs-real comparison work on them.

## Modules

| Module | Responsibility | Workstream | Status |
|---|---|---|---|
| `schemas.py` | Shared data models; the contract between modules | all | v1 |
| `llm.py` | `LLM` protocol, `ClaudeLLM`, `ScriptedLLM`, `LLMRefusal`, `Usage` | infra | v1 |
| `config.py` | Env-driven settings (`NEGOTRAIN_MODEL`, `NEGOTRAIN_EFFORT`, `NEGOTRAIN_SESSIONS_DIR`) | infra | v1 |
| `cases/__init__.py` | `load_case` | cases | v1 |
| `cases/scoring.py` | `score_offer`, `joint_points`, `max_joint_offer`, `efficiency` | cases | v1 |
| `cases/parser.py` | Raw case text or a set of files (`parse_documents`) → `Case`; infers a missing sheet | cases | MVP (T-004) |
| `cases/documents.py` | Text from uploaded PDF / Word / text files | cases | MVP (T-045) |
| `prep.py` | Prep brief: `prep_numbers` (code), `build_prep` (LLM + template); own sheet only | app | MVP (T-045) |
| `cases/offers.py` | Offer search: `closest_offer`, `best_joint_offer`, `claim`, `surplus_share` | cases | MVP |
| `counterpart/profiles.py` | Tier presets, `sample_profile`, `describe` | counterpart | v1 (T-012) |
| `counterpart/aspiration.py` | Concession schedule (`aspiration`) | counterpart | MVP (T-011) |
| `counterpart/agent.py` | `CounterpartAgent`, `CounterpartMove` | counterpart | v1 + schedule (T-010, T-011) |
| `counterpart/rule_based.py` | `RuleBasedCounterpart`, `Counterpart` protocol | counterpart | MVP |
| `simulation.py` | `ScriptedUser`, `run_episode`, `episode_value` | counterpart | MVP (T-016) |
| `feedback/` | `critical_turns`, `analyze_session`, `build_report`, `Debrief` | feedback | MVP (T-020, T-021, T-023) |
| `profiling/` | `extract_features`, `flags`, `build_profile` | profiling | MVP (T-024, T-025) |
| `curriculum/` | `next_scenario`, `counterpart_for` | counterpart | MVP (T-027) |
| `sessions.py` | `SessionStore` (+ artifacts), `ParticipantStore` | infra | v1 |
| `cli.py` | `negotrain show`, `negotrain play` | infra | v1 |
| `app/` | Streamlit UI: Start, Prepare, Rehearse, Feedback, My profile, Real negotiation, Case library | app | MVP (T-014, T-028) |

## Counterpart dials

All dials are in [0, 1]. `describe()` maps each one into low, mid, or high instructions.

| Dial | Low | High |
|---|---|---|
| `anchoring` | opens near a fair split | opens near its best outcome |
| `concession_rate` | rarely concedes, small steps | concedes readily |
| `cooperativeness` | fixed-pie competitor | seeks cross-issue trades |
| `aggression` | warm, polite | forceful, applies pressure |
| `disclosure` | deflects questions about priorities | shares priorities openly |
| `bluffing` | strictly truthful | exaggerates alternatives and priorities |

Tiers 1-5 are presets that run from transparent-cooperative to hardball (`profiles.TIERS`).

## LLM usage conventions

- Make every call through an `LLM` instance passed in by the caller (dependency
  injection), so tests can substitute `ScriptedLLM`.
- Use `llm.parse(system, messages, PydanticModel)` for anything the code will read.
  Prefer flat schemas: lists of small objects instead of free-form dicts.
- Keep the system prompt stable within a session (the case and role sheet go first) so
  prompt caching applies; put per-turn content in `messages`.
- Opus 5.5 always thinks; control depth and spend with effort (`NEGOTRAIN_EFFORT`, or
  `ClaudeLLM(effort=...)`). `temperature` is not accepted by the API.
- Parallelize rollouts with `concurrent.futures.ThreadPoolExecutor`; the SDK client is
  thread-safe.
- `ClaudeLLM.usage` accumulates calls and tokens; log it with experiment results.

## Schema additions in the MVP (decision 0005)

- `RoleSheet.inferred`: the parser estimated this sheet (the user had only their own).
- `Session.kind` (`rehearsal` | `real`), `Session.notes`, `Session.observed_counterpart`
  (participant's 0-1 ratings of a real counterpart on the dials).
- `Participant`: onboarding record (pseudonymous id, experience, goals, self-ratings,
  consent).

All new fields have defaults, so existing session and case JSON still loads.
