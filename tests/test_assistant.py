import pytest

from negotrain.assistant import (
    AssistantConversation,
    AssistantMessage,
    answer_question,
    context_sections,
    conversation_key,
    visible_sources,
)
from negotrain.cases.parser import parse_case, parse_documents
from negotrain.feedback import Debrief, build_report
from negotrain.llm import ScriptedLLM
from negotrain.prep import build_prep
from negotrain.schemas import Session, SourceDocument, Turn
from test_parser import parsed_from


def conversation(case):
    return AssistantConversation(case_id=case.id, role_id="candidate")


def rendered(sections):
    return "\n".join(s.title + "\n" + s.text for s in sections)


def session_for(case, status="active"):
    return Session(
        case_id=case.id,
        user_role_id="candidate",
        counterpart_role_id="recruiter",
        status=status,
        notes="INTERNAL_SEED_AND_DIAGNOSTICS",
        turns=[Turn(index=0, speaker="user", text="Could we discuss travel?")],
    )


def test_assistant_only_receives_visible_context_during_rehearsal(case):
    case.role("recruiter").confidential_brief = "OPPONENT_SECRET"
    case.source = "INTERNAL_SCORING_PROVENANCE"
    case.source_documents = [
        SourceDocument(
            name="general.txt",
            text="Qiso is a fictional coastal region.",
            visible_to=["candidate", "recruiter"],
        ),
        SourceDocument(name="my-sheet.txt", text="MY_SOURCE_DETAIL", visible_to=["candidate"]),
        SourceDocument(
            name="their-sheet.txt", text="OPPONENT_SOURCE_SECRET", visible_to=["recruiter"]
        ),
        SourceDocument(name="combined.txt", text="INSTRUCTOR_SECRET", visible_to=[]),
    ]
    chat = conversation(case)
    session = session_for(case)
    before = session.model_dump_json()
    sections = context_sections(
        case,
        "candidate",
        "Rehearse",
        question="Where is Qiso?",
        sources=visible_sources(case, "candidate", chat),
        prep=build_prep(case, "candidate"),
        session=session,
    )
    llm = ScriptedLLM(["Qiso is a fictional coastal region. [Source: general.txt]"])
    reply = answer_question("Where is Qiso?", chat, sections, "Rehearse", llm)
    prompt = str(llm.calls)
    assert "MY_SOURCE_DETAIL" in prompt and "Could we discuss travel?" in prompt
    assert "Preparation brief" in prompt and "Qiso" in reply
    for secret in (
        "OPPONENT_SECRET",
        "OPPONENT_SOURCE_SECRET",
        "INSTRUCTOR_SECRET",
        "INTERNAL_SEED_AND_DIAGNOSTICS",
        "INTERNAL_SCORING_PROVENANCE",
    ):
        assert secret not in prompt
    assert session.model_dump_json() == before
    assert chat.messages == []  # the caller commits successful replies separately


@pytest.mark.parametrize(
    "page,revealed", [("Prepare", False), ("Rehearse", True), ("Feedback", True)]
)
def test_revealed_sheet_and_feedback_follow_the_visible_page(case, page, revealed):
    case.role("recruiter").confidential_brief = "REVEALED_ONLY_AFTER_FINISH"
    session = session_for(case, "impasse")
    debrief = Debrief(report=build_report(session, case))
    text = rendered(context_sections(case, "candidate", page, session=session, debrief=debrief))
    assert ("REVEALED_ONLY_AFTER_FINISH" in text) is revealed
    assert (debrief.report.headline in text) is (page == "Feedback")


def test_mismatched_role_or_case_cannot_supply_transcript_or_revealed_sheet(case):
    session = session_for(case, "impasse")
    session.case_id = "some_other_case"
    text = rendered(context_sections(case, "candidate", "Feedback", session=session))
    assert "Could we discuss travel?" not in text
    assert "Revealed counterpart sheet" not in text
    session.case_id = case.id
    session.user_role_id = "recruiter"
    assert "Could we discuss travel?" not in rendered(
        context_sections(case, "candidate", "Feedback", session=session)
    )


