from decimal import Decimal
import json

import httpx
import pytest

from backend.app.intelligence.provider import EmbeddingResponse, ProviderResponse, ProviderUsage
from backend.app.intelligence.reviews import ReviewEvidence
from backend.app.intelligence.semantic_reviews import (
    SEMANTIC_REVIEW_SCHEMA_VERSION,
    cluster_near_duplicates,
    interpret_reviews,
)
from backend.app.intelligence.yescale import ProviderError, YEScaleProvider


def reviews_fixture():
    return [
        {"evidence_id": "r1", "text": "The fabric is thin and stitching is poor.", "rating": 5},
        {"evidence_id": "r2", "text": "Thin material with very poor stitching quality.", "rating": 5},
        {"evidence_id": "r3", "text": "Shipping arrived very late.", "rating": 2},
        {"evidence_id": "r4", "text": "Delivery was delayed for many days.", "rating": 2},
        {"evidence_id": "r5", "text": "Sizing was correct and packaging was fine.", "rating": 5},
        {"evidence_id": "r6", "text": "Color matched the listing.", "rating": 5},
        {"evidence_id": "r7", "text": "Seller answered my question.", "rating": 4},
        {"evidence_id": "r8", "text": "Neutral note about the order.", "rating": 3},
    ]


class FakeEmbeddings:
    def embed_texts(self, **kwargs):
        return EmbeddingResponse(
            provider="FAKE_EMBEDDING",
            request_id="embed-req-1",
            requested_model=kwargs["model"],
            response_model="fixture-embedding-v1",
            vectors=(
                (1.0, 0.0, 0.0),
                (0.99, 0.04, 0.0),
                (0.0, 1.0, 0.0),
                (0.0, 0.99, 0.04),
                (0.0, 0.0, 1.0),
                (0.5, 0.5, 0.7),
                (-0.7, 0.2, 0.1),
                (0.1, -0.7, 0.2),
            ),
            usage=ProviderUsage(80, 0, 80, Decimal("0.0004"), {"prompt_tokens": 80}),
            latency_ms=33,
            settings={"encoding_format": "float"},
        )


class FakeLLM:
    def __init__(self, output=None):
        self.output = output or {
            "schema_version": SEMANTIC_REVIEW_SCHEMA_VERSION,
            "language": "vi",
            "findings": [
                {
                    "category": "QUALITY",
                    "severity": "HIGH",
                    "statement_vi": "Hai đánh giá mô tả vật liệu mỏng và đường may kém.",
                    "evidence_ids": ["r1", "r2"],
                    "confidence": 0.92,
                },
                {
                    "category": "DELIVERY",
                    "severity": "MEDIUM",
                    "statement_vi": "Hai đánh giá phản ánh giao hàng chậm.",
                    "evidence_ids": ["r3", "r4"],
                    "confidence": 0.88,
                },
            ],
            "confidence": 0.86,
        }

    def generate_json(self, **kwargs):
        return ProviderResponse(
            provider="FAKE_LLM",
            request_id="llm-req-1",
            requested_model=kwargs["model"],
            response_model="fixture-chat-v1",
            content=json.dumps(self.output, ensure_ascii=False),
            usage=ProviderUsage(300, 120, 420, Decimal("0.002"), {"total_tokens": 420}),
            latency_ms=120,
            finish_reason="stop",
            settings={"temperature": kwargs["temperature"], "max_tokens": kwargs["max_tokens"]},
        )


def test_mixed_fixture_yields_findings_clusters_reliability_and_provenance():
    run = interpret_reviews(
        reviews_fixture(),
        aggregate_review_count=8,
        embedding_provider=FakeEmbeddings(),
        embedding_model="fixture-embed",
        provider=FakeLLM(),
        model="fixture-chat",
    )
    assert run.assessment.schema_version == SEMANTIC_REVIEW_SCHEMA_VERSION
    assert [(finding.category, finding.severity) for finding in run.assessment.findings] == [
        ("QUALITY", "HIGH"), ("DELIVERY", "MEDIUM")
    ]
    assert [cluster.evidence_ids for cluster in run.semantic_clusters] == [["r1", "r2"], ["r3", "r4"]]
    semantic = [pattern for pattern in run.assessment.suspicious_patterns
                if pattern.kind == "SEMANTIC_NEAR_DUPLICATE"]
    assert [pattern.evidence_ids for pattern in semantic] == [["r1", "r2"], ["r3", "r4"]]
    assert run.assessment.review_reliability < run.deterministic_analysis.reliability
    assert run.assessment.confidence == 0.86
    assert run.embedding_response.request_id == "embed-req-1"
    assert run.provider_response.request_id == "llm-req-1"
    assert run.embedding_response.response_model == "fixture-embedding-v1"
    assert run.provider_response.response_model == "fixture-chat-v1"
    assert run.prompt_version and run.pipeline_version and run.schema_version
    assert len(run.input_sha256) == 64


