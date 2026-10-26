"""LLM parsing of raw case documents into a structured ``Case`` (T-004).

Structured outputs work best with flat schemas, so the model fills a list-based
``ParsedCase`` that code converts into ``Case`` (whose point tables are dict-of-dicts).
Validation errors go back to the model once. Always have a human review the JSON before a
case is used in a study: parsed point tables are easy to get subtly wrong.

In a real class exercise a student usually has only their own confidential sheet. With
``infer_missing=True`` the model also writes a plausible sheet for the other side, marked
``inferred``; rehearsing against several sampled counterparts (domain randomization) covers
the fact that it is a guess.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, ValidationError

from negotrain.llm import LLM
from negotrain.schemas import Case, Constraint, Issue, Option, RoleSheet


class ParsedOption(BaseModel):
    id: str = Field(description="Short lowercase slug, unique within the issue, e.g. 's120'")
    label: str


class ParsedIssue(BaseModel):
    id: str = Field(description="Short lowercase slug, e.g. 'salary'")
    name: str
    description: str = ""
    options: list[ParsedOption]


class ParsedPoints(BaseModel):
    issue_id: str
    option_id: str
    points: float


class ParsedConstraint(BaseModel):
    description: str
    issue_id: str
    banned_option_ids: list[str]


class ParsedRole(BaseModel):
    id: str = Field(description="Short lowercase slug, e.g. 'buyer'")
    name: str
    confidential_brief: str = Field(
        description="The role's confidential instructions, condensed but complete, in second person"
    )
    points: list[ParsedPoints] = Field(description="One entry for every option of every issue")
    reservation_value: float = Field(description="Points from walking away without a deal")
    constraints: list[ParsedConstraint] = Field(default_factory=list)
    inferred: bool = Field(description="True if this sheet was not provided and you estimated it")


class ParsedCase(BaseModel):
    id: str = Field(description="Short lowercase slug for the case")
    title: str
    public_brief: str = Field(description="Information both sides have, condensed but complete")
    issues: list[ParsedIssue]
    roles: list[ParsedRole] = Field(description="Exactly two roles")
    scoring_notes: str = Field(
        description="How the point tables were obtained: copied from the case, or estimated "
        "(and how), so a reviewer knows what to check"
    )


SYSTEM = """You convert negotiation exercise materials into a structured case for a \
negotiation training simulator. Code will score every deal from your point tables, so they \
must be exact.

Rules:
- Issues are the terms the parties must settle. Give each a small set of discrete options \
(2-6). If a term is continuous (a price, a date), choose options that span the realistic \
range, including each side's likely targets.
- If the materials give point schedules, copy them exactly. If not, build additive point \
tables that faithfully reflect each role's stated priorities and walk-away alternative, \
on one common scale (for example, the most important issue spans 0-100 points), and explain \
this in scoring_notes.
- The reservation value is the points of the role's best alternative to a negotiated \
agreement (BATNA), on the same scale as the points.
- Every role must have points for every option of every issue.
- Hard constraints ("you cannot accept X") go in constraints with the banned option ids.
- Condense briefs, but keep every fact a negotiator would use.
- If a role's confidential sheet is not provided and you are asked to infer it, write a \
plausible sheet for that role from the public information, mark inferred=true, and say in \
its brief that it is an estimate."""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "x"


def to_case(parsed: ParsedCase, source: str = "") -> Case:
    issues = [
        Issue(
            id=_slug(i.id),
            name=i.name,
            description=i.description,
            options=[Option(id=_slug(o.id), label=o.label) for o in i.options],
        )
        for i in parsed.issues
    ]
    roles = []
    for r in parsed.roles:
        table: dict[str, dict[str, float]] = {}
        for p in r.points:
            table.setdefault(_slug(p.issue_id), {})[_slug(p.option_id)] = p.points
        roles.append(
            RoleSheet(
                id=_slug(r.id),
                name=r.name,
                confidential_brief=r.confidential_brief,
                points=table,
                reservation_value=r.reservation_value,
                constraints=[
                    Constraint(
                        description=c.description,
                        disallowed={_slug(c.issue_id): [_slug(o) for o in c.banned_option_ids]},
                    )
                    for c in r.constraints
                ],
                inferred=r.inferred,
            )
        )
    note = f"Parsed by LLM. {parsed.scoring_notes}".strip()
    if len(roles) != 2:
        raise ValueError(f"expected exactly two roles, got {len(roles)}")
    return Case(
        id=_slug(parsed.id),
        title=parsed.title,
        public_brief=parsed.public_brief,
        issues=issues,
        roles=roles,
        source=f"{source} {note}".strip(),
    )


def _user_message(public_text: str, role_texts: dict[str, str], infer_missing: bool) -> str:
    parts = [f"# Public information\n{public_text.strip()}"]
    for name, text in role_texts.items():
        parts.append(f"# Confidential sheet: {name}\n{text.strip()}")
    if len(role_texts) < 2:
        if infer_missing:
            parts.append(
                "Only one confidential sheet is provided. Infer a plausible sheet for the "
                "other party and mark it inferred=true."
            )
        else:
            parts.append("Only one confidential sheet is provided; include only what is given.")
    return "\n\n".join(parts)


def _parse(messages: list[dict], llm: LLM, source: str) -> Case:
    error = ""
    for _ in range(2):
        parsed = llm.parse(SYSTEM, messages, ParsedCase)
        try:
            return to_case(parsed, source)
        except (ValidationError, ValueError) as e:
            error = str(e)
            messages = messages + [
                {"role": "assistant", "content": parsed.model_dump_json()},
                {
                    "role": "user",
                    "content": f"That case is invalid: {error}\nFix it and reply again.",
                },
            ]
    raise ValueError(f"could not parse a valid case: {error}")


def parse_case(
    public_text: str,
    role_texts: dict[str, str],
    llm: LLM,
    *,
    infer_missing: bool = True,
    source: str = "",
) -> Case:
    """Structured ``Case`` from raw case text. ``role_texts`` maps role name -> sheet text."""
    messages = [{"role": "user", "content": _user_message(public_text, role_texts, infer_missing)}]
    return _parse(messages, llm, source)


def parse_documents(
    documents: dict[str, str],
    llm: LLM,
    *,
    infer_missing: bool = True,
    source: str = "",
) -> Case:
    """Structured ``Case`` from a set of uploaded files (file name -> extracted text).

    The model decides which file holds the public information and which holds each
    party's confidential instructions, so participants can upload everything they were
    given without labeling it.
    """
    parts = [f"# File: {name}\n{text.strip()}" for name, text in documents.items()]
    instruction = (
        "These files are all the materials one participant has for a two-party negotiation "
        "exercise. Work out which parts are public information and which are each party's "
        "confidential instructions (file names and headings are clues)."
    )
    if infer_missing:
        instruction += (
            " If a party's confidential instructions are not among the files, infer a "
            "plausible sheet for that party from the public information and mark it "
            "inferred=true."
        )
    else:
        instruction += " Include only roles whose instructions are provided."
    content = "\n\n".join(parts + [instruction])
    return _parse([{"role": "user", "content": content}], llm, source)
