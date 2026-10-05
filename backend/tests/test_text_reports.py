from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from backend.app.interpretation.contracts import validate_report
from backend.app.interpretation.provider import ReportConfig, YEScaleProvider, ProviderError
from backend.app.interpretation.service import process_report_once, prepare_evidence, bounded_generate
from backend.app.interpretation.service import minimize


def configured(**kwargs):
    return replace(ReportConfig(enabled=True, endpoint="https://provider.test/v1/chat/completions",
                   api_key="private-key", model="pinned-model", model_version="version-2026-10-05",
                   budget_usd=Decimal("1"), call_ceiling_usd=Decimal("0.1"),
                   input_usd_per_million=Decimal("1"), output_usd_per_million=Decimal("2")), **kwargs)


def content(citation="E1"):
    return json.dumps({"summary": "Nguồn có thông tin sản phẩm; cần xác minh trước đặt hàng.",
                       "findings": [{"kind": "observation", "text": "Trang hiển thị sản phẩm.", "citations": [citation]}],
                       "limitations": ["Chưa xác minh độc lập."], "actions": ["Yêu cầu mẫu trước đặt cọc."]}, ensure_ascii=False)


class FakeProvider:
    def __init__(self, output=None, error=None):
        self.calls = []
        self.output, self.error = output or content(), error

    def generate(self, messages, config, dispatch_id):
        self.calls.append((messages, dispatch_id))
        if self.error:
            raise self.error
        return {"content": self.output, "returned_model": config.model,
                "usage": {"prompt_tokens": 700, "completion_tokens": 100}, "latency_ms": 3, "request_id": "fake-request"}


class MemoryStore:
    def __init__(self):
        self.row = {"supplier_snapshot_id": uuid4(), "source_url": "https://detail.1688.com/offer/996518024136.html",
                    "extraction_method": "USER_UPLOAD", "result": {"extraction_status": "PARTIAL"},
                    "supplier_data": {"products": [{"title": "中国商品"}], "missing_fields": ["rating"],
                                      "extracted_at": "2026-10-05T00:00:00Z"}, "reviews": []}
        self.state, self.reservations = "QUEUED", []
        self.token, self.id = uuid4(), uuid4()

    def claim_text_report(self, lease):
        if self.state != "QUEUED": return None
        self.state = "PROCESSING"
        return {"analysis_id": self.id, "lease_token": self.token}

    def get(self, analysis_id): return self.row

    def dispatch_text_report(self, analysis_id, token, reserve, budget, ceiling, metadata):
        if reserve > min(budget, ceiling): return None
        self.reservations.append(dict(metadata))
        return uuid4()

    def settle_text_report(self, analysis_id, token, state, code, report, metadata):
        self.state, self.code, self.report, self.metadata = state, code, report, dict(metadata)


def test_saved_chinese_evidence_to_persisted_vietnamese_citations_and_redelivery():
    store, provider = MemoryStore(), FakeProvider()
    assert process_report_once(store, configured(), provider)
    assert store.state == "READY"
    assert store.report["findings"][0]["citations"] == ["E1"]
    assert store.report["evidence"][0]["value"][0]["title"] == "中国商品"
    assert any("rating" in limitation for limitation in store.report["limitations"])
    assert store.metadata["actual_cost_usd"] is None
    assert store.metadata["cost_provenance"] == "unknown"
    assert store.metadata["returned_model"] == "pinned-model"
    assert store.metadata["prompt_version"] and store.metadata["schema_version"] and store.metadata["pipeline_version"]
    assert not process_report_once(store, configured(), provider)
    assert len(provider.calls) == len(store.reservations) == 1


@pytest.mark.parametrize("case,expected", [("disabled", "UNAVAILABLE"), ("budget", "UNAVAILABLE"),
    ("no_snapshot", "INSUFFICIENT"), ("fixture", "INSUFFICIENT"), ("empty", "INSUFFICIENT"), ("input", "UNAVAILABLE")])
def test_no_spend_fallback(case, expected):
    store, provider, config = MemoryStore(), FakeProvider(), configured()
    if case == "disabled": config = replace(config, enabled=False)
    if case == "budget": config = replace(config, call_ceiling_usd=Decimal("0.000001"))
    if case == "no_snapshot": store.row["supplier_snapshot_id"] = None
    if case == "fixture": store.row["extraction_method"] = "FIXTURE"
    if case == "empty": store.row["supplier_data"] = {}
    if case == "input": config = replace(config, max_input_bytes=1000)
    original = json.dumps(store.row["result"])
    process_report_once(store, config, provider)
    assert store.state == expected and not provider.calls and not store.reservations
    assert json.dumps(store.row["result"]) == original


