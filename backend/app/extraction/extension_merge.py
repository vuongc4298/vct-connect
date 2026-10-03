"""Merge selected browser evidence with an owner's same-page snapshot.

The prior snapshot stays immutable. This module only works with normalized
SupplierData and keeps a reference to the original raw evidence.
"""

import copy
from datetime import datetime
import re

from .contracts import EVIDENCE_FIELDS, evidence_coverage, evidence_status, extension_evidence_present
from .urls import normalize_source_url


MERGE_VERSION = "extension-merge.v1"
MAX_MERGED_ITEMS = 20  # Match the per-platform parser and extension selection limits.
_SECRET = re.compile(
    r"(?i)(?:\b(?:password|passwd|cookie|set-cookie|access[_-]?token|"
    r"refresh[_-]?token|session[_-]?(?:id|key|token)|session|sid|auth|"
    r"csrf|xsrf|csrftoken|jwt|token|jsessionid|asp\.net_sessionid|"
    r"phpsessid|_m_h5_tk|_tb_token_|x5sec)\b\s*[:=]|"
    r"\bbearer\s+[a-z0-9._~+/-]{8,})"
)
_COOKIE_PAIR = re.compile(r"(?i)\b[a-z0-9_.-]{2,64}=[^;\s]+;\s*[a-z0-9_.-]{2,64}=")


def reject_sensitive_page_state(value: object) -> None:
    """Reject credential-shaped content even inside otherwise allowed text."""
    if isinstance(value, str):
        if _SECRET.search(value) or _COOKIE_PAIR.search(value):
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


def _deduplicate(old: list[dict], new: list[dict], key_function) -> tuple[list[dict], int]:
    result: list[dict] = []
    positions: dict[str, int] = {}
    for item in old + new:
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
    # The active page wins when the combined evidence exceeds the same bound
    # used by each adapter. Older unique items fill the remaining slots.
    current_keys = {key_function(item) for item in new}
    ordered = [item for item in result if key_function(item) in current_keys]
    ordered.extend(item for item in result if key_function(item) not in current_keys)
    return ordered[:MAX_MERGED_ITEMS], max(len(ordered) - MAX_MERGED_ITEMS, 0)


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
    previous_raw = previous.get("raw_payload") or {}
    prior_field_sources = previous_raw.get("field_sources") or {}
    prior_dict_sources = previous_raw.get("dict_key_sources") or {}
    prior_item_sources = previous_raw.get("item_sources") or {}
    source_snapshots = copy.deepcopy(previous_raw.get("source_snapshots") or {})
    source_snapshots[baseline] = {"extracted_at": prior["extracted_at"],
                                  "extraction_method": prior["extraction_method"]}
    dict_key_sources: dict[str, dict[str, list[str]]] = {}
    item_sources: dict[str, dict[str, list[str]]] = {}
    omitted: dict[str, int] = {}

    def inherited_sources(field: str, *, detail: str | None = None, kind: str | None = None) -> list[str]:
        granular = (prior_dict_sources if kind == "dict" else prior_item_sources).get(field, {})
        labels = granular.get(detail) if detail is not None and isinstance(granular, dict) else None
        if not isinstance(labels, list):
            labels = prior_field_sources.get(field)
        if not isinstance(labels, list):
            labels = [f"snapshot:{baseline}"]
        resolved = [f"snapshot:{baseline}" if label == "EXTENSION_DOM" else label
                    for label in labels if isinstance(label, str)]
        resolved = [label if label.startswith("snapshot:") and label[9:] in source_snapshots
                    else f"snapshot:{baseline}" for label in resolved]
        return list(dict.fromkeys(resolved))

    for field in EVIDENCE_FIELDS:
        old, new = prior.get(field), current.get(field)
        if field in {"reviews", "products"}:
            identity = _review_key if field == "reviews" else _product_key
            value, omitted[field] = _deduplicate(old or [], new or [], identity)
            merged[field] = value or None
            item_sources[field] = {}
            for item in value:
                key = identity(item)
                old_item = next((candidate for candidate in old or [] if identity(candidate) == key), None)
                new_item = next((candidate for candidate in new or [] if identity(candidate) == key), None)
                old_contributes = old_item is not None and (new_item is None or any(
                    name not in new_item or new_item[name] is None for name in old_item
                ))
                labels = (inherited_sources(field, detail=key, kind="item") if old_contributes else []) + (
                    ["EXTENSION_DOM"] if new_item is not None else []
                )
                item_sources[field][key] = list(dict.fromkeys(labels))
            field_sources[field] = list(dict.fromkeys(
                label for labels in item_sources[field].values() for label in labels
            ))
        elif isinstance(old, dict) or isinstance(new, dict):
            previous_dict, current_dict = old or {}, new or {}
            merged[field] = {**copy.deepcopy(previous_dict), **copy.deepcopy(current_dict)}
            dict_key_sources[field] = {}
            for key in merged[field]:
                dict_key_sources[field][key] = (["EXTENSION_DOM"] if key in current_dict else
                                                inherited_sources(field, detail=key, kind="dict"))
            field_sources[field] = list(dict.fromkeys(
                label for labels in dict_key_sources[field].values() for label in labels
            ))
        else:
            merged[field] = copy.deepcopy(new if new is not None else old)
            if merged[field] is not None:
                field_sources[field] = ["EXTENSION_DOM"] if new is not None else inherited_sources(field)
    merged["platform_supplier_id"] = prior.get("platform_supplier_id") or current.get("platform_supplier_id")
    merged["extractor_version"] = MERGE_VERSION
    merged.update(evidence_coverage(merged, present=extension_evidence_present))
    raw = copy.deepcopy(capture["raw_payload"])
    raw["merged_from_snapshot_id"] = baseline
    used_ids = {label.removeprefix("snapshot:") for labels in field_sources.values()
                for label in labels if label.startswith("snapshot:")}
    if not used_ids:
        standalone = copy.deepcopy(capture)
        for field in ("reviews", "products"):
            standalone["supplier_data"][field] = copy.deepcopy(merged[field])
        standalone["reviews"] = copy.deepcopy(merged["reviews"] or [])
        return standalone
    raw["source_snapshots"] = {key: value for key, value in source_snapshots.items() if key in used_ids}
    if raw["source_snapshots"]:
        earliest = min(raw["source_snapshots"].values(),
                       key=lambda item: datetime.fromisoformat(item["extracted_at"]))
        raw["merged_from_extracted_at"] = earliest["extracted_at"]
        raw["merged_from_extraction_method"] = earliest["extraction_method"]
    raw["omitted_review_count"] = omitted.get("reviews", 0)
    raw["omitted_product_count"] = omitted.get("products", 0)
    raw["field_sources"] = field_sources
    raw["dict_key_sources"] = dict_key_sources
    raw["item_sources"] = item_sources
    return {**capture, "extraction_status": evidence_status(merged),
            "supplier_data": merged, "raw_payload": raw,
            "reviews": copy.deepcopy(merged["reviews"] or [])}
