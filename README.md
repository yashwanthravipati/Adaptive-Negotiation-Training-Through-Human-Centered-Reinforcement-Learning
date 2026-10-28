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

Opens at http://localhost:8501. The app talks to Claude in one of three ways (Settings in the
sidebar, or `NEGOTRAIN_BACKEND`):

- **Claude Code (default when installed):** uses your logged-in Claude plan through the
  local `claude` CLI, with no API key. For personal, local use.
- **API key:** `ANTHROPIC_API_KEY` in `.env`, or pasted in the app.
- **Offline:** rule-based counterpart and template feedback (also `NEGOTRAIN_OFFLINE=1`),
  handy for demos and UI work.

The app runs locally for one person (no sign-in). Typical flow for a class simulation:

1. **Upload your case** (the first screen; nothing else is unlocked until this is done):
   drop in all your case files (PDF, Word, text), individually or in a ZIP bundle.
   ZIPs can contain folders; supported documents are read with their paths preserved.
   Hidden/macOS metadata is ignored, and unreadable or unsupported files are reported.
   ZIPs are limited to 200 entries and 50 MB of uncompressed documents; password-protected
   files and ZIPs inside ZIPs aren't supported. Claude works out which file is which and
   builds a scorable scenario, estimating the other side's instructions if you don't have
   them (saved to `data/cases/private/`, gitignored). Pick your role and start training.
   Offline, or to reuse a case, pick a saved case instead.
2. **Prepare**: your prep brief from your side only (overview, walk-away and target,
   what's at stake per issue, hypotheses about the other side, questions, opening plan,
   pitfalls, checklist) and a training plan: warm-up, realistic, tough, and
   profile-recommended counterparts on this exact scenario.
3. **Rehearse**: chat, attach formal offers with the per-issue builder, accept, or walk
   away. For each issue, choose a suggestion or type your own solution and press Enter;
   leave undecided issues blank. The AI counterpart can discuss, counterpropose, or accept
   custom terms. They are saved exactly as proposed. Ask Your assistant for help when needed.
4. **Feedback**: after each session: outcome vs walk-away and vs the best joint deal, a
   coaching report, and "moments that mattered" from counterfactual rollouts. Both sheets
   are revealed.
5. **My profile**: Beta beliefs over six error rates, case-fact awareness, and rapport,
   with credible intervals and a cost-weighted recommendation for the next rehearsal.
6. **Real negotiation**: after the real simulation, log the outcome (including custom
   agreed terms) and how the other side behaved, compared with your rehearsals (sim-to-real gap).

Custom terms have no defined point value in the case's score tables. These agreements
are marked **not scored**; coaching remains qualitative, and sessions involving custom
terms skip point-based counterfactual simulations and concession metrics. Missing values
are excluded from numeric comparisons and skill estimates. The offline counterpart can
only evaluate listed options; use the AI counterpart for open-ended negotiation.

"New scenario" in the sidebar goes back to step 1.

**Your assistant** stays on the right across Prepare, Rehearse, Feedback, and the other
pages. During rehearsal it clarifies facts only; before or after a session, you can also
explore possible replies. Chat is private to your participant, case, and role, survives
page changes/restarts, and never sends a move to the counterpart. "New chat" clears the
conversation while keeping attached sources.

The assistant cites case sections/source filenames and labels hypothetical responses as
possibilities. It uses your role's visible material; the other sheet is included only on
a finished rehearsal/debrief page where it is already revealed. It has no live web search.
New imports retain original extracted source text with role access classifications;
mixed or unclassified files are withheld. For older imports, or additional documents,
use **Sources and context → Add source documents** in the panel (ZIPs work too).
Offline, saved chat and sources remain readable; choose Claude Code or an API key in
Settings for new AI replies.

Counterfactual feedback uses four rollouts per candidate plus independent fresh batches
for scoring. It reports surplus-share differences and uncertainty, labels hindsight
alternatives, and runs after the session. The free rule-based simulator is the default;
full LLM rollouts can be expensive, and the page estimates calls before running them.
Data lands in `data/sessions/` (gitignored). A visible deadline ends rehearsals after
20 user moves and the corresponding counterpart responses.

The current reimplementation follows [`docs/new-spec.md`](docs/new-spec.md) and
[`docs/report.tex`](docs/report.tex). See [decision 0008](plan/decisions/0008-opportunity-beliefs-and-evaluation-contract.md)
for their differing belief/objective definitions. The persistent API ledger enforces a
$200 user-authorized cumulative cap across calls and restarts (new ledgers default to $150).
See [the sim3 evaluation](docs/results/sim3_evaluation.md) for results and limitations:
7,960 primary offline and 280 live episodes completed. Tier control succeeds; adaptive
targeting has not demonstrated an advantage over no-focus coaching in the live cohort.

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
  profiling/          opportunity detectors, tagging, Beta beliefs, cost-weighted planning
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
