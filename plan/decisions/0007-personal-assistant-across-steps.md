# 0007: Personal assistant across preparation, rehearsal, and feedback

- **Status:** proposed
- **Date:** 2026-10-26
- **Authorization:** User explicitly requested a right sidebar for factual and hypothetical
  questions on every step, with access to everything visible to the user.

## Decision

Provide a persistent, private assistant conversation per participant/case/role. It may
answer user-initiated questions during rehearsal, including possible responses to a draft
message. This is a scoped user-authorized exception to decision 0002. Automatic coaching
and counterfactual simulations remain post-session, and no assistant action sends a turn
to the counterpart or edits a negotiation.

Assemble prompts from explicitly visible context. Include the public case, own role and
brief, visible conversation, and matching feedback. Reveal the counterpart's sheet only
when the selected finished-session page already shows it. Source files are retained with
whole-document role access classifications; ambiguous or mixed files are withheld. Users
may attach additional sources for their selected role. Never serialize full hidden case
or session objects into the assistant prompt.

Distinguish source-backed facts, general background knowledge, and hypothetical responses.
Do not invent locations for fictional case entities or claim certainty about the opponent.
No live web search is included. Calls use the existing LLM gateway and usage accounting;
private chat and raw text stay in gitignored storage. Legacy cases can attach source files
because their original text was not retained by earlier versions.

## Consequences

- Users can ask contextual questions without leaving the current page or losing drafts.
- Chat follows the user across steps and browser restarts; sources persist when chat clears.
- The counterpart never receives personal-assistant messages.
- Raw source classification, like parsed role assignments, needs case review before studies.
- Assisted practice differs from the original unaided rehearsal design; study analysis must
  account for assistant use. Its separate chat artifacts preserve that evidence.
