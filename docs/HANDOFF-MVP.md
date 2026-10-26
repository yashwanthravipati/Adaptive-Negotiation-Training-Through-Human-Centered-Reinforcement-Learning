# Handoff: MVP branch (2026-10-25)

For the next agent or teammate picking this up. Read `CLAUDE.md`, `plan/PLAN.md`, and
`docs/architecture.md` first; this file covers what changed on the `MVP` branch and what
is still open.

## Why this branch exists

The team needed a usable first version for a class negotiation simulation on 2026-10-26.
The ask was an MVP of everything in the Checkpoint 1 proposal: case parsing, an adjustable
counterpart, counterfactual feedback, profiling, tailored scenarios, sim-to-real
comparison, and a UI. Everything is on branch `MVP` (commit `1b5fdf0` plus this file); it
is **not pushed and not merged** into `main`.

## How to run

```bash
source .venv/bin/activate          # venv already created with pip install -e ".[dev]"
streamlit run src/negotrain/app/main.py     # http://localhost:8501
pytest                              # 50 offline tests
```

- With `ANTHROPIC_API_KEY` (in `.env` or pasted into the sidebar) the counterpart,
  coaching report, and case parser use Claude (`claude-opus-5-5`; chat turns at effort
  `low` via `NEGOTRAIN_CHAT_EFFORT`).
- Without a key, or with `NEGOTRAIN_OFFLINE=1`, the app uses `RuleBasedCounterpart` and the
  template coaching report.

## What was built (by module)

| Area | Files | Task |
|---|---|---|
| Offer search (closest offer at a minimum, best joint offer, claim, surplus share) | `cases/offers.py` | shared |
| Case parser: list-based `ParsedCase` → `Case`, 1 retry, infers a missing sheet | `cases/parser.py`, `cases/__init__.py` (`case_library`, `save_private_case`) | T-004 |
| Concession schedule (aspiration level) | `counterpart/aspiration.py` | T-011 |
| Agent: rejects moves below aspiration, private per-turn note, code fallback after 3 bad moves, `enforce_schedule` flag | `counterpart/agent.py` | T-010/T-011 |
| Rule-based counterpart (offline mode, rollout finisher, baseline) | `counterpart/rule_based.py` | — |
| Simulated user + episode runner | `simulation.py` | T-016 (partial) |
| Critical turns, counterfactual rollouts, coaching report, `Debrief` artifact | `feedback/critical.py`, `rollouts.py`, `coaching.py` | T-020, T-021, T-023 |
| Features, error flags, skill profile with shrinkage | `profiling/features.py`, `profile.py` | T-024, T-025 |
| Next-scenario policy | `curriculum/__init__.py` | T-027 |
| Persistence: artifacts in `data/sessions/<kind>/`, `ParticipantStore` | `sessions.py`, `config.py` | — |
| Streamlit app | `app/main.py` (navigation), `app/views.py` (pages) | T-014, T-028 |
| File upload text extraction (PDF via pypdf, Word via python-docx incl. tables) | `cases/documents.py` | T-045 |
| `parse_documents`: the model sorts uploaded files into public info and role sheets | `cases/parser.py` | T-045 |
| Prep brief (code numbers + LLM prose, template fallback, own sheet only) and the `Prep` artifact in `data/sessions/prep/` | `prep.py` | T-045 |
| Usage cost tracking, thread-safe | `llm.py` (`Usage.cost`, `PRICE_PER_MTOK`) | — |

Look and feel: the theme is in `.streamlit/config.toml` (Inter font, indigo primary, dark
sidebar); `app/style.py` adds CSS and small HTML components (hero, page headers, cards,
chips, offer cards, stat cards, point pills) and `md()`, which escapes `$` so dollar
amounts don't render as LaTeX. **Use `md()` for any case or chat text passed to
`st.markdown`/`st.write`/`st.caption`.** Navigation is grouped (Get ready / Practice /
Progress / More).

