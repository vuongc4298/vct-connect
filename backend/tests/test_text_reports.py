from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from backend.app.interpretation.contracts import validate_report
from backend.app.interpretation.contracts import screen_vietnamese
from backend.app.interpretation.provider import ReportConfig, YEScaleProvider, ProviderError
from backend.app.interpretation.service import process_report_once, prepare_evidence, bounded_generate
from backend.app.interpretation.service import minimize
from scripts.evaluate_report_prose import evaluate


@pytest.mark.parametrize("text,reason", [
    ("Nguồn có thông tin sản phẩm. " * 60, "SCHEMA_INVALID"),
    ("Nguồn hiển thị điểm rủi ro 5.", "UNSUPPORTED_SCORE"),
])
def test_offline_probe_separates_non_language_rejections(tmp_path, text, reason):
    fixture = tmp_path / "probe.jsonl"
    fixture.write_text(json.dumps({"id": "other", "expected_vietnamese": True, "text": text}), encoding="utf-8")
    result = evaluate(fixture)
    assert result["cases"][0]["screen_accepts"]
    assert result["cases"][0]["report_rejection"]["reason"] == reason
    assert result["report_language_mismatches"] == []
    assert result["report_other_rejections"] == ["other"]


def configured(**kwargs):
    return replace(ReportConfig(enabled=True, endpoint="https://provider.test/v1/chat/completions",
                   api_key="private-key", model="pinned-model", model_version="version-2026-10-05",
                   budget_usd=Decimal("1"), call_ceiling_usd=Decimal("0.1"),
                   input_usd_per_million=Decimal("1"), output_usd_per_million=Decimal("2")), **kwargs)


def content(citation="E1"):
    return json.dumps({"summary": "Nguồn có thông tin sản phẩm; cần xác minh trước đặt hàng.",
                       "findings": [{"kind": "observation", "text": "Trang hiển thị sản phẩm.", "citations": [citation]}],
                       "limitations": ["Chưa xác minh độc lập."], "actions": ["Yêu cầu mẫu trước đặt cọc."],
                       "self_reported_confidence": {"score": 0.65, "basis": "Dữ liệu nguồn còn thiếu; cần xác minh độc lập."}}, ensure_ascii=False)


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


@pytest.mark.parametrize("quoted", [
    "'Women's Autumn and Winter Retro Elegant Knitted Texture Fabric V Neck Slim Long Sleeve Long Dress'",
    "‘Women's Autumn and Winter Long Dress’", "‘Women’s Autumn and Winter Long Dress’", "'中国商品'",
    "'Girls' Autumn and Winter Retro Elegant Knitted Texture Fabric V Neck Slim Long Sleeve Long Dress'",
    "‘Girls’ Autumn and Winter Long Dress’",
])
def test_single_quoted_source_titles_preserve_vietnamese_context(quoted):
    data = json.loads(content())
    data["findings"][0]["text"] = f"Nguồn liệt kê một sản phẩm: {quoted}."
    evidence = [{"id": "E1", "value": [{"title": quoted[1:-1].replace("’", "'")}]}]
    assert validate_report(json.dumps(data, ensure_ascii=False), evidence)["findings"] == data["findings"]


@pytest.mark.parametrize("prose", [
    "'The supplier is reliable and should accept an order.'",
    "Nguồn có thông tin '中国商品'. The supplier is reliable.",
    "Nguồn liệt kê một sản phẩm: 'Women's Autumn and Winter Long Dress.",
    "Nguồn có thông tin supplier's terms and buyer's order are reliable.",
])
def test_single_quotes_do_not_hide_unquoted_foreign_prose(prose):
    assert not screen_vietnamese(prose)


def test_single_quotes_do_not_hide_unsupported_scores():
    data = json.loads(content())
    data["summary"] = "Nguồn hiển thị 'Điểm rủi ro là 72'."
    with pytest.raises(ValueError, match="UNSUPPORTED_SCORE"):
        validate_report(json.dumps(data, ensure_ascii=False), [{"id": "E1"}])


@pytest.mark.parametrize("prose", [
    "Nguồn có thông tin '中国商品'and the supplier is reliable '中国商品'.",
    "Nguồn có thông tin ‘中国商品’and the supplier is reliable ‘中国商品’.",
    "Nguồn liệt kê một sản phẩm: 'The supplier is reliable and should accept an order'.",
])
def test_single_quoted_source_matching_keeps_foreign_prose_visible(prose):
    data = json.loads(content())
    data["findings"][0]["text"] = prose
    with pytest.raises(ValueError, match="NON_VIETNAMESE_PROSE"):
        validate_report(json.dumps(data, ensure_ascii=False), [{"id": "E1", "value": "中国商品"}])


