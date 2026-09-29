"""Shared, versioned evidence contract for platform adapters.

Coverage counts the 12 optional SupplierData evidence fields from the MVP spec.
Platform-specific offer identifiers remain provenance, outside the denominator.
"""

from typing import Literal, TypedDict


CONTRACT_VERSION = "supplierdata.v1"
EVIDENCE_FIELDS = (
    "supplier_name", "company_information", "years_active", "categories",
    "certifications", "products", "price_information", "transaction_signals",
    "rating", "reviews", "delivery_information", "activity_history",
)
ExtractionStatus = Literal[
    "SUCCESS", "PARTIAL", "AUTH_REQUIRED", "BLOCKED", "UNSUPPORTED_PAGE",
    "TIMEOUT", "PARSE_FAILED",
]


class Review(TypedDict):
    text: str
    source_url: str


class SupplierData(TypedDict):
    contract_version: Literal["supplierdata.v1"]
    platform: Literal["1688", "TAOBAO", "ALIBABA"]
    source_url: str
    offer_id: str | None
    extracted_at: str
    extraction_method: str
    analysis_mode: str
    extractor_version: str
    completeness: float
    completeness_denominator: list[str]
    missing_fields: list[str]
    platform_supplier_id: str | None
    supplier_name: str | None
    company_information: dict | None
    years_active: int | None
    categories: list[str] | None
    certifications: list[str] | None
    products: list[dict] | None
    price_information: dict | None
    transaction_signals: dict | None
    rating: float | None
    reviews: list[Review] | None
    delivery_information: dict | None
    activity_history: list[dict] | None


class ExtractionOutcome(TypedDict):
    source_url: str
    extraction_status: ExtractionStatus
