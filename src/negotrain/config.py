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


def sessions_dir() -> Path:
    return Path(os.getenv("NEGOTRAIN_SESSIONS_DIR", REPO_ROOT / "data" / "sessions"))