@pytest.mark.parametrize("values", [["中国'商品'中国", "商品"], ["商品", "中国'商品'中国"]])
def test_nested_source_apostrophes_do_not_depend_on_evidence_order(values):
    data = json.loads(content())
    data["findings"][0]["text"] = "Nguồn liệt kê một sản phẩm: ‘中国'商品'中国’."
    assert validate_report(json.dumps(data, ensure_ascii=False), [{"id": "E1", "value": values}])


def test_source_removal_cannot_manufacture_another_source_match():
    data = json.loads(content())
    data["findings"][0]["text"] = "Nguồn có thông tin '中国'Autumn'商品'."
    with pytest.raises(ValueError, match="NON_VIETNAMESE_PROSE"):
        validate_report(json.dumps(data, ensure_ascii=False), [{"id": "E1", "value": ["Autumn", "中国商品"]}])


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
    assert "thinking" not in body
    assert requests[0].headers["x-request-id"] == "dispatch"
    assert result["usage"]["completion_tokens"] == 20 and result["request_id"] == "provider-request"
    assert result["actual_cost_usd"] is None and result["cost_provenance"] == "unknown"


@pytest.mark.parametrize("returned,accepted", [("deepseek-v4-1-flash-260910", True),
    ("deepseek-v4.1-flash", False), ("deepseek-v4-1-flash-261001", False), (None, False)])
