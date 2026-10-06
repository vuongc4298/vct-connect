from decimal import Decimal
import json

import httpx
import pytest
from pydantic import ValidationError

from backend.app.extraction.contracts import EVIDENCE_FIELDS
from backend.app.intelligence.contracts import SCHEMA_VERSION, EvidenceSignal, SupplierInterpretation
from backend.app.intelligence.interpretation import interpret_supplier_data
from backend.app.intelligence.provider import ProviderResponse, ProviderUsage
from backend.app.intelligence.yescale import ProviderError, YEScaleProvider


def supplier_data():
    evidence = dict.fromkeys(EVIDENCE_FIELDS)
    evidence.update(
        supplier_name="Guangzhou Example Co.",
        years_active=6,
        categories=["garment"],
        rating=4.7,
        reviews=[{"text": "Giao hàng nhanh"}],
    )
    missing = [name for name in EVIDENCE_FIELDS if evidence[name] in (None, "", [])]
    return {
        "contract_version": "supplierdata.v1",
        "platform": "1688",
        "source_url": "https://detail.1688.com/offer/996518024136.html",
        "offer_id": "996518024136",
        "platform_supplier_id": "supplier-42",
        "extracted_at": "2026-10-06T12:00:00+00:00",
        "extraction_method": "PUBLIC_HTTP",
        "analysis_mode": "ACCOUNT_PUBLIC",
        "extractor_version": "1688-public.v1",
        "completeness": round((len(EVIDENCE_FIELDS) - len(missing)) / len(EVIDENCE_FIELDS), 4),
        "completeness_denominator": list(EVIDENCE_FIELDS),
        "missing_fields": missing,
        **evidence,
    }


def valid_output():
    return {
        "schema_version": SCHEMA_VERSION,
        "language": "vi",
        "summary_vi": "Bằng chứng hiện có cho thấy nhà cung cấp có lịch sử hoạt động, nhưng dữ liệu vẫn chưa đủ để kết luận toàn diện.",
        "positive_signals": [{
            "statement_vi": "Nguồn hiển thị 6 năm hoạt động.",
            "evidence_fields": ["years_active"],
            "confidence": 0.9,
        }],
        "risk_signals": [],
        "uncertainties": [{
            "statement_vi": "Chưa có thông tin chứng nhận trong ảnh chụp hiện tại.",
            "evidence_fields": ["certifications"],
            "confidence": 0.95,
        }],
        "recommended_verifications": ["Yêu cầu và đối chiếu giấy phép kinh doanh trước khi đặt cọc."],
        "confidence": 0.74,
    }


class FakeProvider:
    def __init__(self, output=None):
        self.output = output or valid_output()
        self.calls = []

    def generate_json(self, **kwargs):
        self.calls.append(kwargs)
        return ProviderResponse(
            provider="FAKE",
            request_id="req_fixture",
            requested_model=kwargs["model"],
            response_model="fixture-model-2026-10-01",
            content=json.dumps(self.output, ensure_ascii=False),
            usage=ProviderUsage(310, 145, 455, Decimal("0.001234"), {"fixture": True}),
            latency_ms=120,
            finish_reason="stop",
            settings={"temperature": kwargs["temperature"], "max_tokens": kwargs["max_tokens"]},
        )


def test_interpretation_is_versioned_grounded_and_has_no_risk_score_contract():
    provider = FakeProvider()
    run = interpret_supplier_data(supplier_data(), provider=provider, model="candidate-model")
    assert run.interpretation.schema_version == SCHEMA_VERSION
    assert run.interpretation.language == "vi"
    assert run.interpretation.confidence == 0.74
    assert run.interpretation.model_dump().keys().isdisjoint({"risk_score", "risk_label", "factory_trader"})
    assert run.provider_response.usage.cost_usd == Decimal("0.001234")
    assert len(run.input_sha256) == 64
    assert provider.calls[0]["metadata"] is None
    assert "Do not output an overall supplier risk score" in provider.calls[0]["system_prompt"]


def test_input_hash_is_deterministic_for_mapping_order():
    first = supplier_data()
    second = dict(reversed(list(first.items())))
    a = interpret_supplier_data(first, provider=FakeProvider(), model="candidate-model")
    b = interpret_supplier_data(second, provider=FakeProvider(), model="candidate-model")
    assert a.input_sha256 == b.input_sha256