def test_semantic_clustering_is_transitive_and_reproducible():
    records = [
        ReviewEvidence(evidence_id="a", text="a"),
        ReviewEvidence(evidence_id="b", text="b"),
        ReviewEvidence(evidence_id="c", text="c"),
    ]
    vectors = [(1, 0), (0.95, 0.31), (0.81, 0.59)]
    first = cluster_near_duplicates(records, vectors, threshold=0.88)
    second = cluster_near_duplicates(records, vectors, threshold=0.88)
    assert first == second
    assert first[0].evidence_ids == ["a", "b", "c"]


def test_unknown_llm_evidence_id_is_rejected():
    output = {
        "schema_version": SEMANTIC_REVIEW_SCHEMA_VERSION,
        "language": "vi",
        "findings": [{
            "category": "QUALITY",
            "severity": "LOW",
            "statement_vi": "Không hợp lệ.",
            "evidence_ids": ["invented-review"],
            "confidence": 0.5,
        }],
        "confidence": 0.5,
    }
    with pytest.raises(ValueError, match="unknown review evidence IDs"):
        interpret_reviews(
            reviews_fixture(),
            aggregate_review_count=8,
            embedding_provider=FakeEmbeddings(),
            embedding_model="fixture-embed",
            provider=FakeLLM(output),
            model="fixture-chat",
        )


def test_model_contract_rejects_supplier_risk_score():
    output = {
        "schema_version": SEMANTIC_REVIEW_SCHEMA_VERSION,
        "language": "vi",
        "findings": [],
        "confidence": 0.5,
        "risk_score": 90,
    }
    with pytest.raises(ValueError, match="failed the review interpretation schema"):
        interpret_reviews(
            reviews_fixture(),
            aggregate_review_count=8,
            embedding_provider=FakeEmbeddings(),
            embedding_model="fixture-embed",
            provider=FakeLLM(output),
            model="fixture-chat",
        )


def test_yescale_embeddings_adapter_uses_endpoint_and_preserves_provenance():
    captured = {}

    def handler(request: httpx.Request):
        captured["request"] = request
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"X-YEScale-Request-Id": "embed-live-1"},
            json={
                "model": "embedding-model-v1",
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ],
                "usage": {"prompt_tokens": 12, "total_tokens": 12, "cost": "0.0001"},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = YEScaleProvider("secret-key", client=client, clock=lambda: 1.0)
        result = provider.embed_texts(
            model="embedding-candidate",
            texts=["first", "second"],
            metadata={"feature": "review_embeddings", "session_id": "analysis-1"},
        )
    assert str(captured["request"].url) == "https://api.yescale.io/v1/embeddings"
    assert captured["request"].headers["authorization"] == "Bearer secret-key"
    assert captured["body"] == {
        "model": "embedding-candidate",
        "input": ["first", "second"],
        "encoding_format": "float",
    }
    assert result.vectors == ((1.0, 0.0), (0.0, 1.0))
    assert result.request_id == "embed-live-1"
    assert result.usage.total_tokens == 12
    assert result.usage.cost_usd == Decimal("0.0001")


@pytest.mark.parametrize("payload", [
    {"model": "x", "data": [{"index": 0, "embedding": [1, 0]}]},
    {"model": "x", "data": [
        {"index": 0, "embedding": ["NaN", 0]},
        {"index": 1, "embedding": [0, 1]},
    ]},
])
def test_yescale_embeddings_fail_closed_on_malformed_vectors(payload):
    with httpx.Client(transport=httpx.MockTransport(
        lambda _request: httpx.Response(200, json=payload)
    )) as client:
        provider = YEScaleProvider("secret", client=client)
        with pytest.raises(ProviderError):
            provider.embed_texts(model="x", texts=["one", "two"])


def test_semantic_input_requires_nonempty_reviews():
    with pytest.raises(ValueError, match="at least one review"):
        interpret_reviews(
            [],
            aggregate_review_count=None,
            embedding_provider=FakeEmbeddings(),
            embedding_model="fixture-embed",
            provider=FakeLLM(),
            model="fixture-chat",
        )
