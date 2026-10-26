"""Runtime configuration from environment variables (loaded from .env if present)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]


def model() -> str:
    return os.getenv("NEGOTRAIN_MODEL", "claude-opus-5-5")


def effort() -> str:
    """low | medium | high | xhigh | max. Thinking depth and token spend per call."""
    return os.getenv("NEGOTRAIN_EFFORT", "medium")


def chat_effort() -> str:
    """Effort for counterpart turns in the app: low keeps a live conversation responsive."""
    return os.getenv("NEGOTRAIN_CHAT_EFFORT", "low")


def offline() -> bool:
    """Run without the API: rule-based counterpart and template feedback."""
    return os.getenv("NEGOTRAIN_OFFLINE", "").lower() in ("1", "true", "yes")


def has_api_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def participant_id() -> str:
    """The app runs locally for one person; their sessions are stored under this id."""
    return os.getenv("NEGOTRAIN_PARTICIPANT", "local")


def sessions_dir() -> Path:
    return Path(os.getenv("NEGOTRAIN_SESSIONS_DIR", REPO_ROOT / "data" / "sessions"))


def participants_dir() -> Path:
    return Path(os.getenv("NEGOTRAIN_PARTICIPANTS_DIR", REPO_ROOT / "data" / "participants"))


def cases_dirs() -> list[Path]:
    """Committed synthetic cases, then private (gitignored) ones, which is where imports go."""
    root = Path(os.getenv("NEGOTRAIN_CASES_DIR", REPO_ROOT / "data" / "cases"))
    return [root, root / "private"]
