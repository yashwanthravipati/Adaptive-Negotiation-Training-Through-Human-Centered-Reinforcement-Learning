# 0001: Stack and LLM provider

- **Status:** proposed (confirm in T-003)
- **Date:** 2026-10-24
- **Deciders:** Yash, Mahdi, Vincent

## Context
We need a stack three people can set up in minutes, one that supports an interactive UI
for study participants, structured LLM outputs, and offline tests.

## Decision
- Python 3.10+, packaged under `src/negotrain`, with pip and venv (uv works too).
- pydantic v2 models in `schemas.py` as the contract between modules.
- Claude through the Anthropic SDK, defaulting to `claude-opus-5-5` (`NEGOTRAIN_MODEL`
  overrides it). Every call goes through `negotrain.llm`, which uses structured outputs
  (`llm.parse`), prompt caching, server-side refusal fallback, and token accounting.
- Streamlit for the participant UI.
- JSON files for session storage (`data/sessions/`), until we need more than that.

## Consequences
- Switching provider or model touches `llm.py` and config only.
- The API no longer accepts temperature or top_p, so rollout diversity has to come from
  natural sampling and profile randomization, not temperature.
- Open: whether simulated users and counterfactual rollouts use a cheaper model, to be
  decided with the budget in T-003.