@pytest.mark.parametrize("output", ["bad json", content("E99"), content().replace('"observation"', '"computed_score"'),
                                     content().replace("Trang hiển thị sản phẩm.", "Độ tin cậy: 72%"),
                                     content()[:-1] + ', "risk_score": 72}'])
def test_invalid_interpretation_is_never_visible(output):
    store, provider = MemoryStore(), FakeProvider(output)
    process_report_once(store, configured(), provider)
    assert store.state == "FAILED" and store.code == "INVALID_OUTPUT" and store.report is None
    assert len(provider.calls) == 1
    assert not process_report_once(store, configured(), provider)


def test_timeout_is_uncertain_without_paid_retry_or_secret():
    store = MemoryStore()
    provider = FakeProvider(error=ProviderError("PROVIDER_TIMEOUT", uncertain=True))
    process_report_once(store, configured(), provider)
    assert store.state == "UNCERTAIN" and not process_report_once(store, configured(), provider)
    assert "private-key" not in json.dumps(store.metadata)


def test_minimize_contacts_reviewer_and_identifiers():
    row = MemoryStore().row
    row["supplier_data"]["supplier_name"] = "Private name"
    row["supplier_data"]["products"] = [{"title": "联系 a@example.com +861234567890", "offer_id": "123", "source_url": "https://secret.test"}]
    row["reviews"] = [{"text": "不错", "reviewer_name": "Private reviewer", "user_id": "secret"}]
    evidence = json.dumps(prepare_evidence(row), ensure_ascii=False)
    assert "不错" in evidence and "联系" in evidence
    for private in ("Private", "a@example.com", "861234567890", "secret", "offer_id"):
        assert private not in evidence


def test_business_attribute_names_and_shipping_text_survive_projection():
    row = MemoryStore().row
    row["supplier_data"]["products"] = [{"title": "商品", "attributes": [{"name": "材质", "value": "棉"}]}]
    row["supplier_data"]["delivery_information"] = {"shop_shipping_display_text": "48小时发货"}
    evidence = {entry["path"]: entry["value"] for entry in prepare_evidence(row)}
    assert evidence["products"][0]["attributes"] == [{"name": "材质", "value": "棉"}]
    assert evidence["delivery_information"] == {"shop_shipping_display_text": "48小时发货"}


def test_quantity_groups_survive_contact_redaction():
    assert minimize("MOQ 1000 2000 3000") == "MOQ 1000 2000 3000"
    assert minimize("价格 1000 2000 3000 件") == "价格 1000 2000 3000 件"


@pytest.mark.parametrize("phone", ["+861234567890", "+86 13800138000", "13800138000", "+84 912 345 678", "(020) 1234 5678", "138 0013 8000", "123-456-7890"])
def test_contact_like_phone_formats_still_redacted(phone):
    projected = minimize("联系 " + phone)
    assert "[ẩn liên hệ]" in projected and not any(character.isdigit() for character in projected)


@pytest.mark.parametrize("field", ["summary", "finding", "limitation", "action"])
@pytest.mark.parametrize("wrong", ["The supplier is reliable and should accept an order.", "供应商可靠，可以订货。",
                                  "Nguồn có thông tin. The supplier is reliable.",
                                  "Nguồn cho thấy supplier is reliable and safe.", "Nguồn hiển thị 中国商品."])
def test_wrong_or_mixed_generated_language_never_becomes_ready(field, wrong):
    data = json.loads(content())
    if field == "finding": data["findings"][0]["text"] = wrong
    elif field == "limitation": data["limitations"][0] = wrong
    elif field == "action": data["actions"][0] = wrong
    else: data[field] = wrong
    store = MemoryStore()
    process_report_once(store, configured(), FakeProvider(json.dumps(data, ensure_ascii=False)))
    assert store.state == "FAILED" and store.code == "INVALID_OUTPUT" and store.report is None


@pytest.mark.parametrize("assertion", ["Điểm rủi ro được hệ thống tính là 72/100.", "Độ tin cậy: khoảng 90%.",
                                       "Hệ thống cho điểm rủi ro tổng thể ở mức 72.",
                                       "Điểm rủi ro được hệ thống tính là bảy mươi hai.",
                                       "Điểm tin cậy là một."])
@pytest.mark.parametrize("field", ["summary", "finding"])
def test_paraphrased_score_assertions_rejected(field, assertion):
    data = json.loads(content())
    if field == "summary": data[field] = assertion
    else: data["findings"][0]["text"] = assertion
    with pytest.raises(ValueError, match="UNSUPPORTED_SCORE"):
        validate_report(json.dumps(data, ensure_ascii=False), [{"id": "E1"}])


def test_vietnamese_source_quantities_and_quoted_source_text_remain_valid():
    data = json.loads(content())
    data["summary"] = "Nguồn hiển thị MOQ 1000 2000 3000 và giá 4.8 USD."
    data["findings"][0]["text"] = 'Trang hiển thị sản phẩm “中国商品” và tỷ lệ đánh giá tích cực 90%.'
    assert validate_report(json.dumps(data, ensure_ascii=False), [{"id": "E1"}])["summary"] == data["summary"]


