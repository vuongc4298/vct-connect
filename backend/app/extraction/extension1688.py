"""Normalize a small, user-provided selection of rendered 1688 offer text."""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import EVIDENCE_FIELDS, assemble_supplier_data, evidence_status, extension_evidence_present
from .evidence import MalformedPage, validate_json_evidence
from .extensiontaobao import SelectedText
from .urls import normalize_1688_url, offer_id

MAX_CAPTURE_BYTES = 16_384
EXTRACTOR_VERSION = "1688-extension-dom.v2"


class NamedValue(BaseModel):
    """A selected visible label and its value, never an embedded source object."""

    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=240)

    @field_validator("name", "value")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Selected labels and values must not be empty")
        return cleaned


class DomFields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    supplier_name: str | None = Field(default=None, max_length=240)
    product_title: str | None = Field(default=None, max_length=500)
    price_text: str | None = Field(default=None, max_length=160)
    company_location: str | None = Field(default=None, max_length=160)
    review_count: int | None = Field(default=None, ge=0, le=1_000_000_000)
    supplier_tenure: str | None = Field(default=None, max_length=160)
    main_business: str | None = Field(default=None, max_length=160)
    supplier_metrics: list[NamedValue] = Field(default_factory=list, max_length=10)
    product_attributes: list[NamedValue] = Field(default_factory=list, max_length=50)
    price_details: str | None = Field(default=None, max_length=1200)
    sku_options: list[NamedValue] = Field(default_factory=list, max_length=20)
    shipping_details: list[NamedValue] = Field(default_factory=list, max_length=10)
    consign_metrics: list[NamedValue] = Field(default_factory=list, max_length=10)
    review_summary: str | None = Field(default=None, max_length=160)
    rating: float | None = Field(default=None, ge=0, le=5)
    reviews: list[SelectedText] = Field(default_factory=list, max_length=20)

    @model_validator(mode="before")
    @classmethod
    def safe_selected_text(cls, value):
        # Validate before whitespace cleanup so a forbidden control cannot disappear.
        def visit(item):
            if isinstance(item, str):
                if any(ord(character) < 32 and character not in "\t\n" for character in item):
                    raise ValueError("Control characters are not allowed")
            elif isinstance(item, dict):
                for key, child in item.items():
                    visit(key)
                    visit(child)
            elif isinstance(item, list):
                for child in item:
                    visit(child)
        visit(value)
        try:
            validate_json_evidence(value)
        except MalformedPage as exc:
            raise ValueError("Invalid selected evidence text") from exc
        return value

    @field_validator("supplier_name", "product_title", "price_text", "company_location",
                     "supplier_tenure", "main_business", "price_details", "review_summary")
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
    try:
        validate_json_evidence(capture.model_dump())
    except MalformedPage as exc:
        raise ValueError("Invalid selected evidence text") from exc
    source_url = normalize_1688_url(capture.source_url)
    if capture.offer_id != offer_id(source_url):
        raise ValueError("Offer ID does not match the active offer URL")
    if capture.canonical_url is not None:
        if normalize_1688_url(capture.canonical_url) != source_url:
            raise ValueError("Canonical URL does not match the active offer URL")

    fields = {key: value for key, value in capture.fields.model_dump(exclude_none=True).items()
              if value != []}
    if not fields.get("supplier_name") and not fields.get("product_title"):
        return {"source_url": source_url, "extraction_status": "PARSE_FAILED",
                "reason": "NO_SELECTED_EVIDENCE"}

    evidence = {key: None for key in EVIDENCE_FIELDS}
    evidence["supplier_name"] = fields.get("supplier_name")
    def pairs(name):
        selected = []
        for item in fields.get(name, []):
            if item not in selected:
                selected.append(item)
        return selected

    if fields.get("product_title"):
        product = {"offer_id": capture.offer_id, "title": fields["product_title"]}
        for key in ("product_attributes", "sku_options"):
            if pairs(key):
                product["attributes" if key == "product_attributes" else key] = pairs(key)
        evidence["products"] = [product]
    price = fields.get("price_details") or fields.get("price_text")
    if price:
        evidence["price_information"] = {"display_text": price}
    company = {}
    if fields.get("company_location"):
        company["location"] = fields["company_location"]
    if fields.get("supplier_tenure"):
        company["platform_tenure_display_text"] = fields["supplier_tenure"]
    if fields.get("main_business"):
        company["main_business"] = fields["main_business"]
        evidence["categories"] = [fields["main_business"]]
    evidence["company_information"] = company or None
    transaction = {}
    if "review_count" in fields:
        transaction["review_count"] = fields["review_count"]
    if fields.get("review_summary"):
        transaction["review_count_display_text"] = fields["review_summary"]
    metrics = [{"label": item["name"], "value": item["value"], "scope": scope}
               for key, scope in (("supplier_metrics", "SUPPLIER_PLATFORM"),
                                  ("consign_metrics", "CONSIGN_DROPSHIPPING"))
               for item in pairs(key)]
    if metrics:
        transaction["source_metrics"] = metrics
    evidence["transaction_signals"] = transaction or None
    if "rating" in fields:
        evidence["rating"] = fields["rating"]
    shipping = pairs("shipping_details")
    if shipping:
        evidence["delivery_information"] = {"source_metrics": [
            {"label": item["name"], "value": item["value"], "scope": "PRODUCT_SHIPPING"}
            for item in shipping]}
    reviews = [{"text": review["text"].strip(), "source_url": source_url}
               for review in fields.get("reviews", []) if review["text"].strip()]
    evidence["reviews"] = reviews or None

    timestamp = datetime.now(timezone.utc).isoformat()
    supplier_data = assemble_supplier_data(
        evidence, present=extension_evidence_present,
        platform="1688", source_url=source_url, offer_id=capture.offer_id,
        platform_supplier_id=None, extracted_at=timestamp, extraction_method="EXTENSION_DOM",
        analysis_mode="EXTENSION_ENHANCED", extractor_version=EXTRACTOR_VERSION,
    )
    return {
        "source_url": source_url,
        "extraction_status": evidence_status(supplier_data),
        "supplier_data": supplier_data,
        "raw_payload": {"source_url": source_url, "captured_at": timestamp,
                        "provenance": "USER_PROVIDED_BROWSER_EVIDENCE",
                        "selected_fields": fields},
        "reviews": reviews,
    }
