from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import math
import os
import time
from typing import Protocol
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class ReportConfig:
    enabled: bool = False
    endpoint: str = ""
    api_key: str = ""
    model: str = ""
    model_version: str = ""
    expected_returned_model: str = ""
    thinking: str = ""  # Empty preserves the provider default.
    budget_usd: Decimal = Decimal("0")
    call_ceiling_usd: Decimal = Decimal("0")
    # Required conservative contractual upper bound; not an observed cost.
    input_usd_per_million: Decimal = Decimal("0")
    output_usd_per_million: Decimal = Decimal("0")
    max_input_bytes: int = 24000
    max_output_tokens: int = 2400
    max_response_bytes: int = 48000
    deadline_seconds: float = 45

    @classmethod
    def from_env(cls):
        try:
            return cls(
                enabled=os.getenv("TEXT_REPORT_ENABLED", "false").lower() == "true",
                endpoint=os.getenv("YESCALE_CHAT_ENDPOINT", ""), api_key=os.getenv("YESCALE_API_KEY", ""),
                model=os.getenv("YESCALE_MODEL", ""), model_version=os.getenv("YESCALE_MODEL_VERSION", ""),
                expected_returned_model=os.getenv("YESCALE_EXPECTED_RETURNED_MODEL", ""),
                thinking=os.getenv("YESCALE_THINKING", ""),
                budget_usd=Decimal(os.getenv("TEXT_REPORT_BUDGET_USD", "0")),
                call_ceiling_usd=Decimal(os.getenv("TEXT_REPORT_CALL_CEILING_USD", "0")),
                input_usd_per_million=Decimal(os.getenv("YESCALE_INPUT_USD_PER_MILLION", "0")),
                output_usd_per_million=Decimal(os.getenv("YESCALE_OUTPUT_USD_PER_MILLION", "0")),
                max_input_bytes=int(os.getenv("TEXT_REPORT_MAX_INPUT_BYTES", "24000")),
                max_output_tokens=int(os.getenv("TEXT_REPORT_MAX_OUTPUT_TOKENS", "2400")),
                deadline_seconds=float(os.getenv("TEXT_REPORT_DEADLINE_SECONDS", "45")),
            )
        except (ValueError, InvalidOperation):
            return cls()  # Bad activation configuration never enables spend.

    def available(self):
        try:
            endpoint = urlsplit(self.endpoint)
        except ValueError:
            return False
        numbers = (self.budget_usd, self.call_ceiling_usd, self.input_usd_per_million, self.output_usd_per_million)
        return bool(self.enabled and self.api_key and self.model and self.model_version
                    and self.thinking in {"", "enabled", "disabled"}
                    and endpoint.scheme == "https" and endpoint.hostname and not endpoint.username
                    and not endpoint.password and not endpoint.query and not endpoint.fragment
                    and all(n.is_finite() and n > 0 for n in numbers)
                    and 1000 <= self.max_input_bytes <= 64000 and 100 <= self.max_output_tokens <= 8000
                    and 1000 <= self.max_response_bytes <= 128000
                    and math.isfinite(self.deadline_seconds) and 1 <= self.deadline_seconds <= 120)

    def reservation(self, input_bytes: int) -> Decimal:
        # UTF-8 bytes conservatively bound text tokens, plus protocol overhead.
        return ((Decimal(input_bytes + 1024) * self.input_usd_per_million
                 + Decimal(self.max_output_tokens) * self.output_usd_per_million) / Decimal(1000000))

    def returned_model_matches(self, model):
        return model == (self.expected_returned_model or self.model)


class ProviderError(RuntimeError):
    def __init__(self, code: str, *, uncertain=False, metadata=None):
        super().__init__(code)
        self.code, self.uncertain = code, uncertain
        self.metadata = metadata or {}


class LLMProvider(Protocol):
    def generate(self, messages: list[dict], config: ReportConfig, dispatch_id: str) -> dict: ...


