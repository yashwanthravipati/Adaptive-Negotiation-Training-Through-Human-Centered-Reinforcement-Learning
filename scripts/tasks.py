#!/usr/bin/env python3
"""Task board for plan/tasks/*.md. Standard library only, so it runs without the venv.

python scripts/tasks.py                     board (open tasks grouped by status)
python scripts/tasks.py next [--owner X]    todo tasks whose dependencies are all done
python scripts/tasks.py list [--status S] [--milestone M] [--owner O] [--workstream W]
python scripts/tasks.py show T-010
python scripts/tasks.py new "Title" --milestone M1 --workstream counterpart [--depends T-010]
python scripts/tasks.py set T-010 status=in-progress owner=yash [--note "picked up"]
python scripts/tasks.py check               validate all task files (run in CI)
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "plan" / "tasks"
TEMPLATE = ROOT / "plan" / "templates" / "task.md"

STATUSES = ["in-progress", "review", "blocked", "todo", "done"]
WORKSTREAMS = ["cases", "counterpart", "feedback", "profiling", "app", "study", "analysis", "infra"]
REQUIRED = ["id", "title", "status", "milestone", "workstream", "owner", "depends_on"]
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def parse(path: Path) -> dict:
    match = FRONTMATTER.match(path.read_text())
    if not match:
        raise ValueError(f"{path.name}: missing frontmatter")
    meta: dict = {"path": path}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        value = value.split(" #", 1)[0].strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key.strip()] = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key.strip()] = value.strip("\"'")
    return meta


def load() -> list[dict]:
    return sorted((parse(p) for p in TASKS.glob("T-*.md")), key=lambda t: t["id"])


def find(tasks: list[dict], task_id: str) -> dict:
    for t in tasks:
        if t["id"] == task_id.upper():
            return t
    sys.exit(f"no task {task_id}")


def row(t: dict) -> str:
    owner = "" if t["owner"] in ("", "unassigned") else f"  @{t['owner']}"
    deps = f"  (after {', '.join(t['depends_on'])})" if t["depends_on"] else ""
    return f"  {t['id']}  [{t['milestone']}/{t['workstream']}]  {t['title']}{owner}{deps}"


def ready(t: dict, by_id: dict) -> bool:
    return t["status"] == "todo" and all(
        by_id.get(d, {}).get("status") == "done" for d in t["depends_on"]
    )


def cmd_board(tasks: list[dict], show_done: bool) -> None:
    for status in STATUSES:
        group = [t for t in tasks if t["status"] == status]
        if status == "done" and not show_done:
            print(f"\nDONE ({len(group)}; --all to list)")
            continue
        print(f"\n{status.upper()} ({len(group)})")
        for t in group:
            print(row(t))


def cmd_set(tasks: list[dict], task_id: str, pairs: list[str], note: str | None) -> None:
    t = find(tasks, task_id)
    text = t["path"].read_text()
    match = FRONTMATTER.match(text)
    front, body = match.group(1), text[match.end() :]
    for pair in pairs:
        key, _, value = pair.partition("=")
        if key == "status" and value not in STATUSES:
            sys.exit(f"status must be one of {STATUSES}")
        if not re.search(rf"^{re.escape(key)}:", front, re.M):
            sys.exit(f"{t['id']} has no field {key!r}")
        front = re.sub(rf"^{re.escape(key)}:.*$", f"{key}: {value}", front, flags=re.M)
    if note:
        entry = f"- {date.today().isoformat()}: {note}"
        body = (
            body.rstrip("\n") + "\n" + entry + "\n"
            if "## Log" in body
            else (body.rstrip("\n") + f"\n\n## Log\n{entry}\n")
        )
    t["path"].write_text(f"---\n{front}\n---\n{body}")
    print(f"updated {t['path'].relative_to(ROOT)}")


def cmd_new(tasks: list[dict], title: str, milestone: str, workstream: str, deps: str) -> None:
    next_num = max((int(t["id"][2:]) for t in tasks), default=0) + 1
    task_id = f"T-{next_num:03d}"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48]
    path = TASKS / f"{task_id}-{slug}.md"
    text = TEMPLATE.read_text()
    for key, value in {
        "ID": task_id,
        "TITLE": title,
        "MILESTONE": milestone,
        "WORKSTREAM": workstream,
        "DEPENDS": ", ".join(d.strip().upper() for d in deps.split(",") if d.strip()),
    }.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    path.write_text(text)
    print(f"created {path.relative_to(ROOT)}")


def cmd_check(tasks: list[dict]) -> int:
    errors = []
    ids = [t.get("id") for t in tasks]
    by_id = {t["id"]: t for t in tasks if "id" in t}
    for t in tasks:
        name = t["path"].name
        for key in REQUIRED:
            if key not in t:
                errors.append(f"{name}: missing {key}")
        if "id" in t and not name.startswith(t["id"] + "-"):
            errors.append(f"{name}: filename must start with its id {t['id']}")
        if ids.count(t.get("id")) > 1:
            errors.append(f"{name}: duplicate id {t.get('id')} (renumber one of them)")
        if t.get("status") not in STATUSES:
            errors.append(f"{name}: bad status {t.get('status')!r}")
        if t.get("workstream") not in WORKSTREAMS:
            errors.append(f"{name}: bad workstream {t.get('workstream')!r}")
        if not re.fullmatch(r"M\d", t.get("milestone", "")):
            errors.append(f"{name}: milestone should look like M0..M9")
        for dep in t.get("depends_on", []):
            if dep not in by_id:
                errors.append(f"{name}: depends on unknown task {dep}")
    for e in sorted(set(errors)):
        print(e)
    print(f"{len(tasks)} tasks, {len(set(errors))} problems")
    return 1 if errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="command")
    p_board = sub.add_parser("board")
    p_board.add_argument("--all", action="store_true")
    p_next = sub.add_parser("next")
    p_next.add_argument("--owner")
    p_list = sub.add_parser("list")
    for flag in ("status", "milestone", "owner", "workstream"):
        p_list.add_argument(f"--{flag}")
    sub.add_parser("show").add_argument("id")
    p_new = sub.add_parser("new")
    p_new.add_argument("title")
    p_new.add_argument("--milestone", required=True)
    p_new.add_argument("--workstream", required=True, choices=WORKSTREAMS)
    p_new.add_argument("--depends", default="")
    p_set = sub.add_parser("set")
    p_set.add_argument("id")
    p_set.add_argument("pairs", nargs="*", metavar="key=value")
    p_set.add_argument("--note")
    sub.add_parser("check")
    args = parser.parse_args()

    tasks = load()
    by_id = {t["id"]: t for t in tasks}
    if args.command in (None, "board"):
        cmd_board(tasks, getattr(args, "all", False))
    elif args.command == "next":
        for t in tasks:
            if ready(t, by_id) and (not args.owner or t["owner"] in (args.owner, "unassigned")):
                print(row(t))
    elif args.command == "list":
        for t in tasks:
            if all(
                getattr(args, f) in (None, t[f])
                for f in ("status", "milestone", "owner", "workstream")
            ):
                print(f"  {t['status']:<12}" + row(t).lstrip())
    elif args.command == "show":
        print(find(tasks, args.id)["path"].read_text())
    elif args.command == "new":
        cmd_new(tasks, args.title, args.milestone, args.workstream, args.depends)
    elif args.command == "set":
        cmd_set(tasks, args.id, args.pairs, args.note)
    elif args.command == "check":
        sys.exit(cmd_check(tasks))


if __name__ == "__main__":
    main()
