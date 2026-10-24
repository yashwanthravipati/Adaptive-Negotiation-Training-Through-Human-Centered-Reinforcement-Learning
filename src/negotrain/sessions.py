"""Session persistence: one JSON file per session under data/sessions/ (gitignored)."""

from __future__ import annotations

from pathlib import Path

from negotrain import config
from negotrain.schemas import Session


class SessionStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else config.sessions_dir()

    def save(self, session: Session) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{session.id}.json"
        path.write_text(session.model_dump_json(indent=2))
        return path

    def load(self, session_id: str) -> Session:
        return Session.model_validate_json((self.root / f"{session_id}.json").read_text())

    def all(self) -> list[Session]:
        return [
            Session.model_validate_json(p.read_text()) for p in sorted(self.root.glob("*.json"))
        ]
