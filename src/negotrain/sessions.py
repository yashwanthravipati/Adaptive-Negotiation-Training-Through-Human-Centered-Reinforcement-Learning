"""Persistence: one JSON file per session under data/sessions/ (gitignored), per-session
artifacts such as feedback in subfolders, and onboarding records under data/participants/."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from negotrain import config
from negotrain.schemas import Participant, Session

T = TypeVar("T", bound=BaseModel)


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

    def for_participant(self, participant_id: str) -> list[Session]:
        sessions = [s for s in self.all() if s.participant_id == participant_id]
        return sorted(sessions, key=lambda s: s.created_at)

    # Artifacts live in subfolders so that all() keeps globbing only sessions.
    def save_artifact(self, session_id: str, kind: str, data: BaseModel) -> Path:
        folder = self.root / kind
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{session_id}.json"
        path.write_text(data.model_dump_json(indent=2))
        return path

    def load_artifact(self, session_id: str, kind: str, model: type[T]) -> T | None:
        path = self.root / kind / f"{session_id}.json"
        return model.model_validate_json(path.read_text()) if path.exists() else None


class ParticipantStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else config.participants_dir()

    def save(self, participant: Participant) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{participant.id}.json"
        path.write_text(participant.model_dump_json(indent=2))
        return path

    def load(self, participant_id: str) -> Participant | None:
        path = self.root / f"{participant_id}.json"
        return Participant.model_validate_json(path.read_text()) if path.exists() else None
