# CLAUDE.md

Guidance for Claude (and other coding agents) working in this repository.

## What this project is

A class research project (CS2822r, three students) that builds an LLM rehearsal
environment for training *human* negotiators: an adaptive counterpart, post-session
feedback via counterfactual credit assignment, and negotiator profiling, evaluated with
simulation experiments and a pilot human study. It's an ML research prototype on a
deadline: prefer simple, working, measurable code over elaborate abstractions.

Read before non-trivial work:
- `plan/PLAN.md`: goals, research questions, milestones, study design, risks
- `docs/architecture.md`: data flow, module map, LLM conventions
- the task file for whatever you're doing (`plan/tasks/T-*.md`)

## Planning system: use it

Work is tracked as one markdown file per task in `plan/tasks/`. See `plan/README.md`.

```bash
python scripts/tasks.py            # board
python scripts/tasks.py next       # ready-to-start tasks
python scripts/tasks.py show T-014
python scripts/tasks.py set T-014 status=in-progress owner=<name> --note "..."
python scripts/tasks.py new "Title" --milestone M2 --workstream feedback --depends T-021
python scripts/tasks.py check
```

When you work on something:
1. **Map the request to a task.** If the user names a task, read its file first. If the
   work clearly belongs to an existing task, say which one. For a non-trivial piece of
   work with no task, offer to create one; don't create tasks for small fixes.
2. **Respect scope.** The acceptance criteria define done. If you discover more work,
   add it to the log or propose a new task instead of silently expanding scope.
3. **Close the loop.** When you finish, tick the criteria you completed, add a dated log
   line (what changed, key numbers, open questions), and set the status (`review` if a
   PR is open, `done` only when the user confirms or the work is merged). Never mark
   criteria done that you didn't verify.
4. **Decisions.** If you make a choice that affects other workstreams (schemas, models,
   study design), propose a decision record in `plan/decisions/` and tell the user.
5. Update `plan/PLAN.md` only when the user agrees the strategy has changed.

## Setup and commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"                 # ,analysis for pandas/scipy/matplotlib/jupyter
pytest                                  # offline tests; live API tests are deselected
pytest -m live                          # live tests: they cost money, so ask first
ruff check . && ruff format .           # lint and format (line length 100)
negotrain show data/cases/cloudline_hiring.json
negotrain play data/cases/cloudline_hiring.json --role candidate --tier 3   # calls the API
```

Use `.venv/bin/` executables if the venv isn't activated. CI (`.github/workflows/ci.yml`)
runs ruff, pytest, and `scripts/tasks.py check`. Keep all three green.

## Code map

```
src/negotrain/
  schemas.py        Case, RoleSheet, Issue, Option, Constraint, Offer, Turn, Session, CounterpartProfile
  llm.py            LLM protocol, ClaudeLLM, ScriptedLLM, LLMRefusal, Usage
  config.py         env settings (NEGOTRAIN_MODEL, NEGOTRAIN_EFFORT, NEGOTRAIN_SESSIONS_DIR)
  assistant.py      personal assistant context, source retrieval, private conversation models
  app/assistant_panel.py  persistent right-hand chat (Streamlit fragment)
  cases/            load_case, scoring.py (deterministic), parser.py (T-004)
  counterpart/      agent.py (CounterpartAgent), profiles.py (tiers, dials, sampling)
  feedback/         counterfactual credit assignment and coaching (T-020 to T-023)
  profiling/        behavioral features and negotiator profile (T-024 to T-026)
  curriculum/       next-scenario selection (T-027)
  sessions.py       SessionStore (JSON per session)
  cli.py            `negotrain` command
tests/              pytest; `case` fixture loads data/cases/cloudline_hiring.json
```

## Conventions

- **Schemas are the contract.** `schemas.py` is shared by all three workstreams. Change it
  deliberately: update tests and `docs/architecture.md` in the same change, and point the
  change out to the user, since teammates' code may depend on it.
- **All LLM calls go through `negotrain.llm`.** Never construct `anthropic.Anthropic()`
  elsewhere. Accept an `LLM` argument (dependency injection) so tests can pass
  `ScriptedLLM`. Use `llm.parse(..., PydanticModel)` for anything code consumes.
- **Tests never hit the network.** Use `ScriptedLLM`. Tests that need the real API get
  `@pytest.mark.live` (deselected by default).
- **Scoring stays deterministic and LLM-free.** Outcomes, surplus, and efficiency come from
  `cases/scoring.py`, never from an LLM judgment.
- **Experiments are reproducible.** Seed every `random.Random`; write outputs to
  `results/<experiment>/` with the config and `llm.usage`; keep the analysis in a script
  or notebook in the repo.
- **Prompts** live as module-level strings or f-strings next to the code that uses them.
  Keep the system prompt stable within a session (prompt caching) and put per-turn
  content in messages.
- Match the existing style: type hints, `from __future__ import annotations`, small
  functions, docstrings that say *why*. Python 3.10 compatible.

## Product and research guardrails (do not violate without the user's say-so)

- **Automatic coaching remains post-session** (decision 0002). The user-requested personal
  assistant answers explicit questions, including hypotheticals, during rehearsal
  (decision 0007). It never sends a move to the counterpart or uses an unrevealed sheet.
- **Information hiding:** the counterpart never sees the user's confidential sheet, and the
  user never sees the counterpart's sheet before the debrief. Test this when you touch
  prompts or the UI.
- **Assistant context:** use only visible role-projected sources, own brief, and the visible
  conversation/feedback. Never serialize a full Case or Session into its prompt. Raw
  source text and assistant chats stay in the existing gitignored private data folders.
- **Listed-offer economics are enforced in code**: reservation values and the aspiration
  schedule (decision 0003). User-requested custom terms are qualitative and unscored
  (decision 0006); never invent points or claim numeric guarantees for those agreements.
- **Data (decision 0004):** never commit `.env`, `data/cases/private/`, `data/sessions/`,
  `data/study/`, or participant information. Commit only synthetic cases. If you're
  asked to add a case from class materials, put it in `data/cases/private/`.

## Cost and safety of API use

- Default model: `claude-opus-5-5` (config). Thinking is always on for this model; tune
  spend with effort, not temperature (the API rejects temperature).
- **Before any run that makes more than about 50 LLM calls** (sweeps, rollouts,
  simulations), estimate calls × tokens × price, write it in the task log, and ask the
  user before running.
- Handle `LLMRefusal` where a refusal would otherwise crash a user-facing flow.

## Git

- Branch per task (`t-014-streamlit-ui`); reference task ids in commit messages.
- Don't commit, push, or open PRs unless the user asks. Never force-push `main`.
- Teammates: Yash, Mahdi, Vincent. Don't @-mention GitHub handles you haven't confirmed.