def test_explicit_returned_version_and_thinking_request(returned, accepted):
    requests = []
    config = configured(model="deepseek-v4.1-flash",
        expected_returned_model="deepseek-v4-1-flash-260910", thinking="disabled")
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"model": returned,
            "choices": [{"finish_reason": "stop", "message": {"content": content()}}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        if accepted:
            assert YEScaleProvider(client).generate([], config, "dispatch")["returned_model"] == returned
        else:
            with pytest.raises(ProviderError, match="UNEXPECTED_MODEL"):
                YEScaleProvider(client).generate([], config, "dispatch")
    body = json.loads(requests[0].content)
    assert body["model"] == "deepseek-v4.1-flash"
    assert body["thinking"] == {"type": "disabled"} and len(requests) == 1


@pytest.mark.parametrize("returned,expected", [("deepseek-v4-1-flash-260910", "READY"),
                                            ("deepseek-v4.1-flash", "FAILED")])
def test_service_checks_configured_returned_version_and_preserves_provenance(returned, expected):
    class VersionProvider(FakeProvider):
        def generate(self, *args):
            return {**super().generate(*args), "returned_model": returned}
    store = MemoryStore()
    config = configured(model="deepseek-v4.1-flash",
        expected_returned_model="deepseek-v4-1-flash-260910", thinking="disabled")
    process_report_once(store, config, VersionProvider())
    assert store.state == expected
    assert store.metadata["model"] == config.model
    assert store.metadata["expected_returned_model"] == config.expected_returned_model
    assert store.metadata["returned_model"] == returned and store.metadata["thinking"] == "disabled"


def test_returned_version_and_thinking_environment_settings(monkeypatch):
    monkeypatch.setenv("YESCALE_EXPECTED_RETURNED_MODEL", "dated-version")
    monkeypatch.setenv("YESCALE_THINKING", "disabled")
    config = ReportConfig.from_env()
    assert config.expected_returned_model == "dated-version" and config.thinking == "disabled"
    assert not configured(thinking="typo").available()
    store, provider = MemoryStore(), FakeProvider()
    process_report_once(store, configured(thinking="typo"), provider)
    assert store.state == "UNAVAILABLE" and not provider.calls and not store.reservations


@pytest.mark.parametrize("prose", [
    "Nguồn liệt kê một sản phẩm váy dài tay, cổ V, chất liệu dệt kim, phong cách retro thanh lịch cho nữ mùa thu đông.",
    "Dữ liệu trích xuất ở trạng thái PARTIAL; nhiều trường bị thiếu.",
    "Không rõ thời điểm thu thập dữ liệu (capture_freshness: unknown).",
    "Không có thông tin về chính sách đổi trả, bảo hành, hoặc xử lý khiếu nại.",
    "Yêu cầu báo giá chính thức bao gồm phí vận chuyển, thuế, phí nền tảng và điều kiện thanh toán.",
    "Thống nhất điều khoản đặt cọc, hoàn tiền và xử lý tranh chấp bằng văn bản trước khi thanh toán.",
])
def test_valid_vietnamese_purchasing_prose_is_not_rejected(prose):
    assert screen_vietnamese(prose)


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


@pytest.mark.parametrize("confidence,reason,location", [
    (None, "SCHEMA_INVALID", "self_reported_confidence"),
    ({}, "SCHEMA_INVALID", "self_reported_confidence.score"),
    *(({"score": score, "basis": "Chưa xác minh độc lập."}, "SCHEMA_INVALID", "self_reported_confidence.score")
      for score in [True, -0.01, 1.01, float("nan"), float("inf"), "0.5"]),
    *(({"score": 0.5, "basis": basis}, "NON_VIETNAMESE_PROSE", "self_reported_confidence.basis")
      for basis in ["The supplier is reliable.", "供应商可靠", "Nguồn hiển thị sản phẩm. “供应商可靠，放心购买”", 'Nguồn hiển thị sản phẩm. "The supplier is reliable."']),
    ({"score": 0.5, "basis": "Độ tin cậy là 90%."}, "UNSUPPORTED_SCORE", "self_reported_confidence.basis"),
    ({"score": 0.5, "basis": "Chưa xác minh độc lập.", "calibration": "calibrated"}, "SCHEMA_INVALID", "self_reported_confidence")])
def test_bad_confidence_fails_with_safe_location(confidence, reason, location):
    data = json.loads(content())
    if confidence is None:
        del data["self_reported_confidence"]
    else:
        data["self_reported_confidence"] = confidence
    store = MemoryStore()
    process_report_once(store, configured(), FakeProvider(json.dumps(data, ensure_ascii=False)))
    assert store.state == "FAILED" and store.code == "INVALID_OUTPUT" and store.report is None
    assert (store.metadata["validation_reason"], store.metadata["validation_location"]) == (reason, location)


@pytest.mark.parametrize("score", [0, 0.65, 1])
def test_valid_confidence_is_application_labeled_and_prompt_versioned(score):
    data = json.loads(content())
    data["self_reported_confidence"]["score"] = score
    store, provider = MemoryStore(), FakeProvider(json.dumps(data, ensure_ascii=False))
    process_report_once(store, configured(), provider)
    assert store.state == "READY"
    assert store.report["self_reported_confidence"] == {
        **data["self_reported_confidence"], "provenance": "model_self_reported", "calibration": "uncalibrated"}
    assert store.metadata["prompt_version"] == "vi-text.v7"
    assert store.metadata["schema_version"] == "text-report.v2"
    assert 'self_reported_confidence' in provider.calls[0][0][0]["content"]


@pytest.mark.parametrize("case,reason,location", [
    ("json", "SCHEMA_INVALID", "report"), ("extra_key", "SCHEMA_INVALID", "report"),
    ("nested_key", "SCHEMA_INVALID", "findings"), ("schema", "SCHEMA_INVALID", "findings.kind"),
    ("citation", "UNKNOWN_CITATION", "findings.citations"),
    ("score", "UNSUPPORTED_SCORE", "summary"), ("language", "NON_VIETNAMESE_PROSE", "actions"),
    ("literal_key", "CREDENTIAL_ECHO", "report"), ("escaped_key", "CREDENTIAL_ECHO", "report"),
    ("escaped_extra_key", "CREDENTIAL_ECHO", "report")])
def test_diagnostics_never_retain_rejected_values_keys_or_exceptions(case, reason, location):
    data = json.loads(content())
    sentinel = "sensitive-source-value"
    if case == "extra_key": data[sentinel] = sentinel
    if case == "nested_key": data["findings"][0][sentinel] = sentinel
    if case == "schema": data["findings"][0]["kind"] = sentinel
    if case == "citation": data["findings"][0]["citations"] = ["E99"]
    if case == "score": data["summary"] = "Điểm rủi ro là 72%."
    if case == "language": data["actions"] = [sentinel]
    if case in {"literal_key", "escaped_key"}: data["summary"] = "private-key"
    if case == "escaped_extra_key": data["private-key"] = sentinel
    output = json.dumps(data, ensure_ascii=False)
    if case.startswith("escaped"):
        output = output.replace("private-key", "".join(f"\\u{ord(char):04x}" for char in "private-key"))
    if case == "json": output = '{"' + sentinel
    store, provider = MemoryStore(), FakeProvider(output)
    process_report_once(store, configured(), provider)
    assert store.state == "FAILED" and store.report is None and store.code == "INVALID_OUTPUT"
    assert (store.metadata["validation_reason"], store.metadata["validation_location"]) == (reason, location)
    serialized = json.dumps(store.metadata)
    assert sentinel not in serialized and "private-key" not in serialized and "ValidationError" not in serialized
    assert not process_report_once(store, configured(), provider) and len(provider.calls) == 1


@pytest.mark.parametrize("field", ["summary", "findings", "limitations", "actions", "self_reported_confidence"])
def test_confidence_score_cannot_be_repeated_in_prose(field):
    data = json.loads(content())
    prose = "Điểm tự báo cáo của mô hình là 0.65; cần xác minh độc lập."
    if field == "findings": data[field][0]["text"] = prose
    elif field == "self_reported_confidence": data[field]["basis"] = prose
    elif field in {"limitations", "actions"}: data[field] = [prose]
    else: data[field] = prose
    store = MemoryStore()
    process_report_once(store, configured(), FakeProvider(json.dumps(data, ensure_ascii=False)))
    assert store.state == "FAILED" and store.metadata["validation_reason"] == "UNSUPPORTED_SCORE"


@pytest.mark.parametrize("case", ["nesting", "duplicate", "escaped_duplicate"])
def test_complete_invalid_json_never_settles_as_uncertain_or_hides_credentials(case):
    if case == "nesting": output = "[" * 2000 + "0" + "]" * 2000
    else:
        key = "".join(f"\\u{ord(char):04x}" for char in "private-key")
        first = key if case == "escaped_duplicate" else "Nguồn hiển thị sản phẩm."
        output = '{"summary":"' + first + '",' + content()[1:]
    store, provider = MemoryStore(), FakeProvider(output)
    process_report_once(store, configured(), provider)
    assert store.state == "FAILED" and store.report is None and store.code == "INVALID_OUTPUT"
    assert store.metadata["validation_reason"] == ("CREDENTIAL_ECHO" if case == "escaped_duplicate" else "SCHEMA_INVALID")
    assert store.metadata["validation_location"] == "report"
    assert "private-key" not in json.dumps(store.metadata)
    assert not process_report_once(store, configured(), provider) and len(provider.calls) == 1


def test_natural_vietnamese_confidence_basis_is_accepted():
    data = json.loads(content())
    data["self_reported_confidence"]["basis"] = "Tôi khá chắc chắn về cách diễn giải vì nội dung nhất quán."
    store = MemoryStore()
    process_report_once(store, configured(), FakeProvider(json.dumps(data, ensure_ascii=False)))
    assert store.state == "READY"


@pytest.mark.parametrize("basis", [
    "Diễn giải dựa trên 2 đánh giá; chưa xác minh độc lập.",
    "Nguồn hiển thị giá 2.01; chưa xác minh độc lập.",
    "Diễn giải dựa trên hai đánh giá; cần kiểm tra mẫu.",
    "Dữ liệu nguồn chỉ có một phần; cần xác minh độc lập.",
    "Nội dung nguồn nhất quán; chưa xác minh độc lập.",
])
def test_qualitative_confidence_basis_with_source_numbers_settles_ready(basis):
    data = json.loads(content())
    data["self_reported_confidence"]["basis"] = basis
    store, provider = MemoryStore(), FakeProvider(json.dumps(data, ensure_ascii=False))
    process_report_once(store, configured(), provider)
    assert store.state == "READY"
    assert store.report["self_reported_confidence"] == {
        "score": 0.65, "basis": basis, "provenance": "model_self_reported", "calibration": "uncalibrated"}
    assert store.metadata["prompt_version"] == "vi-text.v7"
    assert not process_report_once(store, configured(), provider) and len(provider.calls) == 1


@pytest.mark.parametrize("prose", [
    "Độ tin cậy là 65%.", "Điểm tin cậy là 0.65.", "Điểm tự báo cáo là hai phần ba.",
    "Điểm rủi ro là bảy mươi hai.", "Độ tin cậy là 65/100.",
])
@pytest.mark.parametrize("field", ["summary", "findings", "limitations", "actions", "self_reported_confidence"])
def test_numeric_and_number_word_scores_fail_safely_in_every_prose_field(prose, field):
    data = json.loads(content())
    if field == "findings": data[field][0]["text"] = prose
    elif field == "self_reported_confidence": data[field]["basis"] = prose
    elif field in {"limitations", "actions"}: data[field] = [prose]
    else: data[field] = prose
    location = {"findings": "findings.text", "self_reported_confidence": "self_reported_confidence.basis"}.get(field, field)
    store, provider = MemoryStore(), FakeProvider(json.dumps(data, ensure_ascii=False))
    process_report_once(store, configured(), provider)
    assert store.state == "FAILED" and store.report is None
    assert (store.metadata["validation_reason"], store.metadata["validation_location"]) == ("UNSUPPORTED_SCORE", location)
    assert prose not in json.dumps(store.metadata, ensure_ascii=False)
    assert not process_report_once(store, configured(), provider) and len(provider.calls) == 1


def test_embedded_foreign_brand_requires_vietnamese_rendering():
    from backend.app.interpretation.contracts import ReportValidationError
    data = json.loads(content())
    data["summary"] = "Trang hi\u1ec3n th\u1ecb s\u1ea3n ph\u1ea9m kh\u0103n gi\u1ea5y th\u01b0\u01a1ng hi\u1ec7u \u6d4b\u8bd5."
    with pytest.raises(ReportValidationError) as error:
        validate_report(json.dumps(data), [{"id": "E1", "value": "source"}])
    assert (error.value.reason, error.value.location) == ("NON_VIETNAMESE_PROSE", "summary")
    data["summary"] = "Trang hi\u1ec3n th\u1ecb s\u1ea3n ph\u1ea9m kh\u0103n gi\u1ea5y; ch\u01b0a x\u00e1c minh \u0111\u1ed9c l\u1eadp."
    assert validate_report(json.dumps(data), [{"id": "E1", "value": "source"}])["summary"] == data["summary"]


def test_vietnamese_tissue_description_with_source_quote():
    data = json.loads(content())
    title = "\u6d4b\u8bd5"
    data["findings"][0]["text"] = "Ti\u00eau \u0111\u1ec1 s\u1ea3n ph\u1ea9m '" + title + "' g\u1ee3i \u00fd \u0111\u00e2y l\u00e0 kh\u0103n gi\u1ea5y \u0103n d\u1ea1ng r\u00fat, ba l\u1edbp; ti\u00eau \u0111\u1ec1 tuy\u00ean b\u1ed1 m\u1ec1m m\u1ea1i v\u00e0 ph\u00f9 h\u1ee3p cho da nh\u1ea1y c\u1ea3m v\u00e0 tr\u1ebb em."
    evidence = [{"id":"E1", "value":{"title": title}}]
    assert validate_report(json.dumps(data), evidence)
    data["findings"][0]["text"] += " The supplier is reliable."
    with pytest.raises(ValueError):
        validate_report(json.dumps(data), evidence)


@pytest.mark.parametrize("prose", [
    "Theo ng\u01b0\u1eddi b\u00e1n, th\u1eddi gian g\u1eedi h\u00e0ng trung b\u00ecnh l\u00e0 18 gi\u1edd v\u00e0 ph\u1ea3n h\u1ed3i kh\u00e1ch h\u00e0ng trung b\u00ecnh l\u00e0 12 gi\u00e2y.",
    "Th\u00f4ng tin v\u1eadn chuy\u1ec3n v\u00e0 ph\u1ea3n h\u1ed3i kh\u00e1ch h\u00e0ng do ng\u01b0\u1eddi b\u00e1n c\u00f4ng b\u1ed1, ch\u01b0a x\u00e1c minh \u0111\u1ed9c l\u1eadp.",
])
def test_vietnamese_shipping_service_prose_with_versioned_validation(prose):
    data = json.loads(content())
    data["findings"][0]["text"] = prose
    store = MemoryStore()
    process_report_once(store, configured(), FakeProvider(json.dumps(data)))
    assert store.state == "READY"
    assert store.metadata["validation_version"] == "vi-prose.v3"
    assert store.metadata["prompt_version"] == "vi-text.v7"
    for foreign in [" The supplier is reliable.", " \u4f9b\u5e94\u5546\u53ef\u9760", " Le fournisseur est fiable."]:
        assert not screen_vietnamese(prose + foreign)
    data["findings"][0]["citations"] = ["E99"]
    with pytest.raises(ValueError):
        validate_report(json.dumps(data), [{"id":"E1","value":"source"}])


PROSE_CASES = [json.loads(line) for line in
    (Path(__file__).parent / "fixtures/vietnamese_report_prose.jsonl").read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("case", PROSE_CASES, ids=[case["id"] for case in PROSE_CASES])
def test_offline_source_related_prose_corpus(case):
    # Synthetic language examples; acceptance here does not verify a claim's truth.
    assert screen_vietnamese(case["text"]) is case["expected_vietnamese"]


def test_authentic_taobao_grounding_projection_and_vietnamese_settlement():
    from backend.app.extraction import parse_taobao_page
    html = (Path(__file__).parent / "fixtures/taobao_item_1076425861755.html").read_text(encoding="utf-8")
    source = "https://item.taobao.com/item.htm?id=1076425861755"
    payload = parse_taobao_page(html, source, extraction_method="USER_UPLOAD", uploaded_bytes=html.encode("utf-8"))
    assert payload["supplier_data"]["extractor_version"] == "taobao-upload.v1"
    assert payload["raw_payload"]["provenance"] == "USER_PROVIDED_SAVED_PAGE"
    assert payload["raw_payload"]["captured_at"] is None
    store = MemoryStore()
    store.row.update(source_url=source, supplier_data=payload["supplier_data"], reviews=payload["reviews"])
    original = json.dumps(store.row["supplier_data"], ensure_ascii=False, sort_keys=True)
    # Hand-authored output verifies compatibility and settlement, not live model semantics.
    data = json.loads(content())
    texts = [
        ("Theo tiêu đề, sản phẩm là khăn giấy rút 100 lượt, 3 lớp; chưa xác minh độc lập.", ["E1"]),
        ("Giá hiển thị trước ưu đãi từ 3.35 tệ, sau ưu đãi từ 2.01 tệ; phí chưa xác định.", ["E2"]),
        ("Nguồn hiển thị tỷ lệ đánh giá tích cực sản phẩm 100% trong 3 tháng; cửa hàng có tỷ lệ 97% cho người mua thành viên.", ["E3"]),
        ("Cửa hàng công bố thời gian gửi hàng trung bình 23 giờ; chưa xác minh độc lập.", ["E4"]),
        ("Một người mua khen chất lượng; người khác cho biết giấy hơi xốp, độ dày trung bình và đủ dùng hằng ngày.", ["E5", "E6"]),
    ]
    data["findings"] = [{"kind": "observation", "text": text, "citations": refs} for text, refs in texts]
    provider = FakeProvider(json.dumps(data, ensure_ascii=False))
    assert process_report_once(store, configured(), provider) and store.state == "READY"
    evidence = store.report["evidence"]
    assert [e["id"] for e in evidence] == [f"E{i}" for i in range(1, 7)]
    assert evidence[2]["scope"] == {"positive_review_rate_display_text": "product", "shop_metrics_display_text": "shop"}
    assert evidence[1]["value"]["price"]["priceDesc"] == evidence[1]["value"]["extraPrice"]["priceDesc"] == "起"
    assert evidence[3]["value"]["shop_shipping_display_text"] == ["平均23小时发货"]
    exported = provider.calls[0][0][1]["content"]
    assert json.loads(exported)["evidence"] == evidence
    for private in ("心相印维达生活馆", "159450000", "2895982467", "1076425861755", "<html>", source):
        assert private not in exported
    assert json.dumps(store.row["supplier_data"], ensure_ascii=False, sort_keys=True) == original
    assert store.metadata["prompt_version"] == "vi-text.v7"
    assert store.report["self_reported_confidence"]["calibration"] == "uncalibrated"
    assert not process_report_once(store, configured(), provider) and len(provider.calls) == 1


@pytest.mark.parametrize("version", ["taobao-http.v1", "taobao-upload.v1", "public-browser.v1", "taobao-raw.v2"])
def test_scope_annotation_follows_audited_taobao_item_provenance(version):
    data = {"platform": "TAOBAO", "offer_id": "item", "extractor_version": version,
            "transaction_signals": {"positive_review_rate_display_text": "近3个月好评率90%"}}
    entry = prepare_evidence({"supplier_data": data})[0]
    assert entry["scope"] == {"positive_review_rate_display_text": "product"}
    assert entry["value"] == data["transaction_signals"]


@pytest.mark.parametrize("override", [
    {"platform": "ALIBABA"}, {"offer_id": None}, {"extractor_version": "unknown"},
    {"transaction_signals": {"sales_display_text": "2万+"}},
])
def test_scope_annotation_does_not_invent_missing_or_unsupported_scope(override):
    data = {"platform": "TAOBAO", "offer_id": "item", "extractor_version": "taobao-upload.v1",
            "transaction_signals": {"positive_review_rate_display_text": "100%", "shop_metrics_display_text": ["97%"]}, **override}
    assert "scope" not in prepare_evidence({"supplier_data": data})[0]
