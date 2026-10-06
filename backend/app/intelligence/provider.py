"""Provider-neutral model contracts used by analysis intelligence."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Protocol, Sequence


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


@dataclass(frozen=True)
class EmbeddingResponse:
    provider: str
    request_id: str | None
    requested_model: str
    response_model: str
    vectors: tuple[tuple[float, ...], ...]
    usage: ProviderUsage
    latency_ms: int
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


class EmbeddingProvider(Protocol):
    def embed_texts(
        self,
        *,
        model: str,
        texts: Sequence[str],
        metadata: Mapping[str, str] | None = None,
    ) -> EmbeddingResponse:
        """Return one vector per input text in original input order."""
