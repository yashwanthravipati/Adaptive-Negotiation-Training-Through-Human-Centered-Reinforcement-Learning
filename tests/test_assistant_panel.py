import pytest
from streamlit.testing.v1 import AppTest

from negotrain.assistant import AssistantConversation, conversation_key
from negotrain.cases import save_private_case
from negotrain.llm import ScriptedLLM
from negotrain.prep import build_prep, prep_key
from negotrain.schemas import Session, Turn
from negotrain.sessions import SessionStore


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch, case):
    monkeypatch.setenv("NEGOTRAIN_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("NEGOTRAIN_CASES_DIR", str(tmp_path / "cases"))
    monkeypatch.setenv("NEGOTRAIN_OFFLINE", "1")
    monkeypatch.setenv("NEGOTRAIN_PARTICIPANT", "local")
    save_private_case(case)
    from negotrain.app import views

    views.set_active_scenario(case.id, "candidate")
    SessionStore().save_artifact(
        prep_key("local", case.id, "candidate"), "prep", build_prep(case, "candidate")
    )


def script(name, title):
    from negotrain.app import assistant_panel, views

    views.sidebar()
    getattr(views, name)()
    assistant_panel.render(title)


def page(name="page_prepare", title="Prepare"):
    return AppTest.from_function(script, args=(name, title), default_timeout=30).run()


def online(monkeypatch, replies):
    from negotrain.app import views

    llm = ScriptedLLM(replies)
    monkeypatch.setattr(views, "online", lambda: True)
    monkeypatch.setattr(views, "llm", lambda effort=None: llm)
    monkeypatch.setattr(views, "_total_calls", lambda: 0)
    monkeypatch.setattr(views, "_total_cost", lambda: 0.0)
    return llm


def saved(case):
    return SessionStore().load_artifact(
        conversation_key("local", case.id, "candidate"), "assistant", AssistantConversation
    )


def test_chat_persists_across_steps_and_restarts_without_sending_negotiation_turns(
    case, monkeypatch
):
    llm = online(
        monkeypatch,
        [
            "Qiso is not located in the current materials.",
            "One possible reply is to ask about implementation.",
        ],
    )
    at = page()
    assert not at.exception
    at.chat_input[0].set_value("Where is Qiso?").run()
    assert not at.exception
    assert len(saved(case).messages) == 2
    assert not SessionStore().all()
    rehearse = page("page_rehearse", "Rehearse")
    assert not rehearse.exception
    assert "Where is Qiso?" in " ".join(str(m.value) for m in rehearse.markdown)
    rehearse.chat_input[0].set_value("What might they say if I proposed joint registration?").run()
    assert not rehearse.exception
    assert len(saved(case).messages) == 4
    assert len(llm.calls) == 2
    assert not SessionStore().all()

    session = Session(
        case_id=case.id,
        participant_id="local",
        user_role_id="candidate",
        counterpart_role_id="recruiter",
        status="impasse",
    )
    SessionStore().save(session)
    feedback = page("page_feedback", "Feedback")
    assert not feedback.exception
    assert "joint registration" in " ".join(str(m.value) for m in feedback.markdown)


def test_failed_answer_can_be_retried_without_duplicate_questions(case, monkeypatch):
    def fail(system, messages):
        raise RuntimeError("service unavailable")

    llm = online(monkeypatch, [fail, "Here is the answer."])
    at = page()
    at.chat_input[0].set_value("What is my role?").run()
    assert not at.exception and at.error
    assert saved(case).pending_question == "What is my role?"
    next(b for b in at.button if b.label == "Retry answer").click().run()
    assert not at.exception
    assert saved(case).pending_question is None
    assert len(saved(case).messages) == 2 and len(llm.calls) == 2


def test_failed_question_can_be_rephrased_without_duplicate_retry_buttons(case, monkeypatch):
    def fail(system, messages):
        raise RuntimeError("temporary failure")

    online(monkeypatch, [fail, fail, "Answer to the revised question."])
    at = page()
    at.chat_input[0].set_value("First question").run()
    at.chat_input[0].set_value("Revised question").run()
    assert not at.exception
    retry = [b for b in at.button if b.label == "Retry answer"]
    assert len(retry) == 1
    retry[0].click().run()
    assert not at.exception
    assert [m.content for m in saved(case).messages if m.role == "user"] == ["Revised question"]


def test_attachments_are_private_to_role_and_new_chat_keeps_sources(case, monkeypatch):
    online(monkeypatch, ["Qiso is fictional. [Added: facts.txt]"])
    at = page()
    next(u for u in at.file_uploader if u.label == "Add source documents").set_value(
        [("facts.txt", b"Qiso is a fictional place in this exercise.", "text/plain")]
    ).run()
    next(b for b in at.button if b.label == "Add to assistant").click().run()
    assert not at.exception
    assert saved(case).sources[0].visible_to == ["candidate"]
    at.chat_input[0].set_value("Where is Qiso?").run()
    next(b for b in at.button if b.label == "New chat").click().run()
    assert not at.exception
    assert saved(case).messages == [] and len(saved(case).sources) == 1


def test_offline_panel_does_not_call_api_or_change_existing_session(case, monkeypatch):
    from negotrain.app import views

    monkeypatch.setattr(views, "online", lambda: False)
    monkeypatch.setattr(views, "llm", lambda *args: pytest.fail("offline must not call the API"))
    session = Session(
        case_id=case.id,
        participant_id="local",
        user_role_id="candidate",
        counterpart_role_id="recruiter",
        turns=[Turn(index=0, speaker="user", text="My offer")],
    )
    SessionStore().save(session)
    at = page()
    assert not at.exception and at.chat_input[0].disabled
    assert SessionStore().load(session.id) == session