**Flow (simplified 2026-10-25 at the user's request):** no sign-in or onboarding; the app
is local and single-user (`config.participant_id()`, default `local`). The first screen is
the upload page (`page_setup`); the navigation is hidden until an *active scenario* (case +
role, stored at `data/sessions/state/current.json`) exists. Then the pages are Prepare
(brief auto-generated + training plan; T-045), Rehearse, Feedback, My profile, Real
negotiation, Case library. Sidebar: participant, API key, offline toggle, facilitator mode
(shows full case JSON), and an "enforce concession schedule" toggle.

## Key design choices

- **Economics in code** (decision 0003). The aspiration starts at
  `rv + (0.55 + 0.45·anchoring)·span`, decays by `0.04 + 0.26·concession_rate` per
  counterpart turn (plus `cooperativeness ×` the user's concessions), and has a floor of
  `rv + 0.1·(1 − concession_rate)·span`. The LLM is told its minimum in a private note
  appended to the last user message, so the system prompt stays cacheable.
- **Counterfactuals.** Alternatives are concrete offers built in code from the user's own
  point table; "trade across issues" uses both sheets (hindsight; feedback is
  post-session). Each rollout uses the LLM counterpart for `horizon` turns, then the
  rule-based counterpart (same profile and schedule) finishes it for free. The simulated
  user concedes at the real user's observed pace. Default: 3 turns × (1 + 2 alternatives) ×
  2 rollouts × 2 LLM turns = 36 calls. Streamlit state is read *before* the worker
  threads start (`views.counterpart_factory`), because session state is unavailable in
  threads.
- **Numbers come from code; the LLM only writes prose** (`coaching.py`). There is a
  template fallback if the call fails.
- **Profile** = per-skill mean shrunk toward 0.5 with prior weight 2; confidence is
  `n/(n+2)`. It is rebuilt from all sessions each time, not updated incrementally.
- **Prep brief** sees only the public info and the participant's own sheet; anything
  about the other side is phrased as a hypothesis. The training plan is tiers 2/3/4 plus
  the curriculum's pick, on the same case and role. The prep checklist is visible while
  rehearsing; the product principle (decision 0002) is about live hints *during* a
  negotiation, and this is the participant's own preparation.
- **Real negotiations** are stored as `Session(kind="real")` with an agreement and
  `observed_counterpart` ratings, and often no turns.
- **Schema additions** (all defaulted, backward compatible) are proposed in
  `plan/decisions/0005-…`: `RoleSheet.inferred`, `Session.kind/notes/observed_counterpart`,
  `Participant`. **Teammates still need to accept it.**

## Verified vs not verified

Verified offline:
- 59 tests pass, including AppTest smoke tests that click through every page and check
  that the counterpart's confidential brief is not rendered until the session ends.
- ruff and `scripts/tasks.py check` pass, and the server boots.

**Not verified:** anything that calls the real API. No key was available, so these have
never run live:
- the counterpart chat (`ClaudeLLM.parse` with `CounterpartMove`);
- the parser on real case text or uploaded files;
- the LLM prep brief;
- the LLM coaching report;
- feedback cost and latency.

The ~36-call feedback estimate and the `$0.03/call` figure in `views.EST_COST_PER_CALL`
are guesses. Do a live run before relying on any of these.

## Open work (suggested next steps)

1. **Live smoke test.** Run one rehearsal at tiers 1, 3, and 5, plus feedback with the
   Claude counterpart. Record latency per turn, `agent.fallbacks`, and cost in T-010 and
   T-021. Watch for leaks of the counterpart's points or reservation value in its dialogue.
2. **T-045:** try the upload flow with a real class case: check which file was assigned
   to which role, the point tables, and the brief's quality.
3. **T-004:** add the `@pytest.mark.live` test, and check the parser recovers
   `cloudline_hiring.json` from a plain-text rendering.
4. **T-022:** validate the credit assignment (do the rollout deltas identify injected
   mistakes from `ScriptedUser`?).
5. **T-016/T-017:** LLM-persona users, `results/<exp>/` outputs, cost prompts, and the
   controllability experiment (`enforce_schedule` on vs off).
6. **T-013:** extract offers from free text. Right now only offer-builder offers are
   structured, so offers stated only in chat are invisible to scoring and features.
7. **T-015:** human-vs-human mode in the app (can reuse `kind="real"`).
8. **T-028:** export the comparison data for analysis.
9. **Known simplifications:**
   - Question detection is just "contains `?`".
   - `closest_offer` enumerates up to 50k offers and uses a greedy search above that.
   - The rule-based counterpart's dialogue is canned.
   - The "warm/civil/forceful" tone bands come only from `aggression`.

Task files for T-004, T-010, T-011, T-014, T-016, T-020, T-021, T-023, T-024, T-025, T-027,
T-028, and T-045 have ticked criteria (only the verified ones) and dated log lines. They are
`in-progress` with owner `mahdi`; none are marked done.
