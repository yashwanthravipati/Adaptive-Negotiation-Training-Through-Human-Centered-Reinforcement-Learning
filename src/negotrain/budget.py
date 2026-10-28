"""Durable, process-safe API reservations. Uncertain failures retain their full reserve."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from uuid import uuid4


class BudgetExceeded(RuntimeError):
    pass


class SpendLedger:
    def __init__(self, path: str | Path, limit: float = 150.0):
        if not 0 < limit <= 150:
            raise ValueError("the task's total API limit must be in (0, $150]")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY, cap INTEGER)")
            db.execute("INSERT OR IGNORE INTO budget VALUES (1, ?)", (self._micro(limit),))
            # A caller may lower the cap, never silently reset or raise a persisted one.
            db.execute("UPDATE budget SET cap = MIN(cap, ?) WHERE id=1", (self._micro(limit),))
            db.execute("""CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, model TEXT, reserved INTEGER, actual INTEGER,
                state TEXT, usage TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP)""")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=60)

    @staticmethod
    def _micro(dollars: float) -> int:
        if not math.isfinite(dollars) or dollars < 0:
            raise ValueError("cost must be finite and nonnegative")
        return math.ceil(dollars * 1_000_000)

    def reserve(self, model: str, dollars: float) -> str:
        reserve = self._micro(dollars)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cap = db.execute("SELECT cap FROM budget WHERE id=1").fetchone()[0]
            charged = db.execute(
                "SELECT COALESCE(SUM(COALESCE(actual, reserved)),0) FROM requests"
            ).fetchone()[0]
            if charged + reserve > cap:
                raise BudgetExceeded(
                    f"API budget: ${charged / 1e6:.4f} accounted; "
                    f"${reserve / 1e6:.4f} required; cap ${cap / 1e6:.2f}"
                )
            identifier = uuid4().hex
            db.execute(
                "INSERT INTO requests (id,model,reserved,state) VALUES (?,?,?,?)",
                (identifier, model, reserve, "reserved"),
            )
        return identifier

    def settle(self, identifier: str, dollars: float, usage: dict) -> None:
        actual = self._micro(dollars)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT reserved,actual FROM requests WHERE id=?", (identifier,)
            ).fetchone()
            if row is None or row[1] is not None:
                raise ValueError("unknown or already settled reservation")
            db.execute(
                "UPDATE requests SET actual=?,state='completed',usage=? WHERE id=?",
                (actual, json.dumps(usage, sort_keys=True), identifier),
            )
        if actual > row[0]:
            raise RuntimeError("provider usage exceeded its context/output cost bound")

    def uncertain(self, identifier: str, error: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE requests SET state=?,usage=? WHERE id=? AND actual IS NULL",
                ("uncertain", json.dumps({"error_type": error}), identifier),
            )

    def snapshot(self) -> dict:
        with self._connect() as db:
            cap = db.execute("SELECT cap FROM budget WHERE id=1").fetchone()[0]
            count, actual, accounted, unresolved = db.execute("""SELECT COUNT(*),
                COALESCE(SUM(actual),0), COALESCE(SUM(COALESCE(actual,reserved)),0),
                COALESCE(SUM(actual IS NULL),0) FROM requests""").fetchone()
        return {
            "limit_usd": cap / 1e6,
            "requests": count,
            "actual_usd": actual / 1e6,
            "accounted_usd": accounted / 1e6,
            "unresolved_requests": unresolved,
            "remaining_usd": (cap - accounted) / 1e6,
        }
