"""YEScale OpenAI-compatible Chat Completions adapter."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import time
from typing import Mapping

import httpx

from .provider import ProviderResponse, ProviderUsage


YESCALE_BASE_URL = "https://api.yescale.io/v1"


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, request_id: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id


def _nonnegative_int(value) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def _cost(payload: dict, response: httpx.Response) -> Decimal | None:
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    candidates = (
        usage.get("cost"), usage.get("total_cost"), usage.get("cost_usd"),
        payload.get("cost"), payload.get("cost_usd"),
        response.headers.get("x-yescale-cost-usd"), response.headers.get("x-cost-usd"),
    )
    for value in candidates:
        if value is None:
            continue
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError):
            continue
        if parsed >= 0:
            return parsed
    return None


class YEScaleProvider:
    """Minimal server-only YEScale client with no secret-bearing logging."""

    provider_name = "YESCALE"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = YESCALE_BASE_URL,
        timeout_seconds: float = 45.0,
        client: httpx.Client | None = None,
        clock=time.perf_counter,
    ) -> None:
        if not api_key.strip():
            raise ValueError("YEScale API key is required")
        base_url = base_url.rstrip("/")
        if not base_url.startswith("https://") and client is None:
            raise ValueError("YEScale base URL must use HTTPS")
        self._api_key = api_key
        self._base_url = base_url
        self._clock = clock
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10.0)),
            trust_env=False,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

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
        if not model.strip():
            raise ValueError("YEScale model is required")
        if not 0 <= temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if not 1 <= max_tokens <= 8192:
            raise ValueError("max_tokens must be between 1 and 8192")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if metadata:
            safe_metadata = {str(key): str(value) for key, value in metadata.items() if value is not None}
            if len(safe_metadata) > 5:
                raise ValueError("YEScale metadata supports at most five fields")
            if any(not key or len(key) > 64 or len(value) > 256 for key, value in safe_metadata.items()):
                raise ValueError("YEScale metadata keys or values exceed the application bound")
            headers["X-YEScale-Metadata"] = json.dumps(
                safe_metadata, ensure_ascii=True, sort_keys=True, separators=(",", ":")
            )

        request_settings = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        started = self._clock()
        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    **request_settings,
                },
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderError("YEScale request failed before a valid response") from exc
        latency_ms = max(0, int((self._clock() - started) * 1000))
        request_id = response.headers.get("x-request-id") or response.headers.get("x-yescale-request-id")
        if response.status_code >= 400:
            raise ProviderError(
                f"YEScale request returned HTTP {response.status_code}",
                status_code=response.status_code,
                request_id=request_id,
            )
        try:
            payload = response.json()
            choices = payload["choices"]
            first = choices[0]
            content = first["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("YEScale response did not match the chat completion contract", request_id=request_id) from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("YEScale returned an empty completion", request_id=request_id)

        raw_usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        prompt_tokens = _nonnegative_int(raw_usage.get("prompt_tokens"))
        completion_tokens = _nonnegative_int(raw_usage.get("completion_tokens"))
        total_tokens = _nonnegative_int(raw_usage.get("total_tokens")) or prompt_tokens + completion_tokens
        return ProviderResponse(
            provider=self.provider_name,
            request_id=request_id,
            requested_model=model,
            response_model=str(payload.get("model") or model),
            content=content,
            usage=ProviderUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=_cost(payload, response),
                raw=raw_usage,
            ),
            latency_ms=latency_ms,
            finish_reason=str(first.get("finish_reason")) if first.get("finish_reason") is not None else None,
            settings=request_settings,
        )