def test_source_retrieval_finds_late_facts_within_budget(case):
    source = SourceDocument(
        name="long.txt",
        text="Unrelated background. " * 5000 + "Qiso is on the north coast.",
        visible_to=["candidate"],
    )
    sections = context_sections(
        case, "candidate", "Prepare", question="Where is Qiso?", sources=[source]
    )
    excerpts = [s for s in sections if s.title.startswith("Source:")]
    assert "Qiso is on the north coast." in rendered(excerpts)
    assert sum(len(s.text) for s in excerpts) <= 24000


def test_conversations_and_attachments_are_separated_by_participant_case_and_role(case):
    assert (
        len(
            {
                conversation_key(*args)
                for args in [
                    ("one", "case", "buyer"),
                    ("two", "case", "buyer"),
                    ("one", "case", "seller"),
                    ("one", "other", "buyer"),
                ]
            }
        )
        == 4
    )
    chat = conversation(case)
    chat.sources = [SourceDocument(name="mine.txt", text="MY_ATTACHMENT", visible_to=["candidate"])]
    assert visible_sources(case, "candidate", chat) == chat.sources
    assert visible_sources(case, "recruiter", chat) == []


def test_assistant_keeps_recent_history_and_labels_hypotheticals(case):
    chat = conversation(case)
    chat.messages = [
        AssistantMessage(role="user", content="I want to ask about travel."),
        AssistantMessage(role="assistant", content="Which travel arrangement?"),
    ]
    llm = ScriptedLLM(["One possible reply is a request to clarify who covers travel."])
    answer_question(
        "What might they say?",
        chat,
        context_sections(case, "candidate", "Rehearse"),
        "Rehearse",
        llm,
    )
    system, messages = llm.calls[0]
    assert "I want to ask about travel." in str(messages)
    assert "hypothetical" in system and "even during rehearsal" in system
    assert "no live web search" in system


def test_blank_or_empty_answers_are_not_recorded(case):
    llm = ScriptedLLM(["   "])
    chat = conversation(case)
    with pytest.raises(ValueError, match="Enter a question"):
        answer_question("  ", chat, [], "Prepare", llm)
    assert not llm.calls
    with pytest.raises(ValueError, match="empty reply"):
        answer_question("Where?", chat, [], "Prepare", llm)
    assert not chat.messages


def test_parser_retains_originals_and_limits_whole_document_access(case):
    parsed = parsed_from(case)
    parsed["source_access"] = [
        {"filename": "public.txt", "audience": "public"},
        {"filename": "own.txt", "audience": "role", "role_id": "candidate"},
        {"filename": "other.txt", "audience": "role", "role_id": "recruiter"},
        {"filename": "mixed.txt", "audience": "mixed"},
        {"filename": "unknown.txt", "audience": "role", "role_id": "stranger"},
    ]
    originals = {
        name: f"Original contents of {name}"
        for name in [
            "public.txt",
            "own.txt",
            "other.txt",
            "mixed.txt",
            "unknown.txt",
            "missing.txt",
        ]
    }
    result = parse_documents(originals, ScriptedLLM([parsed]))
    assert {s.name: s.text for s in result.source_documents} == originals
    allowed = visible_sources(result, "candidate", conversation(result))
    assert {s.name for s in allowed} == {"public.txt", "own.txt"}


def test_pasted_case_retains_original_public_and_role_text(case):
    parsed = parse_case(
        "ORIGINAL_PUBLIC",
        {"candidate": "ORIGINAL_OWN", "recruiter": "ORIGINAL_OTHER"},
        ScriptedLLM([parsed_from(case)]),
    )
    allowed = visible_sources(parsed, "candidate", conversation(parsed))
    assert {s.text for s in allowed} == {"ORIGINAL_PUBLIC", "ORIGINAL_OWN"}
