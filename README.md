# Adaptive Negotiation Training Through Human-Centered RL

CS2822r project by Yash Ravipati, Mahdi Nassereddine, and Vincent Song.

Most work on RL for negotiation trains *agents*. We flip it: LLM agents turn a negotiation
case into a rehearsal environment that trains *people*. The environment plays the other
side with controllable behavior, adapts difficulty to the negotiator, gives turn-level
feedback via counterfactual credit assignment, and logs everything as structured data.

- **Project plan, milestones, evaluation design:** [`plan/PLAN.md`](plan/PLAN.md)
- **Task board and planning workflow:** [`plan/README.md`](plan/README.md)
- **System architecture:** [`docs/architecture.md`](docs/architecture.md)
- **Guidance for Claude / coding agents:** [`CLAUDE.md`](CLAUDE.md)

## Quickstart

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"          # add ,analysis for pandas/scipy/matplotlib/jupyter

cp .env.example .env              # then put your ANTHROPIC_API_KEY in .env

pytest                            # offline tests (no API calls)
ruff check .                      # lint
python scripts/tasks.py           # see the task board
python scripts/tasks.py next      # tasks that are ready to pick up
```

## Run the app (MVP)

```bash
streamlit run src/negotrain/app/main.py
```

Opens at http://localhost:8501. With `ANTHROPIC_API_KEY` in `.env` (or pasted into the
sidebar) the counterpart, feedback, and case parser use Claude. Without a key, or with
`NEGOTRAIN_OFFLINE=1`, it runs on a rule-based counterpart and template feedback, which is
handy for demos and UI work.

The app runs locally for one person (no sign-in). Typical flow for a class simulation:

1. **Upload your case** (the first screen; nothing else is unlocked until this is done):
   drop in all your case files (PDF, Word, text). Claude works out which file is which and
   builds a scorable scenario, estimating the other side's instructions if you don't have
   them (saved to `data/cases/private/`, gitignored). Pick your role and start training.
   Offline, or to reuse a case, pick a saved case instead.
2. **Prepare**: your prep brief from your side only (overview, walk-away and target,
   what's at stake per issue, hypotheses about the other side, questions, opening plan,
   pitfalls, checklist) and a training plan: warm-up, realistic, tough, and
   profile-recommended counterparts on this exact scenario.
3. **Rehearse**: chat, attach formal offers with the per-issue builder, accept, or walk
   away. No hints during the negotiation.
4. **Feedback**: after each session: outcome vs walk-away and vs the best joint deal, a
   coaching report, and "moments that mattered" from counterfactual rollouts. Both sheets
   are revealed.
5. **My profile**: skill scores with confidence, recurring error patterns, and the
   recommended next rehearsal.
6. **Real negotiation**: after the real simulation, log the outcome and how the other side
   behaved, compared with your rehearsals (sim-to-real gap).

"New scenario" in the sidebar goes back to step 1.

Feedback with the Claude counterpart makes up to ~37 API calls per session at the default
settings; the page shows an estimate before running (not yet measured live), and the free
rule-based simulator is the alternative. Data lands in `data/sessions/` (gitignored).

## Terminal

Rehearse against the counterpart agent in the terminal (this one calls the API):

```bash
negotrain show data/cases/cloudline_hiring.json
negotrain play data/cases/cloudline_hiring.json --role candidate --tier 2
```

## Repository layout

```
plan/                 project plan, task files, decision records (the planning system)
docs/                 architecture and design notes
src/negotrain/        Python package
  schemas.py          shared data models (Case, Offer, Turn, Session, CounterpartProfile)
  llm.py              the only place that talks to the LLM API
  cases/              case loading, LLM parser, scoring, offer search
  counterpart/        LLM agent, rule-based twin, concession schedule, profiles and tiers
  feedback/           critical turns, counterfactual rollouts, coaching report
  profiling/          behavioral features, error flags, negotiator profile
  curriculum/         tailored scenario selection
  simulation.py       simulated negotiators and the agent-vs-agent episode runner
  sessions.py         session, artifact, and participant persistence
  app/                Streamlit app (main.py entry, views.py pages)
  cli.py              `negotrain` command
data/cases/           synthetic cases (safe to commit); private/ holds licensed class cases (gitignored)
data/sessions/        session logs and feedback (gitignored, may contain participant data)
data/participants/    onboarding records (gitignored)
scripts/tasks.py      task board CLI
tests/                pytest suite (offline by default)
```