class YEScaleProvider:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client

    def generate(self, messages, config, dispatch_id):
        started = time.monotonic()
        trace = {}
        def safe_id(value):
            value = str(value or "")[:160]
            return value if value and config.api_key not in value else None
        client = self.client or httpx.Client(timeout=config.deadline_seconds, follow_redirects=False)
        try:
            if config.thinking not in {"", "enabled", "disabled"}:
                raise ProviderError("INVALID_CONFIG")
            body_params = {"model": config.model, "messages": messages,
                           "max_tokens": config.max_output_tokens,
                           "response_format": {"type": "json_object"}}
            if config.thinking:
                body_params["thinking"] = {"type": config.thinking}
            # No retry transport; request ID is traceability, not a billing guarantee.
            with client.stream("POST", config.endpoint,
                               headers={"Authorization": f"Bearer {config.api_key}", "X-Request-ID": dispatch_id},
                               json=body_params,
                               timeout=config.deadline_seconds) as response:
                trace["request_id"] = safe_id(response.headers.get("x-request-id"))
                if response.status_code != 200:
                    raise ProviderError("PROVIDER_REJECTED", uncertain=True, metadata=trace)
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if time.monotonic() - started > config.deadline_seconds:
                        raise ProviderError("PROVIDER_TIMEOUT", uncertain=True, metadata=trace)
                    if len(body) > config.max_response_bytes:
                        raise ProviderError("OUTPUT_LIMIT", uncertain=True, metadata=trace)
                result = json.loads(body)
                if not isinstance(result, dict):
                    raise ProviderError("INVALID_RESPONSE", metadata=trace)
                trace = {"returned_model": safe_id(result.get("model")),
                         "latency_ms": round((time.monotonic() - started) * 1000),
                         "request_id": safe_id(response.headers.get("x-request-id") or result.get("id"))}
                returned_usage = result.get("usage")
                if isinstance(returned_usage, dict):
                    trace["usage"] = {key: value for key, value in returned_usage.items()
                                      if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
                                      and type(value) is int and value >= 0}
                if not config.returned_model_matches(result.get("model")):
                    raise ProviderError("UNEXPECTED_MODEL", metadata=trace)
                choices = result.get("choices")
                if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                    raise ProviderError("INVALID_RESPONSE", metadata=trace)
                choice = choices[0]
                message = choice.get("message")
                if (not isinstance(message, dict) or not isinstance(message.get("content"), str)
                        or not isinstance(choice.get("finish_reason"), str)):
                    raise ProviderError("INVALID_RESPONSE", metadata=trace)
                if choice.get("finish_reason") != "stop":
                    raise ProviderError("OUTPUT_INCOMPLETE", metadata=trace)
                usage = result.get("usage")
                if usage is not None:
                    if not isinstance(usage, dict):
                        raise ProviderError("INVALID_USAGE", metadata=trace)
                    usage = {key: usage[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens") if key in usage}
                    if any(type(value) is not int or value < 0 for value in usage.values()):
                        raise ProviderError("INVALID_USAGE", metadata=trace)
                    if usage.get("completion_tokens", 0) > config.max_output_tokens:
                        raise ProviderError("OUTPUT_LIMIT", metadata=trace)
                if not isinstance(choice["message"]["content"], str):
                    raise ProviderError("INVALID_RESPONSE", metadata=trace)
                request_id = response.headers.get("x-request-id") or result.get("id")
                return {"content": choice["message"]["content"], "returned_model": result["model"],
                        "usage": usage, "latency_ms": round((time.monotonic() - started) * 1000),
                        "request_id": safe_id(request_id),
                        "actual_cost_usd": None, "cost_provenance": "unknown"}
        except ProviderError:
            raise
        except httpx.TimeoutException:
            raise ProviderError("PROVIDER_TIMEOUT", uncertain=True, metadata=trace) from None
        except httpx.HTTPError:
            raise ProviderError("PROVIDER_TRANSPORT", uncertain=True, metadata=trace) from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("INVALID_RESPONSE", metadata=trace) from None
        finally:
            if self.client is None:
                client.close()
