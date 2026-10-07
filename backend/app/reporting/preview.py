from __future__ import annotations

from typing import Mapping

from .contracts import GuestPreviewPayload

def build_guest_preview(report: Mapping[str, object]) -> GuestPreviewPayload:
    risk = report.get("risk") if isinstance(report.get("risk"), Mapping) else {}
    missing = report.get("missing_data") if isinstance(report.get("missing_data"), Mapping) else {}
    limitations = report.get("limitations_vi") if isinstance(report.get("limitations_vi"), list) else []
    return GuestPreviewPayload(
        analysis_id=str(report.get("analysis_id") or ""),
        platform=str(report.get("platform") or "UNKNOWN"),
        supplier_name=str(report["supplier_name"]) if report.get("supplier_name") is not None else None,
        extracted_at=str(report.get("extracted_at") or ""),
        confidence=float(risk.get("confidence") or 0.0),
        coverage=float(risk.get("coverage") or 0.0),
        information_state="INSUFFICIENT_INFORMATION" if risk.get("label") == "INSUFFICIENT_INFORMATION" else "LIMITED_PREVIEW",
        missing_source_fields=[str(x) for x in missing.get("source_fields", []) if isinstance(x, str)],
        missing_risk_dimensions=[str(x) for x in missing.get("risk_dimensions", []) if isinstance(x, str)],
        uncertainties_vi=[str(x) for x in missing.get("uncertainties_vi", []) if isinstance(x, str)],
        limitations_vi=[str(x) for x in limitations if isinstance(x, str)],
    )
