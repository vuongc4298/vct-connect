"""Shared, versioned evidence contract for platform adapters.

Coverage counts the 12 optional SupplierData evidence fields from the MVP spec.
Platform-specific offer identifiers remain provenance, outside the denominator.
"""

from collections.abc import Callable, Mapping
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


def evidence_present(value: object) -> bool:
    """The v1 evidence rule: numeric zero is present; None/empty text/list aren't."""
    return value is not None and value != "" and value != []


def extension_evidence_present(value: object) -> bool:
    """Legacy extension captures and merges count every non-None value."""
    return value is not None


def evidence_coverage(evidence: Mapping[str, object], *,
                      present: Callable[[object], bool] = evidence_present) -> dict:
    """Return v1 coverage in contract order, excluding provenance fields."""
    missing = [name for name in EVIDENCE_FIELDS if not present(evidence[name])]
    return {
        "completeness": round((len(EVIDENCE_FIELDS) - len(missing)) / len(EVIDENCE_FIELDS), 4),
        "completeness_denominator": list(EVIDENCE_FIELDS),
        "missing_fields": missing,
    }


def assemble_supplier_data(evidence: Mapping[str, object], *,
                           present: Callable[[object], bool] = evidence_present, **provenance) -> dict:
    """Attach the shared contract and coverage to adapter-selected evidence."""
    return {"contract_version": CONTRACT_VERSION, **provenance,
            **evidence_coverage(evidence, present=present), **evidence}


def evidence_status(data: Mapping[str, object]) -> Literal["PARTIAL", "SUCCESS"]:
    return "PARTIAL" if data["missing_fields"] else "SUCCESS"


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
