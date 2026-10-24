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
   guards reject invalid ids and deals below the reservation value and ask the model
   again. T-011 adds the aspiration schedule.
5. **Storage.** `SessionStore` writes `data/sessions/<id>.json` after every turn.
6. **Afterwards.** `feedback/` (critical turns, counterfactual rollouts, coaching report)
   and `profiling/` (features, then a profile) read finished sessions. The profile feeds
   the curriculum's next pick.

## Modules

| Module | Responsibility | Workstream | Status |
|---|---|---|---|
| `schemas.py` | Shared data models; the contract between modules | all | v1 |
| `llm.py` | `LLM` protocol, `ClaudeLLM`, `ScriptedLLM`, `LLMRefusal`, `Usage` | infra | v1 |
| `config.py` | Env-driven settings (`NEGOTRAIN_MODEL`, `NEGOTRAIN_EFFORT`, `NEGOTRAIN_SESSIONS_DIR`) | infra | v1 |
| `cases/__init__.py` | `load_case` | cases | v1 |
| `cases/scoring.py` | `score_offer`, `joint_points`, `max_joint_offer`, `efficiency` | cases | v1 |
| `cases/parser.py` | Raw case text → `Case` | cases | stub (T-004) |
| `counterpart/profiles.py` | Tier presets, `sample_profile`, `describe` | counterpart | v1 (T-012) |
| `counterpart/agent.py` | `CounterpartAgent`, `CounterpartMove` | counterpart | v1 (T-010, T-011) |
| `feedback/` | Critical turns, rollouts, coaching | feedback | planned (T-020 to T-023) |
| `profiling/` | Features, profile | profiling | planned (T-024 to T-026) |
| `curriculum/` | Next-scenario policy | counterpart | planned (T-027) |
| `sessions.py` | `SessionStore` (JSON files) | infra | v1 |
| `cli.py` | `negotrain show`, `negotrain play` | infra | v1 |
| `app/` | Streamlit UI | app | planned (T-014, T-015) |

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
