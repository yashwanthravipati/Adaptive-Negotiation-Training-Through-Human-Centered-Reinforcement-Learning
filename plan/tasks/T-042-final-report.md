---
id: T-042
title: Final report
status: in-progress
milestone: M4
workstream: analysis
owner: unassigned
depends_on: [T-040, T-041]
---

## Goal
The final write-up.

## Context
Structure from the course guidelines; reuse docs/results/*.md.

## Acceptance criteria
- [ ] Draft reviewed by all three
- [ ] Submitted

## Log
- 2026-10-28: Added a brief implementation and preliminary-evaluation section to docs/report.tex, covering completed features, sim3 design, offline diagnostics, live gains and paired comparisons. Explicitly distinguishes practice-plus-coaching gains from coaching's unidentified causal effect and preserves the limits from inferred utilities, eight personas, runtime repairs and absent human validation. Team review and submission remain pending.
- 2026-10-28: Introduced the implemented cost-weighted UCB focus rule and greedy, uniform-random and no-focus comparison baselines in the methods, before the learning objective. Defines deficit, uncertainty, costs and opportunities; makes explicit that greedy also updates, all groups receive feedback, and selected kappa=0 makes UCB and greedy identical on the same observations.
- 2026-10-28: At the user's request, shortened the policy/baseline explanation to four plain-language sentences, retaining the selection factors, uncertainty distinction, shared feedback/difficulty and selected kappa=0 equivalence.
- 2026-10-28: Simplified the paragraph further to the user's requested wording, explaining uncertainty as extra priority for areas we know less about and removing the methods tuning sentence. The results still disclose the selected zero bonus; the policy does not add random noise.
- 2026-10-28: Rewrote the implementation as one connected paragraph explaining controlled bargaining, replay-based feedback and how observations guide the next rehearsal. Preserved the prior-update and deadline implementation distinctions in a footnote instead of a feature list.
- 2026-10-28: At the user's request, removed the offline-results and interpretation paragraphs from the short report, rewrote the design around Simulation 3 materials and eight sampled LLM personas tested under all four mechanisms, and renamed Live results to Results. Added next steps retaining the formalism while exploring coach policies based on observed learning gains. Detailed diagnostics remain in docs/results/sim3_evaluation.md.
- 2026-10-28: Rephrased the performance definition to use "G as the average score" as requested.
- 2026-10-28: Added iteration on the coach's system prompts as a possible next step for improving feedback clarity and usefulness.
- 2026-10-28: Removed confidence-interval and bootstrap references from the short report's prose and table at the user's request; mean gains and the underlying detailed evaluation artifacts are unchanged.
- 2026-10-28: Reworded the policy comparison to explicitly describe differences in mean G gain, using the user's requested phrasing.
- 2026-10-28: Explained that the zero uncertainty bonus was a tentative development choice because it maximized simulated error-cost reduction, making adaptive and greedy the same rule in this evaluation.
