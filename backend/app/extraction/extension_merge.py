"""Merge selected browser evidence with an owner's same-page snapshot.

The prior snapshot stays immutable. This module only works with normalized
SupplierData and keeps a reference to the original raw evidence.
"""

import copy
import re

from .contracts import EVIDENCE_FIELDS
from .urls import normalize_source_url


MERGE_VERSION = "extension-merge.v1"
_SECRET = re.compile(
    r"(?i)(?:\b(?:password|passwd|cookie|set-cookie|access[_-]?token|"
    r"refresh[_-]?token|session[_-]?(?:id|key|token))\b\s*[:=]|"
    r"\bbearer\s+[a-z0-9._~+/-]{8,})"
)


def reject_sensitive_page_state(value: object) -> None:
    """Reject credential-shaped content even inside otherwise allowed text."""
    if isinstance(value, str):
        if _SECRET.search(value):
            raise ValueError("Selected evidence contains sensitive page state")
    elif isinstance(value, dict):
        for key, child in value.items():
            reject_sensitive_page_state(key)
            reject_sensitive_page_state(child)
    elif isinstance(value, list):
        for child in value:
            reject_sensitive_page_state(child)


def _review_key(review: dict) -> str:
    return " ".join(str(review.get("text") or "").split()).casefold()


def _product_key(product: dict) -> str:
    return str(product.get("offer_id") or product.get("source_url") or "").casefold()


def _deduplicate(items: list[dict], key_function) -> list[dict]:
    result: list[dict] = []
    positions: dict[str, int] = {}
    for item in items:
        key = key_function(item)
        if not key:
            if item not in result:
                result.append(copy.deepcopy(item))
        elif key in positions:
            # Preserve richer historical metadata; refresh only selected values.
            position = positions[key]
            result[position].update({k: copy.deepcopy(v) for k, v in item.items() if v is not None})
        else:
            positions[key] = len(result)
            result.append(copy.deepcopy(item))
    return result


def merge_extension_evidence(capture: dict, previous: dict) -> dict:
    """Return a new capture payload combining one eligible prior snapshot."""
    current = capture["supplier_data"]
    prior = previous["supplier_data"]
    source = current["source_url"]
    if (normalize_source_url(source) != source
            or normalize_source_url(prior["source_url"]) != source
            or current["platform"] != prior["platform"]
            or current.get("offer_id") != prior.get("offer_id")):
        raise ValueError("Cannot merge evidence from a different page")
    merged = copy.deepcopy(current)
    field_sources: dict[str, list[str]] = {}
    baseline = str(previous["supplier_snapshot_id"])
    for field in EVIDENCE_FIELDS:
        old, new = prior.get(field), current.get(field)
        if field == "reviews":
            value = _deduplicate((old or []) + (new or []), _review_key)
            merged[field] = value or None
        elif field == "products":
            value = _deduplicate((old or []) + (new or []), _product_key)
            merged[field] = value or None
        elif isinstance(old, dict) and isinstance(new, dict):
            merged[field] = {**copy.deepcopy(old), **copy.deepcopy(new)}
        else:
            merged[field] = copy.deepcopy(new if new is not None else old)
        if old is not None or new is not None:
            combines = field in {"reviews", "products"} or isinstance(old, dict) and isinstance(new, dict)
            field_sources[field] = ([f"snapshot:{baseline}"] if old is not None and (new is None or combines) else []) + (
                ["EXTENSION_DOM"] if new is not None else []
            )
    merged["platform_supplier_id"] = prior.get("platform_supplier_id") or current.get("platform_supplier_id")
    merged["extractor_version"] = MERGE_VERSION
    missing = [field for field in EVIDENCE_FIELDS if merged[field] is None]
    merged["missing_fields"] = missing
    merged["completeness_denominator"] = list(EVIDENCE_FIELDS)
    merged["completeness"] = round((len(EVIDENCE_FIELDS) - len(missing)) / len(EVIDENCE_FIELDS), 4)
    raw = copy.deepcopy(capture["raw_payload"])
    raw["merged_from_snapshot_id"] = baseline
    raw["merged_from_extracted_at"] = prior["extracted_at"]
    raw["merged_from_extraction_method"] = prior["extraction_method"]
    raw["field_sources"] = field_sources
    return {**capture, "extraction_status": "PARTIAL" if missing else "SUCCESS",
            "supplier_data": merged, "raw_payload": raw,
            "reviews": copy.deepcopy(merged["reviews"] or [])}
