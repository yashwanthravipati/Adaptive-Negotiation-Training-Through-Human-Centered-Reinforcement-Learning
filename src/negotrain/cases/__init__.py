"""Negotiation cases: loading, parsing raw case text (parser.py), scoring (scoring.py), and
offer search (offers.py)."""

from __future__ import annotations

from pathlib import Path

from negotrain import config
from negotrain.schemas import Case


def load_case(path: str | Path) -> Case:
    return Case.model_validate_json(Path(path).read_text())


def case_library(dirs: list[Path] | None = None) -> dict[str, tuple[Case, Path]]:
    """All loadable cases by id. Private cases override committed ones with the same id."""
    library: dict[str, tuple[Case, Path]] = {}
    for folder in dirs or config.cases_dirs():
        for path in sorted(Path(folder).glob("*.json")):
            try:
                case = load_case(path)
            except ValueError:
                continue  # half-edited or non-case JSON; the library page reports it
            library[case.id] = (case, path)
    return library


def save_private_case(case: Case, dirs: list[Path] | None = None) -> Path:
    folder = (dirs or config.cases_dirs())[-1]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{case.id}.json"
    path.write_text(case.model_dump_json(indent=2))
    return path


__all__ = ["case_library", "load_case", "save_private_case"]
