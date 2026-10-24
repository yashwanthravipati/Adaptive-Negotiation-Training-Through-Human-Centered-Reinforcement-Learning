from pathlib import Path

import pytest

from negotrain.cases import load_case
from negotrain.schemas import Case

CASES_DIR = Path(__file__).resolve().parents[1] / "data" / "cases"


@pytest.fixture
def case() -> Case:
    return load_case(CASES_DIR / "cloudline_hiring.json")
