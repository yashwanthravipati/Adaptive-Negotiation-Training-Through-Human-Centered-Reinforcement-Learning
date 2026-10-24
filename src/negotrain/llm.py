"""The single gateway to the LLM API.

Every model call in the project goes through an ``LLM`` so that we can swap models in one
place, keep token accounting for cost estimates, and run the whole stack offline with
``ScriptedLLM`` in tests. Do not construct ``anthropic.Anthropic`` anywhere else.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

import anthropic
from pydantic import BaseModel

from negotrain import config

T = TypeVar("T", bound=BaseModel)
Message = dict[str, Any]  # {"role": "user" | "assistant", "content": str}

# Server-side fallback: if a safety classifier declines, the API retries on the model
# Anthropic recommends for that refusal category instead of returning the refusal.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMRefusal(RuntimeError):
    pass


class LLM(Protocol):
    def complete(
        self, system: str, messages: Sequence[Message], *, max_tokens: int = 16000
    ) -> str: ...

    def parse(
        self,
        system: str,
        messages: Sequence[Message],
        output_type: type[T],
        *,
        max_tokens: int = 16000,
    ) -> T: ...


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0

    def add(self, usage: Any) -> None:
        self.calls += 1
        self.input_tokens += usage.input_tokens or 0
        self.output_tokens += usage.output_tokens or 0
        self.cache_read_input_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0


class ClaudeLLM:
    """Claude via the Anthropic SDK. Credentials come from ANTHROPIC_API_KEY (see .env)."""

    def __init__(
        self,
        model: str | None = None,
        effort: str | None = None,
        client: anthropic.Anthropic | None = None,
    ):
        self.model = model or config.model()
        self.effort = effort or config.effort()
        self.client = client or anthropic.Anthropic()
        self.usage = Usage()

    def _request(self, system: str, messages: Sequence[Message], max_tokens: int) -> dict:
        return {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": list(messages),
            "output_config": {"effort": self.effort},
            # The system prompt (case + role sheet) is identical across turns of a session.
            "cache_control": {"type": "ephemeral"},
            "betas": [_FALLBACK_BETA],
            "fallbacks": "default",
        }

    def _check(self, response: Any) -> None:
        self.usage.add(response.usage)
        if response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            raise LLMRefusal(f"model declined (category={category})")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("response hit max_tokens; raise the limit for this call")

    def complete(self, system: str, messages: Sequence[Message], *, max_tokens: int = 16000) -> str:
        response = self.client.beta.messages.create(**self._request(system, messages, max_tokens))
        self._check(response)
        return "".join(b.text for b in response.content if b.type == "text")

    def parse(
        self,
        system: str,
        messages: Sequence[Message],
        output_type: type[T],
        *,
        max_tokens: int = 16000,
    ) -> T:
        response = self.client.beta.messages.parse(
            **self._request(system, messages, max_tokens), output_format=output_type
        )
        self._check(response)
        if response.parsed_output is None:
            raise RuntimeError("model returned no parseable output")
        return response.parsed_output


Responder = Callable[[str, Sequence[Message]], Any]


@dataclass
class ScriptedLLM:
    """Offline stand-in for tests and UI work. Returns scripted responses in order.

    Each script entry is a string (for ``complete``), a pydantic model or dict (for
    ``parse``), or a callable ``(system, messages) -> response`` for dynamic behavior.
    Every call is recorded in ``calls`` so tests can assert on prompts.
    """

    script: list[Any]
    calls: list[tuple[str, list[Message]]] = field(default_factory=list)

    def _next(self, system: str, messages: Sequence[Message]) -> Any:
        self.calls.append((system, list(messages)))
        if not self.script:
            raise RuntimeError("ScriptedLLM ran out of scripted responses")
        item = self.script.pop(0)
        return item(system, messages) if callable(item) else item

    def complete(self, system: str, messages: Sequence[Message], *, max_tokens: int = 16000) -> str:
        return str(self._next(system, messages))

    def parse(
        self,
        system: str,
        messages: Sequence[Message],
        output_type: type[T],
        *,
        max_tokens: int = 16000,
    ) -> T:
        item = self._next(system, messages)
        return item if isinstance(item, output_type) else output_type.model_validate(item)
