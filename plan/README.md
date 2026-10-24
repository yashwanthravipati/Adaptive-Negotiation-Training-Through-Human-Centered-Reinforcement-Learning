# Planning system

Everything about *what* we're doing and *why* lives in this folder, as plain files in git.
Humans and Claude agents use the same system.

```
plan/
  PLAN.md          strategy: goals, research questions, milestones, risks (changes rarely)
  tasks/           one file per unit of work (T-001-short-slug.md)
  decisions/       short decision records: what we chose and why (0001-*.md)
  templates/       templates for new tasks and decisions
  study/           study protocol and instruments (created in T-030)
```

## Tasks

Each task is a markdown file with frontmatter:

```yaml
id: T-014
title: Streamlit rehearsal UI v1
status: todo          # todo | in-progress | review | blocked | done
milestone: M1         # M0..M4, defined in PLAN.md §6
workstream: app       # cases | counterpart | feedback | profiling | app | study | analysis | infra
owner: unassigned     # first name, e.g. yash / mahdi / vincent
depends_on: [T-010]
```

The body has **Goal**, **Context**, **Acceptance criteria** (checkboxes), and **Log** (dated
one-liners: what happened, decisions made, PR links).

One file per task keeps merge conflicts rare: two people editing different tasks never
collide.

### Commands

`scripts/tasks.py` uses only the standard library, so it runs with any Python 3.10+.

```bash
python scripts/tasks.py                      # board: open tasks by status
python scripts/tasks.py next                 # todo tasks whose dependencies are done
python scripts/tasks.py next --owner vincent
python scripts/tasks.py list --milestone M1 --workstream counterpart
python scripts/tasks.py show T-014
python scripts/tasks.py set T-014 status=in-progress owner=mahdi --note "starting UI"
python scripts/tasks.py new "Add rubric survey" --milestone M3 --workstream study --depends T-030
python scripts/tasks.py check                # validate all task files (CI runs this)
```

Editing the files by hand is fine too; `check` catches mistakes.

### Workflow

1. **Pick:** `next`, then claim with `set T-0XX status=in-progress owner=<you>`. Commit and
   push that change early so teammates see the claim.
2. **Branch:** `t-0xx-short-name`. Reference the task id in commits (`T-014: add offer builder`).
3. **Work:** tick acceptance criteria as you go. Add log lines for anything a teammate
   would want to know (surprises, decisions, numbers).
4. **Review:** `status=review` when the PR is open; `done` when merged.
5. **Scope changes:** edit the criteria, or split into new tasks with `new`. Keep a task
   to about 1-2 days of work.
6. **Blocked:** `status=blocked` plus a log line saying what it's waiting on.

New task ids are `max + 1`. If two branches create the same id, `check` flags the duplicate
in CI; renumber one of them.

## Decisions

When a choice affects more than one workstream, or would be expensive to reverse (a schema
change, a model choice, the study design), copy `templates/decision.md` to
`decisions/NNNN-title.md`. Keep it under a page. Mark it `proposed` until the team agrees,
then `accepted`. Never delete one; supersede it with a new record.

## PLAN.md

Update it when milestones, scope, or the study design change: not for day-to-day
progress, which belongs in task logs.
