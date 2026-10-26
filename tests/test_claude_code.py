"""ClaudeCodeLLM against a fake `claude` executable (no network, no Claude Code needed)."""

import json
import os
import stat
import sys

import pytest

from negotrain.counterpart import TIERS, CounterpartAgent, CounterpartMove
from negotrain.llm import ClaudeCodeLLM, LLMRefusal, flatten
from negotrain.schemas import Session

FAKE = """import json, os, sys
args = sys.argv[1:]
prompt = sys.stdin.read()
with open(os.environ["FAKE_LOG"], "w") as f:
    json.dump({{"args": args, "prompt": prompt, "cwd": os.getcwd(),
               "env": [k for k in os.environ if k.startswith("CLAUDE")]}}, f)
print(os.environ["FAKE_REPLY"])
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
"""


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    script = tmp_path / "fake_claude.py"
    script.write_text(FAKE.format())
    # A shell wrapper, because a shebang can't hold an interpreter path with spaces.
    path = tmp_path / "claude"
    path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "log.json"
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("CLAUDECODE", "1")  # as when the app is started from Claude Code
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "parent")

    def reply(data: dict, exit_code: int = 0):
        monkeypatch.setenv("FAKE_REPLY", json.dumps(data))
        monkeypatch.setenv("FAKE_EXIT", str(exit_code))

    def logged() -> dict:
        return json.loads(log.read_text())

    return ClaudeCodeLLM(binary=str(path), effort="low"), reply, logged


def ok(structured=None, result="", **extra):
    usage = {"input_tokens": 3, "output_tokens": 40, "cache_creation_input_tokens": 900}
    return {
        "is_error": False,
        "result": result,
        "structured_output": structured,
        "stop_reason": "end_turn",
        "usage": usage,
        **extra,
    }


def test_parse_uses_json_schema_and_a_clean_child_session(fake_claude):
    llm, reply, logged = fake_claude
    move = {"message": "Hello", "offer": [], "accept": False, "walk_away": False}
    reply(ok(structured=move))
    got = llm.parse("SYSTEM", [{"role": "user", "content": "hi"}], CounterpartMove)
    assert got == CounterpartMove(**move)
    call = logged()
    args = call["args"]
    assert args[:3] == ["-p", "--output-format", "json"]
    assert args[args.index("--system-prompt") + 1] == "SYSTEM"
    assert args[args.index("--tools") + 1] == ""
    assert args[args.index("--effort") + 1] == "low"
    schema = json.loads(args[args.index("--json-schema") + 1])
    assert "offer" in schema["properties"]
    assert "--no-session-persistence" in args and "--bare" not in args  # bare would need a key
    assert call["prompt"] == "hi"
    assert call["env"] == []  # parent Claude Code session variables stripped
    assert os.path.realpath(call["cwd"]) == os.path.realpath(llm.workdir)
    assert llm.usage.calls == 1 and llm.usage.output_tokens == 40


def test_parse_falls_back_to_json_in_result(fake_claude):
    llm, reply, _ = fake_claude
    move = {"message": "Hi", "offer": [], "accept": False, "walk_away": False}
    reply(ok(structured=None, result=json.dumps(move)))
    assert llm.parse("s", [{"role": "user", "content": "x"}], CounterpartMove).message == "Hi"


def test_errors_and_refusals(fake_claude):
    llm, reply, _ = fake_claude
    reply(ok(is_error=True, result="rate limited"))
    with pytest.raises(RuntimeError, match="rate limited"):
        llm.complete("s", [{"role": "user", "content": "x"}])
    reply(ok(stop_reason="refusal"))
    with pytest.raises(LLMRefusal):
        llm.complete("s", [{"role": "user", "content": "x"}])


def test_unparseable_output_raises_with_detail(fake_claude, monkeypatch):
    llm, _, _ = fake_claude
    monkeypatch.setenv("FAKE_REPLY", "not json")
    monkeypatch.setenv("FAKE_EXIT", "1")
    with pytest.raises(RuntimeError, match="exit 1"):
        llm.complete("s", [{"role": "user", "content": "x"}])


def test_flatten_marks_own_turns():
    text = flatten(
        [
            {"role": "user", "content": "Offer A"},
            {"role": "assistant", "content": '{"message": "No"}'},
            {"role": "user", "content": "Offer B"},
        ]
    )
    assert text.index("THEM ---\nOffer A") < text.index("YOU ---") < text.index("Offer B")
    assert text.rstrip().endswith("Write your reply to the last message.")


def test_counterpart_agent_runs_on_claude_code(fake_claude, case):
    llm, reply, logged = fake_claude
    offer = [
        {"issue_id": "salary", "option_id": "s120"},
        {"issue_id": "bonus", "option_id": "b0"},
        {"issue_id": "remote", "option_id": "r0"},
        {"issue_id": "start", "option_id": "w4"},
        {"issue_id": "vacation", "option_id": "v15"},
    ]
    reply(
        ok(structured={"message": "Welcome", "offer": offer, "accept": False, "walk_away": False})
    )
    agent = CounterpartAgent(case, "recruiter", TIERS[3], llm)
    session = Session(case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter")
    turn = agent.respond(session)
    assert turn.offer is not None and agent.fallbacks == 0
    assert case.role("candidate").confidential_brief not in json.dumps(logged())


def test_missing_cli_is_a_clear_error(monkeypatch):
    monkeypatch.setenv("NEGOTRAIN_CLAUDE_BIN", "")
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="not found"):
        ClaudeCodeLLM()


@pytest.mark.live
def test_live_claude_code_round_trip():
    llm = ClaudeCodeLLM(effort="low")
    move = llm.parse(
        "You are a recruiter in a salary negotiation. Reply via the structured output.",
        [{"role": "user", "content": "Hi, can we talk salary?"}],
        CounterpartMove,
    )
    assert move.message
