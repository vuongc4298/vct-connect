"""Versioned contracts for supplier evidence interpretation.

The model interprets supplied evidence and categorical concerns; deterministic
policy owns numeric severity and the overall Risk/Confidence/Coverage assessment.
"""
from __future__ import annotations

from typing import Literal
import json

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.extraction.contracts import EVIDENCE_FIELDS
from .scoring import RiskDimension


SCHEMA_VERSION = "supplier-interpretation.v1"
PROMPT_VERSION = "supplier-interpretation.prompt.v3"
PIPELINE_VERSION = "analysis-intelligence.v0.2"
_ALLOWED_EVIDENCE_FIELDS = frozenset(EVIDENCE_FIELDS)


class EvidenceSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement_vi: str = Field(min_length=1, max_length=800)
    evidence_fields: list[str] = Field(default_factory=list, max_length=len(EVIDENCE_FIELDS))
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_quotes: dict[str, str] = Field(default_factory=dict, max_length=12)

    @field_validator("evidence_quotes", mode="before")
    @classmethod
    def canonical_quotes(cls, value):
        if not isinstance(value, dict):
            return value
        normalized = {}
        for key, quote in value.items():
            field = key.split(".", 1)[0] if isinstance(key, str) else key
            if field not in _ALLOWED_EVIDENCE_FIELDS:
                raise ValueError("quotes contain unsupported SupplierData fields")
            text = json.dumps(quote, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if isinstance(quote, dict) else quote
            if not isinstance(text, str) or not text.strip() or len(text) > 400:
                raise ValueError("source quotes must contain 1-400 characters")
            if field in normalized and normalized[field] != text:
                raise ValueError("conflicting quotes for the same canonical field")
            normalized[field] = text
        return normalized

    @field_validator("evidence_fields")
    @classmethod
    def canonical_evidence_fields(cls, value: list[str]) -> list[str]:
        # Providers sometimes cite a concrete nested metric. Persist its canonical
        # SupplierData parent; scoring still requires an exact quote of that fact.
        value = [item.split(".", 1)[0] for item in value]
        if len(value) != len(set(value)):
            raise ValueError("evidence_fields must not contain duplicates")
        unknown = [item for item in value if item not in _ALLOWED_EVIDENCE_FIELDS]
        if unknown:
            raise ValueError("evidence_fields contains unsupported SupplierData fields")
        return value


class SupplierDimensionAssessment(EvidenceSignal):
    """A categorical interpretation, not a model-generated numeric risk score."""

    dimension: RiskDimension
    severity: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]
    evidence_quotes: dict[str, str] = Field(default_factory=dict, max_length=12,
        description="Exact source quotes keyed by evidence field. Quotes are required to score; omitted quotes leave the category unknown.")

    @model_validator(mode="after")
    def supported_category_has_quotes(self):
        # Discard uncited context and unused quotes rather than adding references.
        # The scoring boundary still verifies each retained quote against source.
        self.evidence_fields = [field for field in self.evidence_fields if field in self.evidence_quotes]
        self.evidence_quotes = {field: self.evidence_quotes[field] for field in self.evidence_fields}
        if not self.evidence_fields:
            # Unsupported categories remain unknown; never fail the entire
            # report just because the model omitted a category's source quote.
            self.severity = "UNKNOWN"
        return self

class SupplierInterpretation(BaseModel):
    """Grounded Vietnamese interpretation of one SupplierData snapshot."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    language: Literal["vi"] = "vi"
    summary_vi: str = Field(min_length=1, max_length=1800)
    positive_signals: list[EvidenceSignal] = Field(default_factory=list, max_length=8)
    risk_signals: list[EvidenceSignal] = Field(default_factory=list, max_length=8)
    uncertainties: list[EvidenceSignal] = Field(default_factory=list, max_length=8)
    recommended_verifications: list[str] = Field(default_factory=list, max_length=8,
        description="Plain Vietnamese action strings, never objects.")
    confidence: float = Field(ge=0.0, le=1.0)
    # Additive: archived v1 interpretations without these records remain readable.
    dimension_assessments: list[SupplierDimensionAssessment] = Field(default_factory=list, max_length=7)

    @field_validator("dimension_assessments")
    @classmethod
    def unique_dimensions(cls, value: list[SupplierDimensionAssessment]) -> list[SupplierDimensionAssessment]:
        if len({item.dimension for item in value}) != len(value):
            raise ValueError("dimension assessments must not repeat a dimension")
        return value

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

