# 0004: What goes in git, and how we treat participant data

- **Status:** accepted
- **Date:** 2026-10-24
- **Deciders:** Yash, Mahdi, Vincent

## Decision
- **Commit:** code, synthetic cases (`data/cases/*.json`), plans, docs, small aggregate
  results and figures.
- **Never commit:** `.env` or API keys; licensed class cases (`data/cases/private/`);
  session logs and anything from participants (`data/sessions/`, `data/study/`); raw
  experiment dumps (`results/**/raw/`).
- Participants are identified by pseudonymous ids only. No names or contact details
  appear in transcripts or session files. The mapping from id to person lives outside the
  repo, with one teammate.
- Participant data is stored privately (not public cloud links) and archived or deleted at
  the end as the consent form says.

## Consequences
`.gitignore` enforces the paths above. Reviewers check that PRs don't add data files.
