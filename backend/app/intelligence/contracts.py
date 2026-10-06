"""Versioned contracts for supplier evidence interpretation.

Story 3.1 deliberately stops before deterministic risk scoring. The model may
interpret supplied evidence and uncertainty, but it must not produce the
product's overall Risk/Confidence/Coverage assessment.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.extraction.contracts import EVIDENCE_FIELDS


SCHEMA_VERSION = "supplier-interpretation.v1"
PROMPT_VERSION = "supplier-interpretation.prompt.v1"
PIPELINE_VERSION = "analysis-intelligence.v0.1"
_ALLOWED_EVIDENCE_FIELDS = frozenset(EVIDENCE_FIELDS)


class EvidenceSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement_vi: str = Field(min_length=1, max_length=800)
    evidence_fields: list[str] = Field(default_factory=list, max_length=len(EVIDENCE_FIELDS))
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("evidence_fields")
    @classmethod
    def canonical_evidence_fields(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("evidence_fields must not contain duplicates")
        unknown = [item for item in value if item not in _ALLOWED_EVIDENCE_FIELDS]
        if unknown:
            raise ValueError("evidence_fields contains unsupported SupplierData fields")
        return value


class SupplierInterpretation(BaseModel):
    """Grounded Vietnamese interpretation of one SupplierData snapshot."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    language: Literal["vi"] = "vi"
    summary_vi: str = Field(min_length=1, max_length=1800)
    positive_signals: list[EvidenceSignal] = Field(default_factory=list, max_length=8)
    risk_signals: list[EvidenceSignal] = Field(default_factory=list, max_length=8)
    uncertainties: list[EvidenceSignal] = Field(default_factory=list, max_length=8)
    recommended_verifications: list[str] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("recommended_verifications")
    @classmethod
    def bounded_actions(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            item = item.strip()
            if not item or len(item) > 600:
                raise ValueError("recommended_verifications entries must be 1-600 characters")
            normalized.append(item)
        if len(normalized) != len(set(normalized)):
            raise ValueError("recommended_verifications must not contain duplicates")
        return normalized

