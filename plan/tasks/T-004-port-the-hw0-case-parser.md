---
id: T-004
title: Port the HW0 case parser
status: todo
milestone: M0
workstream: cases
owner: unassigned
depends_on: []
---

## Goal
parse_case(public_text, role_texts, llm) -> Case in src/negotrain/cases/parser.py, so new cases can be loaded without hand-writing JSON.

## Context
Use llm.parse(). Structured outputs work best with simple schemas: the Case model's dict-of-dict point tables may need an intermediate list-based schema that is converted to Case afterwards.

## Acceptance criteria
- [ ] Parser implemented using llm.parse with a structured output schema
- [ ] Recovers data/cases/cloudline_hiring.json from a plain-text rendering of it
- [ ] Offline unit test with ScriptedLLM; one @pytest.mark.live test

## Log
