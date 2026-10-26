"""Headless smoke tests of the Streamlit app in offline mode (rule-based counterpart)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from negotrain.cases import load_case
from negotrain.schemas import Participant
from negotrain.sessions import ParticipantStore, SessionStore

MAIN = Path(__file__).resolve().parents[1] / "src" / "negotrain" / "app" / "main.py"
CASE = Path(__file__).resolve().parents[1] / "data" / "cases" / "cloudline_hiring.json"
TEXT_ELEMENTS = ("markdown", "caption", "info", "success", "error", "warning", "text", "json")


def page_script(name: str) -> None:
    from negotrain.app import views

    views.sidebar()
    getattr(views, name)()


def page(name: str, pid: str | None = "p1") -> AppTest:
    at = AppTest.from_function(page_script, args=(name,), default_timeout=30)
    if pid:
        at.session_state["pid"] = pid
    return at.run()


def visible_text(at: AppTest) -> str:
    return " ".join(str(e.value) for kind in TEXT_ELEMENTS for e in at.get(kind))


def button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.setenv("NEGOTRAIN_OFFLINE", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("NEGOTRAIN_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("NEGOTRAIN_PARTICIPANTS_DIR", str(tmp_path / "participants"))


@pytest.fixture
def onboarded():
    ParticipantStore().save(Participant(id="p1", consented=True))


def test_main_app_starts_and_onboards():
    at = AppTest.from_file(str(MAIN), default_timeout=30).run()
    assert not at.exception
    next(t for t in at.text_input if t.label == "Participant id").input("p9").run()
    consent = next(c for c in at.checkbox if c.label.startswith("I agree"))
    consent.check()
    button(at, "Save and continue").click().run()
    assert not at.exception
    assert ParticipantStore().load("p9").consented


def test_rehearsal_flow_hides_counterpart_sheet_until_the_end(onboarded):
    case = load_case(CASE)
    secret = case.role("recruiter").confidential_brief
    at = page("page_rehearse")
    assert not at.exception
    button(at, "Start rehearsal").click().run()
    assert not at.exception
    at.text_area[0].input("Hi! What matters most to you?")
    next(c for c in at.checkbox if c.label == "Attach a formal offer").check()
    for issue_id, label in [
        ("salary", "$150,000"),
        ("bonus", "$20,000"),
        ("remote", "4 days remote"),
        ("start", "In 4 weeks"),
        ("vacation", "25 days"),
    ]:
        at.selectbox(key=f"o_{issue_id}").select(label)
    button(at, "Send").click().run()
    assert not at.exception
    session = at.session_state["session"]
    assert [t.speaker for t in session.turns] == ["user", "counterpart"]
    assert session.turns[1].offer is not None
    assert secret not in visible_text(at)

    button(at, "✅ Accept their latest offer").click().run()
    assert not at.exception
    assert at.session_state["session"].status == "agreed"
    assert SessionStore().load(session.id).status == "agreed"
    assert secret in visible_text(at)  # revealed in the debrief


def test_feedback_profile_real_and_cases_pages(onboarded):
    at = page("page_rehearse")
    button(at, "Start rehearsal").click().run()
    next(c for c in at.checkbox if c.label == "I'm sure I want to walk away").check().run()
    button(at, "🚪 Walk away").click().run()
    assert at.session_state["session"].status == "impasse"

    fb = page("page_feedback")
    assert not fb.exception
    button(fb, "Generate feedback").click().run()
    assert not fb.exception
    sid = at.session_state["session"].id
    assert (Path(SessionStore().root) / "feedback" / f"{sid}.json").exists()

    for name in ("page_profile", "page_cases", "page_start"):
        assert not page(name).exception, name

    real = page("page_real")
    button(real, "Save real outcome").click().run()
    assert not real.exception
    assert any(s.kind == "real" for s in SessionStore().all())
    assert "Rehearsal vs real" in " ".join(str(h.value) for h in real.subheader)


def test_pages_ask_for_onboarding_first():
    at = page("page_rehearse", pid=None)
    assert not at.exception
    assert "onboarding" in visible_text(at)
