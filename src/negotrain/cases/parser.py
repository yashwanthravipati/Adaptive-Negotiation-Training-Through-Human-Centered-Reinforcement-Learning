"""LLM parsing of raw case documents into a structured ``Case``.

Port of the HW0 prototype parser. See plan/tasks/T-004-port-hw0-parser.md.

Intended shape: ``parse_case(public_text, role_texts, llm) -> Case`` using
``llm.parse(..., output_type=Case)``, followed by human review of the JSON before the case
is used in a study (parsed point tables are easy to get subtly wrong).
"""

from __future__ import annotations

from negotrain.llm import LLM
from negotrain.schemas import Case


def parse_case(public_text: str, role_texts: dict[str, str], llm: LLM) -> Case:
    raise NotImplementedError("T-004: port the HW0 parser here")
