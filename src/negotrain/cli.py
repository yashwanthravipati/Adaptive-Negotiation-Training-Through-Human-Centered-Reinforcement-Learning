"""`negotrain` command: inspect cases and rehearse against the counterpart in a terminal."""

from __future__ import annotations

import argparse
import random

from negotrain.cases import load_case
from negotrain.cases.scoring import efficiency, joint_points, max_joint_offer, score_offer
from negotrain.counterpart import CounterpartAgent, sample_profile
from negotrain.llm import ClaudeLLM
from negotrain.schemas import Case, Offer, Session, Turn
from negotrain.sessions import SessionStore

HELP = """Type a message and press enter. Commands:
  /offer issue=option ... -- message   make a formal offer (use the ids shown above)
  /accept [message]                    accept the counterpart's latest offer
  /walk [message]                      walk away
  /quit                                stop without recording an outcome"""


def show(case: Case) -> None:
    print(f"{case.title}  ({case.id})\n\n{case.public_brief}\n")
    for issue in case.issues:
        print(f"  {issue.id}: " + ", ".join(f"{o.id}={o.label}" for o in issue.options))
    print()
    for role in case.roles:
        print(f"Role {role.id} ({role.name}): reservation value {role.reservation_value:g}")
    best = max_joint_offer(case)
    print(f"\nMax joint points: {joint_points(case, best):g}  via {best.describe(case)}")


def _parse_user(line: str, index: int) -> Turn | None:
    if line.startswith("/offer"):
        spec, _, message = line.removeprefix("/offer").partition("--")
        terms = dict(pair.split("=", 1) for pair in spec.split())
        return Turn(index=index, speaker="user", text=message.strip(), offer=Offer(terms=terms))
    if line.startswith("/accept"):
        return Turn(
            index=index, speaker="user", text=line.removeprefix("/accept").strip(), accept=True
        )
    if line.startswith("/walk"):
        return Turn(
            index=index, speaker="user", text=line.removeprefix("/walk").strip(), walk_away=True
        )
    if line.startswith("/"):
        return None
    return Turn(index=index, speaker="user", text=line)


def play(case: Case, role_id: str, tier: int, seed: int | None, participant: str) -> None:
    counterpart_role = case.other_role(role_id)
    profile = sample_profile(tier, random.Random(seed))
    agent = CounterpartAgent(case, counterpart_role.id, profile, ClaudeLLM())
    session = Session(
        participant_id=participant,
        case_id=case.id,
        user_role_id=role_id,
        counterpart_role_id=counterpart_role.id,
        counterpart_profile=profile,
    )
    store = SessionStore()
    you = case.role(role_id)
    print(f"You are {you.name}.\n\n{you.confidential_brief}\n")
    for issue_id, table in you.points.items():
        print(f"  {issue_id}: " + ", ".join(f"{k}={v:g}" for k, v in table.items()))
    print(f"  walk-away value: {you.reservation_value:g}\n\n{HELP}\n")

    while session.status == "active":
        line = input("you> ").strip()
        if line == "/quit":
            session.status = "abandoned"
            break
        turn = _parse_user(line, len(session.turns)) if line else None
        if turn is None:
            print(HELP)
            continue
        try:
            session.add_turn(turn, case)
        except ValueError as e:
            print(f"  ! {e}")
            continue
        store.save(session)
        if session.status != "active":
            break
        reply = agent.respond(session)
        session.add_turn(reply, case)
        store.save(session)
        print(f"\n{counterpart_role.name}> {reply.text}")
        if reply.offer:
            mine = score_offer(case, role_id, reply.offer)
            value = (
                "custom terms, not scored"
                if mine.points is None
                else f"worth {mine.points:g} to you"
            )
            print(f"  [offer: {reply.offer.describe(case)}]  ({value})")
        print()

    print(f"Session {session.id}: {session.status}")
    if session.agreement:
        mine = score_offer(case, role_id, session.agreement)
        print(f"Deal: {session.agreement.describe(case)}")
        if mine.points is None:
            print("Custom terms: no defined point score or numeric efficiency.")
        else:
            print(f"Your points: {mine.points:g} (surplus {mine.surplus:+g} over walking away)")
            print(f"Efficiency: {efficiency(case, session.agreement):.0%} of max joint points")
    print(f"Saved to {store.root / (session.id + '.json')}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="negotrain")
    sub = parser.add_subparsers(dest="command", required=True)

    p_show = sub.add_parser("show", help="summarize a case file")
    p_show.add_argument("case")

    p_play = sub.add_parser("play", help="rehearse against the counterpart (calls the API)")
    p_play.add_argument("case")
    p_play.add_argument("--role", required=True, help="the role you play")
    p_play.add_argument("--tier", type=int, default=2, choices=range(1, 6))
    p_play.add_argument("--seed", type=int, default=None)
    p_play.add_argument("--participant", default="dev")

    args = parser.parse_args(argv)
    case = load_case(args.case)
    if args.command == "show":
        show(case)
    else:
        play(case, args.role, args.tier, args.seed, args.participant)


if __name__ == "__main__":
    main()
