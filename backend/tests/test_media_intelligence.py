from decimal import Decimal
import json

import httpx
import pytest

from backend.app.intelligence.media import (
    MEDIA_SCHEMA_VERSION,
    ReviewMediaInput,
    interpret_review_media,
)
from backend.app.intelligence.provider import ProviderResponse, ProviderUsage
from backend.app.intelligence.yescale import YEScaleProvider


PNG_DATA = "data:image/png;base64,aGVsbG8="
JPEG_DATA = "data:image/jpeg;base64,d29ybGQ="


class FakeMultimodalProvider:
    def __init__(self, output=None):
        self.calls = []
        self.output = output or {
            "schema_version": MEDIA_SCHEMA_VERSION,
            "language": "vi",
            "findings": [
                {
                    "media_id": "img-1",
                    "review_evidence_id": "r1",
                    "consistency": "SUPPORTS",
                    "statement_vi": "Hình ảnh cho thấy đường may bị lệch như đánh giá mô tả.",
                    "confidence": 0.9,
                    "timestamp_ms": None,
                },
                {
                    "media_id": "vid-1-frame-2000",
                    "review_evidence_id": "r2",
                    "consistency": "PARTIALLY_SUPPORTS",
                    "statement_vi": "Khung hình cho thấy bao bì móp, nhưng không đủ để xác nhận toàn bộ video.",
                    "confidence": 0.72,
                    "timestamp_ms": 2000,
                },
            ],
            "confidence": 0.82,
        }

    def generate_multimodal_json(self, **kwargs):
        self.calls.append(kwargs)
        return ProviderResponse(
            provider="FAKE_MEDIA",
            request_id="media-request-1",
            requested_model=kwargs["model"],
            response_model="fixture-vision-v1",
            content=json.dumps(self.output, ensure_ascii=False),
            usage=ProviderUsage(120, 80, 200, Decimal("0.003"), {"total_tokens": 200}),
            latency_ms=150,
            finish_reason="stop",
            settings={"temperature": kwargs["temperature"], "max_tokens": kwargs["max_tokens"]},
        )


def accessible_fixture():
    return [
        ReviewMediaInput(
            media_id="img-1",
            review_evidence_id="r1",
            media_type="IMAGE",
            access_status="ACCESSIBLE",
            private_ref="blob://reviews/r1/image-1",
            mime_type="image/png",
            data_url=PNG_DATA,
        ),
        ReviewMediaInput(
            media_id="vid-1-frame-2000",
            review_evidence_id="r2",
            media_type="VIDEO_FRAME",
            access_status="ACCESSIBLE",
            private_ref="blob://reviews/r2/video-1",
            mime_type="image/jpeg",
            data_url=JPEG_DATA,
            timestamp_ms=2000,
        ),
    ]


def test_accessible_image_and_video_frame_produce_consistency_findings_and_provenance():
    provider = FakeMultimodalProvider()
    run = interpret_review_media(
        {"r1": "The stitching is crooked.", "r2": "Packaging arrived damaged."},
        accessible_fixture(),
        provider=provider,
        model="fixture-vision",
    )
    assert run.assessment.schema_version == MEDIA_SCHEMA_VERSION
    assert [(f.media_id, f.consistency) for f in run.assessment.findings] == [
        ("img-1", "SUPPORTS"),
        ("vid-1-frame-2000", "PARTIALLY_SUPPORTS"),
    ]
    assert run.assessment.findings[1].timestamp_ms == 2000
    assert run.assessment.confidence == 0.82
    assert run.provider_response.request_id == "media-request-1"
    assert len(run.input_sha256) == 64
    assert all(p.content_sha256 and len(p.content_sha256) == 64 for p in run.assessment.provenance)
    assert run.assessment.provenance[1].private_ref == "blob://reviews/r2/video-1"
    serialized = json.dumps(run.input_payload)
    assert "data:image" not in serialized
    assert "aGVsbG8=" not in serialized
    assert "d29ybGQ=" not in serialized


def test_inaccessible_media_is_marked_missing_without_provider_call():
    provider = FakeMultimodalProvider()
    run = interpret_review_media(
        {"r1": "Photo should show a damaged seam."},
        [
            ReviewMediaInput(
                media_id="img-missing",
                review_evidence_id="r1",
                media_type="IMAGE",
                access_status="MISSING",
                private_ref="blob://reviews/r1/missing",
                missing_reason="Ảnh nguồn không còn truy cập được.",
            )
        ],
        provider=provider,
        model="fixture-vision",
    )
    assert provider.calls == []
    assert run.provider_response is None
    assert run.assessment.missing_media_ids == ["img-missing"]
    finding = run.assessment.findings[0]
    assert finding.consistency == "CANNOT_DETERMINE"
    assert finding.confidence == 0
    assert "không còn truy cập" in finding.statement_vi


