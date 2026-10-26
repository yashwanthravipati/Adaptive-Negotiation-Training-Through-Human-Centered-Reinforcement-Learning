"""Headless smoke tests of the Streamlit app in offline mode (rule-based counterpart)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from negotrain.cases import load_case
from negotrain.sessions import SessionStore

MAIN = Path(__file__).resolve().parents[1] / "src" / "negotrain" / "app" / "main.py"
CASE = Path(__file__).resolve().parents[1] / "data" / "cases" / "cloudline_hiring.json"
TEXT_ELEMENTS = ("markdown", "caption", "info", "success", "error", "warning", "text", "json")


def page_script(name: str) -> None:
    from negotrain.app import views

    views.sidebar()
    getattr(views, name)()


def page(name: str) -> AppTest:
    return AppTest.from_function(page_script, args=(name,), default_timeout=30).run()


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


@pytest.fixture
def scenario():
    """An active scenario: the candidate role in the committed sample case."""
    from negotrain.app.views import ActiveScenario

    SessionStore().save_artifact(
        "current", "state", ActiveScenario(case_id="cloudline_hiring", role_id="candidate")
    )


def test_app_opens_on_upload_and_unlocks_after_choosing_a_scenario():
    at = AppTest.from_file(str(MAIN), default_timeout=30).run()
    assert not at.exception
    assert "Start with your case." in visible_text(at)
    assert not [b for b in at.button if b.label == "📂 New scenario"]  # nothing unlocked yet

    button(at, "Use this case").click().run()
    button(at, "Start training →").click().run()
    assert not at.exception
    # Now on Prepare (the default page once a scenario is active), with the brief written.
    text = visible_text(at)
    assert "Prepare" in text and "Checklist" in text
    assert load_case(CASE).role("recruiter").confidential_brief not in text

    button(at, "📂 New scenario").click().run()
    assert "Start with your case." in visible_text(at)


def test_rehearsal_flow_hides_counterpart_sheet_until_the_end(scenario):
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


def test_feedback_profile_real_and_cases_pages(scenario):
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

    for name in ("page_profile", "page_cases", "page_setup"):
        assert not page(name).exception, name

    real = page("page_real")
    button(real, "Save real outcome").click().run()
    assert not real.exception
    assert any(s.kind == "real" for s in SessionStore().all())
    assert "Rehearsal vs real" in " ".join(str(h.value) for h in real.subheader)


def test_prepare_writes_brief_and_training_plan_starts_rehearsals(scenario):
    at = page("page_prepare")
    assert not at.exception
    text = visible_text(at)
    assert "Checklist" in text and "Training plan" in " ".join(str(h.value) for h in at.subheader)
    case = load_case(CASE)
    assert case.role("recruiter").confidential_brief not in text
    button(at, "Start").click().run()  # first training step: warm-up, tier 2
    assert not at.exception
    session = at.session_state["session"]
    assert session.case_id == case.id and session.counterpart_profile.tier == 2


def test_upload_builds_a_scenario(tmp_path, monkeypatch):
    import shutil

    from negotrain.app import views
    from negotrain.llm import ScriptedLLM
    from test_parser import parsed_from

    cases = tmp_path / "cases"
    cases.mkdir()
    shutil.copy(CASE, cases)
    monkeypatch.setenv("NEGOTRAIN_CASES_DIR", str(cases))
    uploaded = parsed_from(load_case(CASE)) | {"id": "uploaded_case", "title": "Uploaded"}
    uploaded["roles"][1]["inferred"] = True
    scripted = ScriptedLLM([uploaded])
    monkeypatch.setattr(views, "online", lambda: True)
    monkeypatch.setattr(views, "llm", lambda effort=None: scripted)
    monkeypatch.setattr(views, "_total_calls", lambda: 0)
    monkeypatch.setattr(views, "_total_cost", lambda: 0.0)

    at = page("page_setup")
    at.file_uploader[0].set_value(
        [
            ("general.txt", b"Public info about the hiring.", "text/plain"),
            ("candidate.md", b"My confidential sheet.", "text/markdown"),
            ("scan.pdf", b"not really a pdf", "application/pdf"),
        ]
    )
    at.run()
    button(at, "Build scenario").click().run()
    assert not at.exception
    assert (cases / "private" / "uploaded_case.json").exists()
    assert "general.txt" in scripted.calls[0][1][0]["content"]
    assert any("scan.pdf" in str(w.value) for w in at.warning)  # unreadable file reported
    assert at.session_state["setup_case_id"] == "uploaded_case"
    # The uploaded sheet's role is preselected; the other side is marked as estimated.
    assert "estimated version" in visible_text(at)
    button(at, "Start training →").click().run()
    assert views.active_scenario()[0].id == "uploaded_case"


def test_dollar_amounts_are_escaped_for_markdown():
    from negotrain.app.style import md

    assert md("$120,000 or $150,000") == "\\$120,000 or \\$150,000"
