"""Provider-neutral structured generation contract used by analysis intelligence."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Protocol


@dataclass(frozen=True)
class ProviderUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Decimal | None
    raw: dict


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    request_id: str | None
    requested_model: str
    response_model: str
    content: str
    usage: ProviderUsage
    latency_ms: int
    finish_reason: str | None
    settings: dict


class LLMProvider(Protocol):
    def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        metadata: Mapping[str, str] | None = None,
    ) -> ProviderResponse:
        """Return one non-streaming JSON-object completion."""

