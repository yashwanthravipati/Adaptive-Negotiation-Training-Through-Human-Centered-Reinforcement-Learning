"""Pre-negotiation preparation brief for one role in one case (T-045).

Before rehearsing a specific scenario, the participant gets an overview of the case, their
priorities, their walk-away and targets, hypotheses about the other side, questions to
ask, and a short checklist. Preparation happens before the negotiation, so this is
consistent with decision 0002 (no live recommendations *during* a negotiation).

Information hiding: the brief is built from the public information and the participant's
own sheet only. The other side's sheet (real or inferred) never reaches the prompt, so
everything said about the other side is a hypothesis to test. All numbers come from code.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from negotrain.cases.offers import best_offer_for, best_points
from negotrain.llm import LLM
from negotrain.schemas import Case

TARGET_SHARE = 0.75  # ambitious-but-defensible target: 75% of the way from walk-away to best


class IssuePriority(BaseModel):
    issue_id: str
    name: str
    rank: int  # 1 = matters most to you
    spread: float  # points between your best and worst option
    share: float  # spread as a share of all your spreads
    best_option: str
    worst_option: str


class PrepNumbers(BaseModel):
    role_id: str
    walk_away: float
    best_possible: float
    target: float
    best_deal: str
    priorities: list[IssuePriority]


class PrepBrief(BaseModel):
    overview: str = Field(description="A short paragraph: who, what, why it matters")
    key_facts: list[str] = Field(description="Facts from the materials a negotiator must know")
    your_interests: list[str] = Field(description="What you want and why, from your sheet")
    their_likely_interests: list[str] = Field(
        description="Hypotheses about the other side, each phrased as something to test"
    )
    tradeoffs: list[str] = Field(description="Where to hold firm and where to give, and why")
    questions_to_ask: list[str]
    opening_plan: str = Field(description="How to open: tone, framing, and what to anchor on")
    pitfalls: list[str] = Field(description="Mistakes to avoid in this particular case")
    checklist: list[str] = Field(description="Three to six key points to remember")
    source: str = "template"


class Prep(BaseModel):
    """What the Prepare page stores per participant, case, and role."""

    case_id: str
    role_id: str
    numbers: PrepNumbers
    brief: PrepBrief


def priorities(case: Case, role_id: str) -> list[IssuePriority]:
    role = case.role(role_id)
    rows = []
    for issue in case.issues:
        table = role.points[issue.id]
        best = max(issue.options, key=lambda o: table[o.id])
        worst = min(issue.options, key=lambda o: table[o.id])
        rows.append((issue, table[best.id] - table[worst.id], best.label, worst.label))
    total = sum(spread for _, spread, _, _ in rows) or 1.0
    rows.sort(key=lambda r: -r[1])
    return [
        IssuePriority(
            issue_id=issue.id,
            name=issue.name,
            rank=n + 1,
            spread=spread,
            share=spread / total,
            best_option=best,
            worst_option=worst,
        )
        for n, (issue, spread, best, worst) in enumerate(rows)
    ]


def prep_numbers(case: Case, role_id: str) -> PrepNumbers:
    rv = case.role(role_id).reservation_value
    best = best_points(case, role_id)
    return PrepNumbers(
        role_id=role_id,
        walk_away=rv,
        best_possible=best,
        target=rv + TARGET_SHARE * max(0.0, best - rv),
        best_deal=best_offer_for(case, role_id).describe(case),
        priorities=priorities(case, role_id),
    )


SYSTEM = """You are a negotiation coach helping a student prepare for a negotiation \
exercise they are about to rehearse and then do for real. Write a preparation brief from \
their side only.

You see the public information and the student's own confidential sheet. You do NOT know \
the other side's confidential information: phrase everything about the other side as a \
hypothesis to test at the table ("they may...", "find out whether..."). Use only numbers \
given in the input; never invent point values. Be concrete and specific to this case, \
concise, and practical. The opening plan describes how to open (tone, framing, what to \
anchor on and why), grounded in the student's priorities."""


def _prompt(case: Case, role_id: str, numbers: PrepNumbers) -> str:
    role = case.role(role_id)
    table = "\n".join(
        f"{p.rank}. {p.name}: best = {p.best_option}, worst = {p.worst_option}, "
        f"spread {p.spread:g} points ({p.share:.0%} of what is at stake for you)"
        for p in numbers.priorities
    )
    options = "\n".join(
        f"- {i.name}: " + ", ".join(f"{o.label} ({role.points[i.id][o.id]:g})" for o in i.options)
        for i in case.issues
    )
    return f"""# Case: {case.title}
{case.public_brief}

# The student's role: {role.name} (confidential)
{role.confidential_brief}

# The student's points per option
{options}

# Computed by code
- Walk-away (no deal) value: {numbers.walk_away:g}
- Best possible deal for the student: {numbers.best_possible:g} ({numbers.best_deal})
- Ambitious target: {numbers.target:g}
- Issues ranked by what is at stake for the student:
{table}

Write the preparation brief."""


def template_brief(case: Case, numbers: PrepNumbers) -> PrepBrief:
    top, bottom = numbers.priorities[0], numbers.priorities[-1]
    return PrepBrief(
        overview=case.public_brief,
        key_facts=[
            f"Your walk-away value is {numbers.walk_away:g} points; never accept less.",
            f"Your best possible deal is worth {numbers.best_possible:g} points.",
            f"{top.name} matters most to you ({top.share:.0%} of what is at stake).",
        ],
        your_interests=[
            f"{p.name}: you prefer {p.best_option} (worth {p.spread:g} more than {p.worst_option})"
            for p in numbers.priorities[:3]
        ],
        their_likely_interests=[
            "Find out which issues matter most to them; their priorities probably differ "
            "from yours, which is what makes trades possible.",
        ],
        tradeoffs=[
            f"Hold firm on {top.name}; it carries the most points for you.",
            f"Be ready to give ground on {bottom.name} in exchange for movement on {top.name}.",
        ],
        questions_to_ask=[
            "Which of these terms matters most to you, and why?",
            "What would make this deal work for you?",
            "What constraints are you working under?",
        ],
        opening_plan=(
            f"Open warmly, then anchor ambitiously on {top.name}, near your best option "
            f"({top.best_option}), leaving room to concede on lower-priority issues."
        ),
        pitfalls=[
            "Conceding before the other side does.",
            "Negotiating one issue at a time instead of packaging trades.",
            "Accepting a deal below your walk-away value.",
        ],
        checklist=[
            f"Walk-away: {numbers.walk_away:g}. Target: {numbers.target:g}.",
            f"Top priority: {top.name}. Most tradeable: {bottom.name}.",
            "Ask before you offer; trade, don't give.",
        ],
        source="template",
    )


def build_prep(case: Case, role_id: str, llm: LLM | None = None) -> Prep:
    numbers = prep_numbers(case, role_id)
    brief = None
    if llm is not None:
        try:
            brief = llm.parse(
                SYSTEM,
                [{"role": "user", "content": _prompt(case, role_id, numbers)}],
                PrepBrief,
            ).model_copy(update={"source": "llm"})
        except Exception:  # noqa: BLE001 - fall back to the template; prep must render
            brief = None
    return Prep(
        case_id=case.id,
        role_id=role_id,
        numbers=numbers,
        brief=brief or template_brief(case, numbers),
    )


def prep_key(participant_id: str, case_id: str, role_id: str) -> str:
    """Artifact key for SessionStore.save_artifact (one brief per participant, case, role)."""
    return f"{participant_id}__{case_id}__{role_id}"
