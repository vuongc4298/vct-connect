"""YEScale OpenAI-compatible chat and embedding adapter."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import math
import time
from typing import Mapping, Sequence

import httpx

from .provider import EmbeddingResponse, ProviderResponse, ProviderUsage, VisualInput


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


def _request_id(response: httpx.Response) -> str | None:
    return response.headers.get("x-request-id") or response.headers.get("x-yescale-request-id")


def _metadata_headers(api_key: str, metadata: Mapping[str, str] | None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
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
    return headers


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

    def _post(self, path: str, *, body: dict, metadata: Mapping[str, str] | None) -> tuple[httpx.Response, int]:
        started = self._clock()
        try:
            response = self._client.post(
                f"{self._base_url}{path}",
                headers=_metadata_headers(self._api_key, metadata),
                json=body,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderError("YEScale request failed before a valid response") from exc
        latency_ms = max(0, int((self._clock() - started) * 1000))
        if response.status_code >= 400:
            raise ProviderError(
                f"YEScale request returned HTTP {response.status_code}",
                status_code=response.status_code,
                request_id=_request_id(response),
            )
        return response, latency_ms

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

        request_settings = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        response, latency_ms = self._post(
            "/chat/completions",
            metadata=metadata,
            body={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                **request_settings,
            },
        )
        request_id = _request_id(response)
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

    def generate_multimodal_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        images: Sequence[VisualInput],
        temperature: float,
        max_tokens: int,
        metadata: Mapping[str, str] | None = None,
    ) -> ProviderResponse:
        if not model.strip():
            raise ValueError("YEScale model is required")
        if not images or len(images) > 12:
            raise ValueError("multimodal requests require between 1 and 12 images")
        if not 0 <= temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if not 1 <= max_tokens <= 8192:
            raise ValueError("max_tokens must be between 1 and 8192")

        content: list[dict] = [{"type": "text", "text": user_prompt}]
        for image in images:
            if not image.media_id.strip() or len(image.media_id) > 160:
                raise ValueError("multimodal media_id is invalid")
            if not image.data_url.startswith(
                ("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,")
            ):
                raise ValueError("multimodal inputs must use bounded PNG/JPEG/WebP data URLs")
            if len(image.data_url) > 7_000_000:
                raise ValueError("multimodal image input exceeds the application bound")
            content.append({"type": "text", "text": f"MEDIA_ID: {image.media_id}"})
            content.append({
                "type": "image_url",
                "image_url": {"url": image.data_url, "detail": image.detail},
            })

        request_settings = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        response, latency_ms = self._post(
            "/chat/completions",
            metadata=metadata,
            body={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content},
                ],
                **request_settings,
            },
        )
        request_id = _request_id(response)
        try:
            payload = response.json()
            choices = payload["choices"]
            first = choices[0]
            output = first["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                "YEScale response did not match the multimodal chat contract",
                request_id=request_id,
            ) from exc
        if not isinstance(output, str) or not output.strip():
            raise ProviderError("YEScale returned an empty multimodal completion", request_id=request_id)

        raw_usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        prompt_tokens = _nonnegative_int(raw_usage.get("prompt_tokens"))
        completion_tokens = _nonnegative_int(raw_usage.get("completion_tokens"))
        total_tokens = _nonnegative_int(raw_usage.get("total_tokens")) or prompt_tokens + completion_tokens
        return ProviderResponse(
            provider=self.provider_name,
            request_id=request_id,
            requested_model=model,
            response_model=str(payload.get("model") or model),
            content=output,
            usage=ProviderUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=_cost(payload, response),
                raw=raw_usage,
            ),
            latency_ms=latency_ms,
            finish_reason=str(first.get("finish_reason")) if first.get("finish_reason") is not None else None,
            settings={**request_settings, "image_count": len(images)},
        )

    def embed_texts(
        self,
        *,
        model: str,
        texts: Sequence[str],
        metadata: Mapping[str, str] | None = None,
    ) -> EmbeddingResponse:
        if not model.strip():
            raise ValueError("YEScale embedding model is required")
        if not texts or len(texts) > 64:
            raise ValueError("embedding requests require between 1 and 64 texts")
        normalized = [text.strip() for text in texts]
        if any(not text or len(text) > 4000 for text in normalized):
            raise ValueError("embedding inputs must contain 1-4000 characters each")
        if sum(len(text.encode("utf-8")) for text in normalized) > 65_536:
            raise ValueError("embedding request exceeds the application input budget")

        settings = {"encoding_format": "float"}
        response, latency_ms = self._post(
            "/embeddings",
            metadata=metadata,
            body={"model": model, "input": normalized, **settings},
        )
        request_id = _request_id(response)
        try:
            payload = response.json()
            rows = sorted(payload["data"], key=lambda row: int(row["index"]))
            vectors = tuple(tuple(float(value) for value in row["embedding"]) for row in rows)
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("YEScale response did not match the embeddings contract", request_id=request_id) from exc
        if len(vectors) != len(normalized) or not vectors or any(not vector for vector in vectors):
            raise ProviderError("YEScale returned an incomplete embeddings response", request_id=request_id)
        dimension = len(vectors[0])
        if any(len(vector) != dimension for vector in vectors):
            raise ProviderError("YEScale returned inconsistent embedding dimensions", request_id=request_id)
        if any(not math.isfinite(value) for vector in vectors for value in vector):
            raise ProviderError("YEScale returned a non-finite embedding value", request_id=request_id)

        raw_usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        prompt_tokens = _nonnegative_int(raw_usage.get("prompt_tokens"))
        total_tokens = _nonnegative_int(raw_usage.get("total_tokens")) or prompt_tokens
        return EmbeddingResponse(
            provider=self.provider_name,
            request_id=request_id,
            requested_model=model,
            response_model=str(payload.get("model") or model),
            vectors=vectors,
            usage=ProviderUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                total_tokens=total_tokens,
                cost_usd=_cost(payload, response),
                raw=raw_usage,
            ),
            latency_ms=latency_ms,
            settings=settings,
        )
