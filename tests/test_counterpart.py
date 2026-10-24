import pytest

from negotrain.counterpart import TIERS, CounterpartAgent
from negotrain.llm import ScriptedLLM
from negotrain.schemas import Offer, Session, Turn

FULL = {"salary": "s140", "bonus": "b0", "remote": "r4", "start": "w4", "vacation": "v20"}


def move(message="Hi", offer=None, accept=False, walk_away=False):
    terms = [{"issue_id": k, "option_id": v} for k, v in (offer or {}).items()]
    return {"message": message, "offer": terms, "accept": accept, "walk_away": walk_away}


def setup(case, script):
    llm = ScriptedLLM(script)
    agent = CounterpartAgent(case, "recruiter", TIERS[3], llm)
    session = Session(case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter")
    return agent, session, llm


def test_system_prompt_has_own_sheet_but_not_the_users(case):
    agent, _, _ = setup(case, [])
    assert case.role("recruiter").confidential_brief in agent.system
    assert case.role("candidate").confidential_brief not in agent.system


def test_opening_move_when_counterpart_speaks_first(case):
    agent, session, llm = setup(case, [move("Welcome!", offer=FULL)])
    turn = agent.respond(session)
    assert turn.speaker == "counterpart" and turn.offer == Offer(terms=FULL)
    _, messages = llm.calls[0]
    assert messages[0]["role"] == "user"


def test_history_alternates_and_ends_with_user(case):
    agent, session, llm = setup(case, [move("Fine."), move("Let's talk bonus.")])
    session.add_turn(Turn(index=0, speaker="user", text="Hello"), case)
    session.add_turn(agent.respond(session), case)
    session.add_turn(Turn(index=2, speaker="user", text="What about remote work?"), case)
    agent.respond(session)
    roles = [m["role"] for m in llm.calls[-1][1]]
    assert roles == ["user", "assistant", "user"]


def test_invalid_option_triggers_retry(case):
    agent, session, llm = setup(case, [move(offer={"salary": "s999"}), move(offer=FULL)])
    turn = agent.respond(session)
    assert turn.offer == Offer(terms=FULL)
    assert "invalid move" in llm.calls[1][1][-1]["content"]


def test_will_not_accept_below_reservation_value(case):
    greedy = {"salary": "s150", "bonus": "b20", "remote": "r4", "start": "w8", "vacation": "v25"}
    agent, session, _ = setup(case, [move(accept=True)] * 3)
    session.add_turn(
        Turn(index=0, speaker="user", text="Take it.", offer=Offer(terms=greedy)), case
    )
    with pytest.raises(RuntimeError, match="no valid move"):
        agent.respond(session)
