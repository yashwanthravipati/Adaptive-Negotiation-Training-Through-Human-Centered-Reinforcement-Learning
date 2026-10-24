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
  cases/              case loading, parsing (HW0 port), scoring
  counterpart/        counterpart agent, behavioral profiles, curriculum tiers
  feedback/           counterfactual credit assignment and coaching
  profiling/          behavioral features and negotiator profiles
  curriculum/         tailored scenario selection/generation
  sessions.py         session persistence
  cli.py              `negotrain` command
data/cases/           synthetic cases (safe to commit); private/ holds licensed class cases (gitignored)
data/sessions/        session logs (gitignored, may contain participant data)
scripts/tasks.py      task board CLI
tests/                pytest suite (offline by default)
```
