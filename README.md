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

Typical flow for a class simulation:

1. **Case library**: paste the case's public information and your confidential sheet; the
   parser builds a scorable case (estimating the other side's sheet if you don't have it)
   and saves it to `data/cases/private/` (gitignored). Facilitators can upload JSON instead.
2. **Start**: enter a pseudonymous participant id and complete onboarding once.
3. **Rehearse**: pick the case and your role. The counterpart is recommended from your
   profile (or choose a tier 1-5); each rehearsal samples a slightly different opponent.
   Chat, attach formal offers with the per-issue builder, accept, or walk away. No hints
   during the negotiation.
4. **Feedback**: after the session, generate the debrief: outcome vs walk-away and vs the
   best joint deal, a coaching report, and "moments that mattered" estimated by replaying
   your key decisions with alternatives (counterfactual rollouts). Both sheets are revealed.
5. **My profile**: skill scores with confidence, recurring error patterns, and the
   recommended next rehearsal.
6. **Real negotiation**: after the real simulation, log the outcome and how the other side
   behaved; the page compares it with your rehearsals (sim-to-real gap).

Feedback with the Claude counterpart makes up to ~37 API calls per session at the default
settings; the page shows an estimate before running (not yet measured live), and the free
rule-based simulator is the alternative. Data lands in `data/sessions/` and `data/participants/` (both gitignored).

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
