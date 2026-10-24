"""Negotiation cases: loading, parsing raw case text (parser.py), and scoring (scoring.py)."""

from __future__ import annotations

from pathlib import Path

from negotrain.schemas import Case


def load_case(path: str | Path) -> Case:
    return Case.model_validate_json(Path(path).read_text())


__all__ = ["load_case"]
