import pytest

from negotrain.cases.parser import ParsedCase, parse_case
from negotrain.llm import ScriptedLLM


def parsed_from(case) -> dict:
    """The ParsedCase the model would return for ``case`` (inverse of to_case)."""
    return ParsedCase(
        id=case.id,
        title=case.title,
        public_brief=case.public_brief,
        issues=[
            {
                "id": i.id,
                "name": i.name,
                "options": [{"id": o.id, "label": o.label} for o in i.options],
            }
            for i in case.issues
        ],
        roles=[
            {
                "id": r.id,
                "name": r.name,
                "confidential_brief": r.confidential_brief,
                "points": [
                    {"issue_id": i, "option_id": o, "points": p}
                    for i, t in r.points.items()
                    for o, p in t.items()
                ],
                "reservation_value": r.reservation_value,
                "inferred": False,
            }
            for r in case.roles
        ],
        scoring_notes="Copied from the case.",
    ).model_dump()


def test_parser_recovers_the_case(case):
    llm = ScriptedLLM([parsed_from(case)])
    got = parse_case(case.public_brief, {"Candidate": "...", "Recruiter": "..."}, llm)
    assert got.issues == case.issues
    assert [r.points for r in got.roles] == [r.points for r in case.roles]
    assert "Copied" in got.source


def test_parser_retries_once_on_invalid_case_then_gives_up(case):
    broken = parsed_from(case)
    broken["roles"][0]["points"] = broken["roles"][0]["points"][:-1]  # missing an option
    llm = ScriptedLLM([broken, parsed_from(case)])
    assert parse_case("x", {"A": "y"}, llm).id == case.id
    assert "invalid" in llm.calls[1][1][-1]["content"]
    with pytest.raises(ValueError, match="could not parse"):
        parse_case("x", {"A": "y"}, ScriptedLLM([broken, broken]))


def test_parser_asks_to_infer_a_missing_sheet(case):
    llm = ScriptedLLM([parsed_from(case)])
    parse_case("public", {"Candidate": "mine"}, llm)
    assert "Infer a plausible sheet" in llm.calls[0][1][0]["content"]
