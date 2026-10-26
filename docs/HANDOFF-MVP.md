# Handoff: MVP branch (2026-10-25)

For the next agent or teammate picking this up. Read `CLAUDE.md`, `plan/PLAN.md`, and
`docs/architecture.md` first. This file covers what the `MVP` branch adds, how the app
flows, what has and hasn't been verified, and what is still open.

## Why this branch exists

The team needed a usable first version for a class negotiation simulation on 2026-10-26.
The ask was an MVP of everything in the Checkpoint 1 proposal:
- case parsing;
- an adjustable counterpart;
- counterfactual feedback;
- profiling;
- tailored scenarios;
- sim-to-real comparison;
- a UI.

Later requests in the same session added uploading case files with a prep brief, a visual
redesign, and an upload-first flow with no sign-in.

Branch `MVP` is pushed to `origin`. It is **not merged** into `main`; open a PR when the
team is ready.

| Commit | What |
|---|---|
| `1b5fdf0` | Core MVP: app, concession schedule, parser, feedback, profiling, curriculum |
| `511630c` | First version of this handoff file |
| `41ffc01` | T-045: upload case files, prep brief, scenario training plan |
| `43042a6` | T-014: UI polish (theme, components, grouped nav); fix `$` rendering as LaTeX |
| `39ec7a9` | T-045: upload-first flow, no sign-in; pages unlock once a scenario is chosen |