def test_unicode_escaped_synthetic_key_cannot_be_persisted_as_decoded_prose():
    data = json.loads(content())
    data["summary"] = data["summary"].replace(".", " và mã private-key.")
    escaped = "".join(f"\\u{ord(character):04x}" for character in "private-key")
    output = json.dumps(data, ensure_ascii=False).replace("private-key", escaped)
    assert "private-key" not in output
    assert "private-key" in validate_report(output, [{"id": "E1"}])["summary"]
    store = MemoryStore()
    process_report_once(store, configured(), FakeProvider(output))
    assert store.state == "FAILED" and store.code == "INVALID_OUTPUT" and store.report is None


@pytest.mark.parametrize("change", [{"model_version": ""}, {"api_key": ""}, {"endpoint": "http://provider.test"},
                                    {"budget_usd": Decimal("NaN")}, {"deadline_seconds": float("nan")},
                                    {"input_usd_per_million": Decimal("0")}, {"enabled": False}])
def test_configuration_fails_closed(change):
    assert not configured(**change).available()


def test_malformed_activation_env_fails_closed(monkeypatch):
    monkeypatch.setenv("TEXT_REPORT_ENABLED", "true")
    monkeypatch.setenv("TEXT_REPORT_BUDGET_USD", "not-a-number")
    assert not ReportConfig.from_env().available()


def test_provider_request_pin_limits_usage_and_unknown_cost():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, headers={"x-request-id": "provider-request"}, json={
            "model": "pinned-model", "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "choices": [{"finish_reason": "stop", "message": {"content": content()}}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = YEScaleProvider(client).generate([{"role": "user", "content": "中国商品"}], configured(), "dispatch")
    body = json.loads(requests[0].content)
    assert body["model"] == "pinned-model" and body["max_tokens"] == 2400
    assert requests[0].headers["x-request-id"] == "dispatch"
    assert result["usage"]["completion_tokens"] == 20 and result["request_id"] == "provider-request"
    assert result["actual_cost_usd"] is None and result["cost_provenance"] == "unknown"


@pytest.mark.parametrize("choices", [[None], None, {}, [], [{"finish_reason": "stop", "message": None}],
    [{"finish_reason": "stop", "message": []}], [{"finish_reason": "stop", "message": {"content": None}}],
    [{"finish_reason": None, "message": {"content": content()}}]])
def test_malformed_nested_provider_shapes_keep_safe_trace(choices):
    def handler(request):
        return httpx.Response(200, headers={"x-request-id": "trace-request"}, json={
            "model": "pinned-model", "choices": choices, "usage": {"prompt_tokens": 10, "completion_tokens": 20}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as error:
            YEScaleProvider(client).generate([], configured(), "dispatch")
    assert error.value.code == "INVALID_RESPONSE" and not error.value.uncertain
    assert error.value.metadata["request_id"] == "trace-request"
    assert error.value.metadata["returned_model"] == "pinned-model"
    assert error.value.metadata["usage"]["completion_tokens"] == 20
    assert "private-key" not in json.dumps(error.value.metadata)


@pytest.mark.parametrize("case,code,uncertain", [("model", "UNEXPECTED_MODEL", False), ("length", "OUTPUT_INCOMPLETE", False),
    ("status", "PROVIDER_REJECTED", True), ("timeout", "PROVIDER_TIMEOUT", True),
    ("oversized", "OUTPUT_LIMIT", True), ("json", "INVALID_RESPONSE", False)])
def test_provider_rejections_are_bounded_and_never_retried(case, code, uncertain):
    calls = []
    def handler(request):
        calls.append(request)
        if case == "timeout": raise httpx.ReadTimeout("private-key source details")
        if case == "status": return httpx.Response(503, text="private-key")
        if case == "oversized": return httpx.Response(200, content=b"x" * 50000)
        if case == "json": return httpx.Response(200, text="private-key malformed")
        return httpx.Response(200, json={"model": "other" if case == "model" else "pinned-model",
            "choices": [{"finish_reason": "length" if case == "length" else "stop", "message": {"content": content()}}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as error:
            YEScaleProvider(client).generate([], configured(), "dispatch")
    assert str(error.value) == code and error.value.uncertain == uncertain and len(calls) == 1


def test_deadline_discards_hung_provider():
    from threading import Event
    release = Event()
    class Hanging:
        def generate(self, *args): release.wait(1); return {}
    try:
        with pytest.raises(ProviderError, match="PROVIDER_TIMEOUT"):
            bounded_generate(Hanging(), [], configured(deadline_seconds=0.01), "dispatch")
    finally:
        release.set()
