from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


REPORT_SCHEMA_VERSION = "report.v1"
GUEST_PREVIEW_SCHEMA_VERSION = "guest-preview.v1"


class ReportEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=240)
    source_kind: str = Field(min_length=1, max_length=80)
    source_field: str | None = Field(default=None, max_length=160)
    payload: dict


class ReportFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_key: str = Field(min_length=1, max_length=400)
    finding_type: str = Field(min_length=1, max_length=80)
    dimension: str | None = Field(default=None, max_length=80)
    severity: float | None = Field(default=None, ge=0, le=100)
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_ids: list[str]
    payload: dict


class ReportRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_risk: float | None = Field(default=None, ge=0, le=100)
    label: Literal["LOW", "MODERATE", "HIGH", "INSUFFICIENT_INFORMATION"]
    confidence: float = Field(ge=0, le=1)
    coverage: float = Field(ge=0, le=1)
    scoring_version: str = Field(min_length=1, max_length=80)
    dimensions: list[dict]


class ReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["report.v1"] = REPORT_SCHEMA_VERSION
    language: Literal["vi"] = "vi"
    analysis_id: str = Field(min_length=1, max_length=80)
    source_url: str = Field(min_length=1, max_length=2048)
    platform: str = Field(min_length=1, max_length=40)
    extracted_at: str = Field(min_length=1, max_length=80)
    supplier_name: str | None = Field(default=None, max_length=500)
    platform_supplier_id: str | None = Field(default=None, max_length=300)
    supplier_summary_vi: str = Field(min_length=1, max_length=4000)
    risk: ReportRisk
    factory_trader: dict
    review_summary: dict
    key_risks: list[ReportFinding]
    positive_signals: list[ReportFinding]
    other_findings: list[ReportFinding]
    evidence: list[ReportEvidence]
    missing_data: dict[str, list[str]]
    limitations_vi: list[str]
    recommended_actions_vi: list[str]


class GuestPreviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["guest-preview.v1"] = GUEST_PREVIEW_SCHEMA_VERSION
    language: Literal["vi"] = "vi"
    analysis_id: str = Field(min_length=1, max_length=80)
    platform: str = Field(min_length=1, max_length=40)
    supplier_name: str | None = Field(default=None, max_length=500)
    extracted_at: str = Field(min_length=1, max_length=80)
    confidence: float = Field(ge=0, le=1)
    coverage: float = Field(ge=0, le=1)
    information_state: Literal["INSUFFICIENT_INFORMATION", "LIMITED_PREVIEW"]
    missing_source_fields: list[str]
    missing_risk_dimensions: list[str]
    uncertainties_vi: list[str]
    limitations_vi: list[str]
    registration_required: Literal[True] = True