def test_json_fence_is_tolerated_but_schema_is_still_enforced():
    provider = FakeProvider()
    raw = json.dumps(valid_output(), ensure_ascii=False)
    provider.generate_json = lambda **kwargs: ProviderResponse(
        provider="FAKE", request_id=None, requested_model=kwargs["model"], response_model=kwargs["model"],
        content=f"```json\n{raw}\n```", usage=ProviderUsage(1, 1, 2, None, {}),
        latency_ms=1, finish_reason="stop", settings={},
    )
    run = interpret_supplier_data(supplier_data(), provider=provider, model="candidate-model")
    assert run.interpretation.summary_vi.startswith("Bằng chứng")


def test_unknown_evidence_reference_is_rejected():
    with pytest.raises(ValidationError, match="unsupported SupplierData fields"):
        EvidenceSignal(statement_vi="Không hợp lệ", evidence_fields=["imaginary_field"], confidence=0.5)


def test_extra_model_fields_are_rejected():
    output = valid_output() | {"risk_score": 12}
    with pytest.raises(ValueError, match="failed the supplier interpretation schema"):
        interpret_supplier_data(supplier_data(), provider=FakeProvider(output), model="candidate-model")


def test_yescale_adapter_uses_server_key_metadata_json_mode_and_provenance():
    captured = {}

    def handler(request: httpx.Request):
        captured["request"] = request
        body = json.loads(request.content)
        captured["body"] = body
        return httpx.Response(
            200,
            headers={"X-YEScale-Request-Id": "ys_req_123"},
            json={
                "model": "gpt-4o-mini-2026-06-01",
                "choices": [{"message": {"content": json.dumps(valid_output())}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "cost": "0.0025"},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = YEScaleProvider("secret-test-key", client=client, clock=lambda: 10.0)
        result = provider.generate_json(
            model="gpt-4o-mini", system_prompt="system", user_prompt="user",
            temperature=0.1, max_tokens=800,
            metadata={"feature": "supplier_interpretation", "session_id": "analysis-1"},
        )
    request = captured["request"]
    assert str(request.url) == "https://api.yescale.io/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer secret-test-key"
    assert json.loads(request.headers["x-yescale-metadata"])["feature"] == "supplier_interpretation"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["stream"] is False
    assert result.request_id == "ys_req_123"
    assert result.response_model == "gpt-4o-mini-2026-06-01"
    assert result.usage.total_tokens == 150
    assert result.usage.cost_usd == Decimal("0.0025")


def test_yescale_adapter_records_unavailable_cost_without_inventing_one():
    def handler(_request):
        return httpx.Response(200, json={
            "model": "candidate",
            "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        })
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = YEScaleProvider("secret", client=client, clock=lambda: 1.0).generate_json(
            model="candidate", system_prompt="s", user_prompt="u", temperature=0, max_tokens=10,
        )
    assert result.usage.cost_usd is None


def test_yescale_error_does_not_echo_provider_body_or_api_key():
    def handler(_request):
        return httpx.Response(429, headers={"x-request-id": "req_rate"}, text="sensitive upstream details")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = YEScaleProvider("super-secret", client=client, clock=lambda: 1.0)
        with pytest.raises(ProviderError) as caught:
            provider.generate_json(model="candidate", system_prompt="s", user_prompt="u", temperature=0, max_tokens=10)
    assert caught.value.status_code == 429
    assert caught.value.request_id == "req_rate"
    assert "sensitive upstream details" not in str(caught.value)
    assert "super-secret" not in str(caught.value)


def test_yescale_metadata_is_bounded_before_network_io():
    called = False
    def handler(_request):
        nonlocal called
        called = True
        return httpx.Response(500)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = YEScaleProvider("secret", client=client)
        with pytest.raises(ValueError, match="at most five fields"):
            provider.generate_json(
                model="candidate", system_prompt="s", user_prompt="u", temperature=0, max_tokens=10,
                metadata={str(i): str(i) for i in range(6)},
            )
    assert called is False


def test_supplier_input_budget_is_enforced_before_provider_call():
    data = supplier_data()
    data["company_information"] = {"oversized": "x" * 70_000}
    provider = FakeProvider()
    with pytest.raises(ValueError, match="input budget"):
        interpret_supplier_data(data, provider=provider, model="candidate-model")
    assert provider.calls == []

