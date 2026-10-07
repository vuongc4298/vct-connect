"""Deterministic report.v1 projection from persisted assessment evidence."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from .contracts import ReportEvidence, ReportFinding, ReportPayload, ReportRisk


_RISK_TYPES = {"SUPPLIER_RISK", "REVIEW_FINDING", "REVIEW_PATTERN"}
_POSITIVE_TYPES = {"SUPPLIER_POSITIVE"}


def _as_dict(value: object) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list:
    return list(value) if isinstance(value, list) else []


def _finding_evidence_ids(finding: Mapping[str, object]) -> list[str]:
    payload = _as_dict(finding.get("payload"))
    kind = str(finding.get("finding_type") or "")
    ids: list[str] = []

    if kind.startswith("REVIEW_"):
        raw = payload.get("evidence_ids")
        if isinstance(raw, list):
            ids.extend(str(item) for item in raw if isinstance(item, str) and item)
    elif kind == "MEDIA_CONSISTENCY":
        media_id = payload.get("media_id")
        review_id = payload.get("review_evidence_id")
        if isinstance(media_id, str) and media_id:
            ids.append("media:" + media_id)
        if isinstance(review_id, str) and review_id:
            ids.append(review_id)
    elif kind == "IDENTITY_ASSESSMENT":
        for item in _as_list(payload.get("supporting_evidence")):
            if isinstance(item, Mapping):
                evidence_id = item.get("evidence_id")
                if isinstance(evidence_id, str) and evidence_id:
                    ids.append(evidence_id)
    elif kind.startswith("SUPPLIER_"):
        raw = payload.get("evidence_fields")
        if isinstance(raw, list):
            ids.extend(
                "supplier:" + item
                for item in raw
                if isinstance(item, str) and item
            )

    return list(dict.fromkeys(ids))


def _report_finding(row: Mapping[str, object]) -> ReportFinding:
    severity = row.get("severity")
    confidence = row.get("confidence")
    return ReportFinding(
        finding_key=str(row["finding_key"]),
        finding_type=str(row["finding_type"]),
        dimension=str(row["dimension"]) if row.get("dimension") is not None else None,
        severity=float(severity) if severity is not None else None,
        confidence=float(confidence) if confidence is not None else None,
        evidence_ids=_finding_evidence_ids(row),
        payload=_as_dict(row.get("payload")),
    )


def _material_risk(finding: ReportFinding) -> bool:
    if finding.finding_type in _RISK_TYPES:
        return True
    if finding.finding_type == "IDENTITY_ASSESSMENT":
        return finding.severity is not None
    if finding.finding_type == "MEDIA_CONSISTENCY":
        return finding.payload.get("consistency") == "CONTRADICTS"
    return False


def _review_summary(review_analysis: Mapping[str, object]) -> dict:
    mode = review_analysis.get("mode")
    assessment = _as_dict(review_analysis.get("assessment"))
    if mode == "semantic":
        return {
            "mode": "semantic",
            "confidence": assessment.get("confidence"),
            "review_reliability": assessment.get("review_reliability"),
            "findings": assessment.get("findings", []),
            "suspicious_patterns": assessment.get("suspicious_patterns", []),
        }
    return {
        "mode": "deterministic",
        "review_count": assessment.get("review_count"),
        "aggregate_review_count": assessment.get("aggregate_review_count"),
        "reliability": assessment.get("reliability"),
        "complaint_topics": assessment.get("complaint_topics", []),
        "suspicious_patterns": assessment.get("suspicious_patterns", []),
        "missing_inputs": assessment.get("missing_inputs", []),
    }


def _limitations(
    *,
    risk: Mapping[str, object],
    snapshot: Mapping[str, object],
    identity: Mapping[str, object],
    review_analysis: Mapping[str, object],
) -> list[str]:
    result = [
        "Báo cáo phản ánh bằng chứng đã thu thập tại thời điểm phân tích; dữ liệu nguồn có thể thay đổi sau đó.",
        "Kết quả là công cụ hỗ trợ thẩm định và không thay thế việc xác minh pháp nhân, mẫu hàng, điều khoản giao dịch và thanh toán.",
    ]
    if risk.get("label") == "INSUFFICIENT_INFORMATION":
        result.insert(
            0,
            "Thông tin hiện có chưa đủ để đưa ra mức rủi ro đáng tin cậy; không được diễn giải trạng thái này thành rủi ro thấp.",
        )
    if _as_list(snapshot.get("missing_fields")):
        result.append(
            "Một số trường dữ liệu nguồn không khả dụng và được giữ là chưa biết thay vì giả định an toàn."
        )
    if _as_list(identity.get("uncertainty_reasons")):
        result.append(
            "Nhận định nhà máy/thương mại còn có yếu tố chưa chắc chắn; cần xác minh bằng tài liệu độc lập."
        )
    if review_analysis.get("mode") != "semantic":
        result.append(
            "Phân tích đánh giá hiện chỉ dùng các tín hiệu xác định được từ dữ liệu đã thu thập; chưa có diễn giải ngữ nghĩa đầy đủ cho lần chạy này."
        )
    return result


def _recommended_actions(
    *,
    risk: Mapping[str, object],
    identity: Mapping[str, object],
) -> list[str]:
    actions = [
        "Xác minh tên pháp nhân, giấy phép kinh doanh và tài khoản nhận tiền trước khi đặt cọc.",
        "Yêu cầu mẫu hoặc lô thử và xác nhận tiêu chí chất lượng bằng văn bản trước khi đặt đơn lớn.",
        "Chốt bằng văn bản các điều khoản giao hàng, đổi trả, hoàn tiền và xử lý hàng lỗi.",
    ]
    missing = set(
        item for item in _as_list(risk.get("missing_dimensions")) if isinstance(item, str)
    )
    if risk.get("label") == "INSUFFICIENT_INFORMATION" or missing:
        actions.append(
            "Bổ sung bằng chứng cho các hạng mục còn thiếu trước khi dùng báo cáo để ra quyết định đặt hàng."
        )
    if "DELIVERY" in missing:
        actions.append(
            "Yêu cầu lịch sản xuất, thời gian giao dự kiến và bằng chứng giao hàng gần đây."
        )
    if "AFTER_SALES" in missing:
        actions.append(
            "Xác nhận đầu mối hậu mãi và quy trình khiếu nại/đổi trả trước khi thanh toán."
        )
    if _as_list(identity.get("uncertainty_reasons")):
        actions.append(
            "Yêu cầu bằng chứng độc lập về năng lực sản xuất, địa chỉ cơ sở và vai trò nhà máy/thương mại."
        )
    return list(dict.fromkeys(actions))


def build_report(
    *,
    analysis_id: object,
    source_url: str,
    snapshot: Mapping[str, object],
    assessment: Mapping[str, object],
    findings: Sequence[Mapping[str, object]],
    evidence: Sequence[Mapping[str, object]],
    raw_reviews: Sequence[Mapping[str, object]],
) -> ReportPayload:
    risk = _as_dict(assessment.get("risk_assessment"))
    supplier_interpretation = _as_dict(assessment.get("supplier_interpretation"))
    identity = _as_dict(assessment.get("identity_assessment"))
    review_analysis = _as_dict(assessment.get("review_analysis"))

    normalized = _as_dict(snapshot.get("normalized_data"))
    report_findings = [_report_finding(row) for row in findings]

    evidence_by_id: dict[str, ReportEvidence] = {}
    for row in evidence:
        evidence_id = str(row["evidence_id"])
        evidence_by_id[evidence_id] = ReportEvidence(
            evidence_id=evidence_id,
            source_kind=str(row["source_kind"]),
            source_field=(
                str(row["source_field"])
                if row.get("source_field") is not None
                else None
            ),
            payload=_as_dict(row.get("payload")),
        )
    for ordinal, review in enumerate(raw_reviews):
        evidence_id = f"review:{ordinal}"
        evidence_by_id.setdefault(
            evidence_id,
            ReportEvidence(
                evidence_id=evidence_id,
                source_kind="REVIEW",
                source_field="reviews",
                payload=_as_dict(review.get("payload") if isinstance(review, Mapping) else {}),
            ),
        )

    key_risks = [item for item in report_findings if _material_risk(item)]
    positives = [
        item for item in report_findings if item.finding_type in _POSITIVE_TYPES
    ]
    used = {item.finding_key for item in key_risks + positives}
    other = [item for item in report_findings if item.finding_key not in used]

    return ReportPayload(
        analysis_id=str(analysis_id),
        source_url=source_url,
        platform=str(normalized.get("platform") or "UNKNOWN"),
        extracted_at=str(normalized.get("extracted_at") or ""),
        supplier_name=(
            str(normalized["supplier_name"])
            if normalized.get("supplier_name") is not None
            else None
        ),
        platform_supplier_id=(
            str(normalized["platform_supplier_id"])
            if normalized.get("platform_supplier_id") is not None
            else None
        ),
        supplier_summary_vi=str(
            supplier_interpretation.get("summary_vi")
            or "Chưa có tóm tắt nhà cung cấp có căn cứ."
        ),
        risk=ReportRisk(
            overall_risk=(
                float(risk["overall_risk"])
                if risk.get("overall_risk") is not None
                else None
            ),
            label=str(risk.get("label") or "INSUFFICIENT_INFORMATION"),
            confidence=float(risk.get("confidence") or 0.0),
            coverage=float(risk.get("data_coverage") or 0.0),
            scoring_version=str(
                risk.get("scoring_version")
                or assessment.get("scoring_version")
                or "unknown"
            ),
            dimensions=_as_list(risk.get("dimensions")),
        ),
        factory_trader=identity,
        review_summary=_review_summary(review_analysis),
        key_risks=key_risks,
        positive_signals=positives,
        other_findings=other,
        evidence=[evidence_by_id[key] for key in sorted(evidence_by_id)],
        missing_data={
            "source_fields": [
                str(item)
                for item in _as_list(snapshot.get("missing_fields"))
                if isinstance(item, str)
            ],
            "risk_dimensions": [
                str(item)
                for item in _as_list(risk.get("missing_dimensions"))
                if isinstance(item, str)
            ],
            "uncertainties_vi": [
                str(item.get("statement_vi"))
                for item in _as_list(supplier_interpretation.get("uncertainties"))
                if isinstance(item, Mapping) and item.get("statement_vi")
            ],
        },
        limitations_vi=_limitations(
            risk=risk,
            snapshot=snapshot,
            identity=identity,
            review_analysis=review_analysis,
        ),
        recommended_actions_vi=_recommended_actions(
            risk=risk,
            identity=identity,
        ),
    )