def test_text_only_path_does_not_require_media_or_provider_call():
    provider = FakeMultimodalProvider()
    run = interpret_review_media(
        {"r1": "Text-only review."},
        [],
        provider=provider,
        model="fixture-vision",
    )
    assert provider.calls == []
    assert run.provider_response is None
    assert run.assessment.findings == []
    assert run.assessment.provenance == []
    assert run.assessment.confidence == 0


def test_model_cannot_cite_unknown_or_inaccessible_media():
    provider = FakeMultimodalProvider({
        "schema_version": MEDIA_SCHEMA_VERSION,
        "language": "vi",
        "findings": [{
            "media_id": "invented",
            "review_evidence_id": "r1",
            "consistency": "SUPPORTS",
            "statement_vi": "Không hợp lệ.",
            "confidence": 0.8,
            "timestamp_ms": None,
        }],
        "confidence": 0.8,
    })
    with pytest.raises(ValueError, match="unknown or inaccessible media ID"):
        interpret_review_media(
            {"r1": "Review."},
            [accessible_fixture()[0]],
            provider=provider,
            model="fixture-vision",
        )


def test_model_cannot_change_review_link_or_video_timestamp():
    for changed in [
        {"review_evidence_id": "r1"},
        {"timestamp_ms": 9999},
    ]:
        finding = {
            "media_id": "vid-1-frame-2000",
            "review_evidence_id": "r2",
            "consistency": "SUPPORTS",
            "statement_vi": "Có bằng chứng.",
            "confidence": 0.8,
            "timestamp_ms": 2000,
            **changed,
        }
        provider = FakeMultimodalProvider({
            "schema_version": MEDIA_SCHEMA_VERSION,
            "language": "vi",
            "findings": [finding],
            "confidence": 0.8,
        })
        with pytest.raises(ValueError):
            interpret_review_media(
                {"r1": "Other.", "r2": "Packaging damaged."},
                [accessible_fixture()[1]],
                provider=provider,
                model="fixture-vision",
            )


def test_missing_model_finding_fails_to_cannot_determine_instead_of_guessing():
    provider = FakeMultimodalProvider({
        "schema_version": MEDIA_SCHEMA_VERSION,
        "language": "vi",
        "findings": [],
        "confidence": 0.4,
    })
    run = interpret_review_media(
        {"r1": "Review."},
        [accessible_fixture()[0]],
        provider=provider,
        model="fixture-vision",
    )
    assert run.assessment.findings[0].consistency == "CANNOT_DETERMINE"
    assert run.assessment.findings[0].confidence == 0


def test_accessible_media_requires_supported_data_url_and_video_timestamp():
    with pytest.raises(ValueError):
        ReviewMediaInput(
            media_id="bad",
            review_evidence_id="r1",
            media_type="IMAGE",
            access_status="ACCESSIBLE",
            private_ref="private",
            mime_type="image/png",
            data_url="https://public.example/image.png",
        ).validate()
    with pytest.raises(ValueError):
        ReviewMediaInput(
            media_id="video",
            review_evidence_id="r1",
            media_type="VIDEO_FRAME",
            access_status="ACCESSIBLE",
            private_ref="private",
            mime_type="image/png",
            data_url=PNG_DATA,
        ).validate()


def test_yescale_multimodal_adapter_uses_openai_compatible_image_content_without_private_refs():
    captured = {}

    def handler(request: httpx.Request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"X-YEScale-Request-Id": "vision-request-1"},
            json={
                "model": "vision-model-v1",
                "choices": [{
                    "message": {"content": json.dumps({"ok": True})},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = YEScaleProvider("secret", client=client, clock=lambda: 1.0)
        result = provider.generate_multimodal_json(
            model="vision-candidate",
            system_prompt="system",
            user_prompt="prompt without private ref",
            images=[
                __import__("backend.app.intelligence.provider", fromlist=["VisualInput"]).VisualInput(
                    media_id="img-1", data_url=PNG_DATA
                )
            ],
            temperature=0.1,
            max_tokens=200,
            metadata={"feature": "review_media"},
        )

    messages = captured["body"]["messages"]
    assert messages[1]["content"][0] == {"type": "text", "text": "prompt without private ref"}
    assert messages[1]["content"][1] == {"type": "text", "text": "MEDIA_ID: img-1"}
    assert messages[1]["content"][2]["type"] == "image_url"
    assert messages[1]["content"][2]["image_url"]["url"] == PNG_DATA
    assert result.request_id == "vision-request-1"
    assert result.settings["image_count"] == 1


def test_media_output_schema_rejects_risk_score_field():
    provider = FakeMultimodalProvider({
        "schema_version": MEDIA_SCHEMA_VERSION,
        "language": "vi",
        "findings": [],
        "confidence": 0.5,
        "risk_score": 90,
    })
    with pytest.raises(ValueError, match="media interpretation schema"):
        interpret_review_media(
            {"r1": "Review."},
            [accessible_fixture()[0]],
            provider=provider,
            model="fixture-vision",
        )
