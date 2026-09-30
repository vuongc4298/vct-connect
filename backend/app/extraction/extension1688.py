"""Normalize a small, user-provided selection of rendered 1688 offer text."""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .contracts import CONTRACT_VERSION, EVIDENCE_FIELDS
from .urls import normalize_1688_url, offer_id

MAX_CAPTURE_BYTES = 16_384
EXTRACTOR_VERSION = "1688-extension-dom.v1"


class DomFields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    supplier_name: str | None = Field(default=None, max_length=240)
    product_title: str | None = Field(default=None, max_length=500)
    price_text: str | None = Field(default=None, max_length=160)
    company_location: str | None = Field(default=None, max_length=160)
    review_count: int | None = Field(default=None, ge=0, le=1_000_000_000)

    @field_validator("supplier_name", "product_title", "price_text", "company_location")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if any(ord(character) < 32 and character not in "\t\n" for character in value):
            raise ValueError("Control characters are not allowed")
        return " ".join(value.split()) or None


class DomCapture(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_url: str = Field(max_length=2048)
    canonical_url: str | None = Field(default=None, max_length=2048)
    offer_id: str = Field(pattern=r"^[0-9]{6,20}$")
    fields: DomFields


def normalize_capture(capture: DomCapture) -> dict:
    source_url = normalize_1688_url(capture.source_url)
    if capture.offer_id != offer_id(source_url):
        raise ValueError("Offer ID does not match the active offer URL")
    if capture.canonical_url is not None:
        if normalize_1688_url(capture.canonical_url) != source_url:
            raise ValueError("Canonical URL does not match the active offer URL")

    fields = capture.fields.model_dump(exclude_none=True)
    if not fields.get("supplier_name") and not fields.get("product_title"):
        return {"source_url": source_url, "extraction_status": "PARSE_FAILED",
                "reason": "NO_SELECTED_EVIDENCE"}

    evidence = {key: None for key in EVIDENCE_FIELDS}
    evidence["supplier_name"] = fields.get("supplier_name")
    if fields.get("product_title"):
        evidence["products"] = [{"offer_id": capture.offer_id, "title": fields["product_title"]}]
    if fields.get("price_text"):
        evidence["price_information"] = {"display_text": fields["price_text"]}
    if fields.get("company_location"):
        evidence["company_information"] = {"location": fields["company_location"]}
    if "review_count" in fields:
        evidence["transaction_signals"] = {"review_count": fields["review_count"]}

    missing = [key for key in EVIDENCE_FIELDS if evidence[key] is None]
    timestamp = datetime.now(timezone.utc).isoformat()
    supplier_data = {
        "contract_version": CONTRACT_VERSION,
        "platform": "1688",
        "source_url": source_url,
        "offer_id": capture.offer_id,
        "platform_supplier_id": None,
        "extracted_at": timestamp,
        "extraction_method": "EXTENSION_DOM",
        "analysis_mode": "EXTENSION_ENHANCED",
        "extractor_version": EXTRACTOR_VERSION,
        "completeness": round((len(EVIDENCE_FIELDS) - len(missing)) / len(EVIDENCE_FIELDS), 4),
        "completeness_denominator": list(EVIDENCE_FIELDS),
        "missing_fields": missing,
        **evidence,
    }
    return {
        "source_url": source_url,
        "extraction_status": "PARTIAL" if missing else "SUCCESS",
        "supplier_data": supplier_data,
        "raw_payload": {"source_url": source_url, "captured_at": timestamp,
                        "provenance": "USER_PROVIDED_BROWSER_EVIDENCE",
                        "selected_fields": fields},
        "reviews": [],
    }
