from negotrain.schemas import Session, Turn
from negotrain.sessions import SessionStore


def test_round_trip(tmp_path, case):
    store = SessionStore(tmp_path)
    s = Session(case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter")
    s.add_turn(Turn(index=0, speaker="user", text="Hello"), case)
    store.save(s)
    assert store.load(s.id) == s
    assert [x.id for x in store.all()] == [s.id]