## How to run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"                       # now also installs pypdf and python-docx
streamlit run src/negotrain/app/main.py       # http://localhost:8501
pytest                                        # 59 offline tests
```

- **With `ANTHROPIC_API_KEY`** (in `.env`, or pasted on the first screen or in Settings):
  file parsing, the prep brief, the counterpart, and the coaching report use Claude.
  - The model is `claude-opus-5-5`.
  - Counterpart chat turns run at effort `low` (`NEGOTRAIN_CHAT_EFFORT`).
  - Parsing and coaching run at `medium`.
- **Without a key, or with `NEGOTRAIN_OFFLINE=1`:** `RuleBasedCounterpart` with canned
  dialogue, plus template prep and coaching. Uploading files needs the API, but saved
  cases work offline.
- **Run it from the repo root,** so Streamlit picks up `.streamlit/config.toml` (the theme).

## The app flow (as the user sees it)

The app is **local and single-user**: no sign-in, onboarding, or consent screen. Sessions
are stored under `config.participant_id()` (default `local`, `NEGOTRAIN_PARTICIPANT`).

1. **Upload case** (`views.page_setup`). This is the only screen until a scenario exists,
   and the navigation is hidden.
   - Upload all case files (PDF, Word, txt, md); `parse_documents` works out which file is
     which.
   - Or pick a saved case from the library.
   - Choose your role. The uploaded role is preselected; an estimated other side is
     flagged.
   - "Start training →" writes the *active scenario* (case + role) to
     `data/sessions/state/current.json`.
2. **Prepare** (the default page once active). The prep brief is generated automatically:
   - numbers from code;
   - prose from the LLM, or a template;
   - **only the user's own sheet goes into the prompt.**

   Below it, a training plan of tier 2, 3, and 4 counterparts plus the curriculum's pick,
   each with a Start button.
3. **Rehearse.** Chat with offer cards, and a per-issue offer builder (two-column
   dropdowns, "Leave open" placeholder). Accept, walk away, or abandon. The side panel
   shows:
   - the offers on the table;
   - your sheet as point pills;
   - your prep checklist;
   - the public info.

   The counterpart's sheet is revealed only after the session ends.
4. **Feedback.** Choose a simulator for the alternatives (the same Claude counterpart, or
   the free rule-based one); a cost estimate is shown first. Tabs:
   - coaching report;
   - moments that mattered (counterfactual table);
   - transcript;
   - both sheets;
   - raw features.

   There is also a 1-5 usefulness rating.
5. **My profile.** Skill scores with confidence, recurring error patterns, history, and
   the recommended next rehearsal.
6. **Real negotiation.** Log the real outcome, ratings of the other side's behavior, and
   notes, then compare with rehearsals of the same case and role.
7. **Case library** (under "More"). The case list, plus paste-text and JSON import.
   Facilitator mode (in Settings) shows the full JSON, including both sheets.

The sidebar has the logo, the current scenario with a "📂 New scenario" button (back to
step 1), and a Settings expander:
- API key and offline toggle;
- API usage and estimated cost;
- facilitator mode;
- the "enforce concession schedule" toggle (off gives the prompt-only counterpart, for
  T-017).

## What was built (by module)

| Area | Files | Task |
|---|---|---|
| Offer search (closest offer at a minimum, best joint offer, claim, surplus share) | `cases/offers.py` | shared |
| Text from uploads (PDF via pypdf, Word incl. tables via python-docx, txt/md) | `cases/documents.py` | T-045 |
| Parser: list-based `ParsedCase` → `Case`, 1 retry, infers a missing sheet; `parse_case` (pasted text) and `parse_documents` (files) | `cases/parser.py` | T-004, T-045 |
| Case library and saving to `data/cases/private/` | `cases/__init__.py` | — |
| Concession schedule (aspiration level) | `counterpart/aspiration.py` | T-011 |
| Agent: rejects moves below aspiration, private per-turn note, code fallback after 3 bad moves, `enforce_schedule` flag | `counterpart/agent.py` | T-010, T-011 |
| Rule-based counterpart (offline mode, rollout finisher, baseline) | `counterpart/rule_based.py` | — |
| Simulated user + episode runner | `simulation.py` | T-016 (partial) |
| Critical turns, counterfactual rollouts, coaching report, `Debrief` artifact | `feedback/critical.py`, `rollouts.py`, `coaching.py` | T-020, T-021, T-023 |
| Prep brief (`prep_numbers` in code, `build_prep` LLM + template), `Prep` artifact | `prep.py` | T-045 |
| Features, error flags, skill profile with shrinkage | `profiling/features.py`, `profile.py` | T-024, T-025 |
| Next-scenario policy | `curriculum/__init__.py` | T-027 |
| Persistence: sessions, artifacts in `data/sessions/<kind>/<id>.json` (`feedback`, `prep`, `state`) | `sessions.py`, `config.py` | — |
| Usage and cost tracking, thread-safe | `llm.py` (`Usage.cost`, `PRICE_PER_MTOK`) | — |
| App: navigation and gating | `app/main.py` | T-014 |
| App: pages, active scenario, counterpart factory | `app/views.py` | T-014, T-028, T-045 |
| App: CSS and HTML components, `md()` escaping | `app/style.py`, `app/assets/*.svg`, `.streamlit/config.toml` | T-014 |

## Conventions to keep

- **Use `style.md()` for any case or chat text passed to `st.markdown`, `st.write`,
  `st.caption`, `st.success`, and so on.** Streamlit renders a pair of `$` as LaTeX, and
  cases are full of dollar amounts. HTML components in `style.py` escape their inputs.
- **Read Streamlit state before starting worker threads.** Rollouts run in a thread pool,
  where `st.session_state` is unavailable. `views.counterpart_factory` captures
  everything up front.
- **`views.go(page)`** switches pages, or reruns when pages aren't registered (as in
  tests). `views.PAGES` is rebuilt by `main.py` on every run.
- **UI tests** (`tests/test_app.py`) use `AppTest`:
  - `AppTest.from_file(main.py)` for the gated flow;
  - `AppTest.from_function(page_script, args=(page_name,))` for single pages.

  The `scenario` fixture writes an active scenario. File uploads are tested with
  `at.file_uploader[0].set_value([...])` and a monkeypatched `views.online` / `views.llm`.
- **After editing `views.py` or `style.py`, restart the server.** Streamlit reruns
  `main.py`, but it doesn't reload imported modules.

## Key design choices

- **Economics in code** (decision 0003).
  - The aspiration starts at `rv + (0.55 + 0.45·anchoring)·span`.
  - It decays by `0.04 + 0.26·concession_rate` per counterpart turn, plus
    `cooperativeness ×` the user's concessions.
  - Its floor is `rv + 0.1·(1 − concession_rate)·span`.
  - The LLM is told its minimum in a private note appended to the last user message, so
    the system prompt stays cacheable.
- **Counterfactuals.**
  - Alternatives are concrete offers built in code from the user's own point table.
    "Trade across issues" uses both sheets; that's hindsight, and feedback is
    post-session.
  - Each rollout uses the LLM counterpart for `horizon` turns, then the rule-based
    counterpart (same profile and schedule) finishes it for free.
  - The simulated user concedes at the real user's observed pace.
  - Default cost: 3 turns × (1 + 2 alternatives) × 2 rollouts × 2 LLM turns = 36 calls.
- **Numbers come from code; LLMs only write prose** (coaching and prep), with template
  fallbacks.
- **Profile** = per-skill mean shrunk toward 0.5 with prior weight 2; confidence is
  `n/(n+2)`. It is rebuilt from all sessions each time.
- **Prep brief and decision 0002.** The brief and its opening plan are *pre-negotiation*
  preparation. Decision 0002 forbids live hints *during* a negotiation, and the prep
  checklist shown while rehearsing is the participant's own notes. Flag this to the team
  if anyone reads 0002 more strictly.
- **Schema additions** (all defaulted, backward compatible) are proposed in
  `plan/decisions/0005-…`:
  - `RoleSheet.inferred`;
  - `Session.kind`, `Session.notes`, `Session.observed_counterpart`;
  - `Participant` (now unused by the UI; kept for the study).

  **Teammates still need to accept it.**
- **The study design assumes participant ids** (PLAN.md §7). The single-user local app
  stores everything under `local`. For the pilot study, run one app per participant with
  `NEGOTRAIN_PARTICIPANT=<id>`, or bring back an id field. That's a decision for the
  team.

## Verified vs not verified

**Verified offline:**
- 59 tests pass, including AppTest flows:
  - upload, then role, then unlock, then "New scenario";
  - a rehearsal where the counterpart's sheet stays hidden until the end;
  - feedback, profile, real negotiation, and case library pages;
  - file upload with an unreadable file reported.
- ruff and `scripts/tasks.py check` pass.
- The landing, Prepare, Rehearse, and Feedback pages were checked visually in a browser.

**Not verified:** anything that calls the real API. No key was available, so these have
never run live:
- counterpart chat (`ClaudeLLM.parse` with `CounterpartMove`);
- `parse_documents` on real case files;
- the LLM prep brief and coaching report;
- feedback cost and latency.

The ~36-call feedback estimate and `views.EST_COST_PER_CALL = $0.03` are guesses.

## Open work (suggested next steps)

1. **Live smoke test.** Upload a real case, then run rehearsals at tiers 1, 3, and 5 and
   generate feedback with the Claude counterpart.
   - Record latency per turn, `agent.fallbacks`, and cost in T-010 and T-021.
   - Watch for leaks of the counterpart's points or reservation value in its dialogue.
   - Check the parsed issues and point tables (T-045).
2. **T-004:** add the `@pytest.mark.live` test; check the parser recovers
   `cloudline_hiring.json` from a plain-text rendering.
3. **T-022:** validate the credit assignment (do rollout deltas identify mistakes
   injected through `ScriptedUser`?).
4. **T-016/T-017:** LLM-persona users, `results/<exp>/` outputs, cost prompts, and the
   controllability experiment (`enforce_schedule` on vs off).
5. **T-013:** extract offers from free text. Only offer-builder offers are structured, so
   offers stated only in chat are invisible to scoring and features.
6. **T-015:** a human-vs-human mode (can reuse `kind="real"`).
7. **T-028:** export the comparison data for analysis.
8. **Known simplifications:**
   - Question detection is just "contains `?`".
   - `closest_offer` enumerates up to 50k offers and uses a greedy search above that.
   - The rule-based counterpart's dialogue is canned.
   - Tone bands come only from `aggression`.
   - Only two-party cases are supported.

These task files have ticked criteria (verified ones only) and dated log lines: T-004,
T-010, T-011, T-014, T-016, T-020, T-021, T-023, T-024, T-025, T-027, T-028, and T-045.
They are `in-progress` with owner `mahdi`; none are marked done.
