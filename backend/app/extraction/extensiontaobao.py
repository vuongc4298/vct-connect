"""Strict selected visible Taobao evidence; no source models or session state."""
from datetime import datetime, timezone
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import EVIDENCE_FIELDS, assemble_supplier_data, evidence_status, extension_evidence_present
from .evidence import MalformedPage, validate_json_evidence as _validate_json_evidence
from .urls import normalize_taobao_url, taobao_identity


class SelectedText(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(max_length=2000)
    original_length: int = Field(ge=0, le=2_000_000)

    @model_validator(mode="after")
    def extent(self):
        if self.original_length < len(self.text):
            raise ValueError("Invalid selected text extent")
        return self


class Product(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_url: str = Field(max_length=2048)
    title: str | None = Field(default=None, max_length=500)


class TaobaoFields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    supplier_name: str | None = Field(default=None, max_length=240)
    product_title: str | None = Field(default=None, max_length=500)
    reviews: list[SelectedText] = Field(default_factory=list, max_length=20)
    shop_metrics: list[str] = Field(default_factory=list, max_length=10)
    products: list[Product] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def bounded_metrics(self):
        if any(len(value) > 240 for value in self.shop_metrics):
            raise ValueError("Metric exceeds selection limit")
        return self


class TaobaoCapture(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_url: str = Field(max_length=2048)
    canonical_url: str | None = Field(default=None, max_length=2048)
    source_kind: Literal["item", "shop"]
    source_id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    fields: TaobaoFields


def normalize_taobao_capture(capture: TaobaoCapture) -> dict:
    try:
        _validate_json_evidence(capture.model_dump())
    except MalformedPage as exc:
        raise ValueError("Invalid selected evidence text") from exc
    source = normalize_taobao_url(capture.source_url)
    identity = taobao_identity(source)
    if identity != (capture.source_kind, capture.source_id):
        raise ValueError("Selected source identity does not match the active page")
    if capture.canonical_url is not None and taobao_identity(capture.canonical_url) != identity:
        raise ValueError("Canonical URL does not match the active page")
    fields = capture.fields
    if capture.source_kind == "shop" and (fields.product_title or fields.reviews or fields.shop_metrics):
        raise ValueError("Unaudited shop fields")
    if capture.source_kind == "item" and fields.products:
        raise ValueError("Product collections require a shop page")
    evidence = dict.fromkeys(EVIDENCE_FIELDS)
    evidence["supplier_name"] = (fields.supplier_name or "").strip() or None
    title = (fields.product_title or "").strip()
    products = [{"offer_id": capture.source_id, "title": title}] if title else []
    for product in fields.products:
        url = normalize_taobao_url(product.source_url)
        kind, item_id = taobao_identity(url)
        if kind != "item":
            raise ValueError("Shop product link must identify a Taobao item")
        if all(value["offer_id"] != item_id for value in products):
            products.append({"offer_id": item_id, "title": (product.title or "").strip() or None, "source_url": url})
    evidence["products"] = products or None
    reviews = [{"text": review.text.strip(), "source_url": source} for review in fields.reviews if review.text.strip()]
    evidence["reviews"] = reviews or None
    metrics = [value.strip() for value in fields.shop_metrics if value.strip()]
    evidence["transaction_signals"] = {"shop_metrics_display_text": metrics} if metrics else None
    shipping = [value for value in metrics if re.fullmatch(r"平均[0-9]+小时发货", value)]
    evidence["delivery_information"] = {"shop_shipping_display_text": shipping} if shipping else None
    if not evidence["supplier_name"] and not evidence["products"]:
        return dict(source_url=source, extraction_status="PARSE_FAILED", reason="NO_SELECTED_EVIDENCE")
    timestamp = datetime.now(timezone.utc).isoformat()
    data = assemble_supplier_data(evidence, present=extension_evidence_present, platform="TAOBAO", source_url=source,
                offer_id=capture.source_id if capture.source_kind == "item" else None,
                platform_supplier_id=None, extracted_at=timestamp, extraction_method="EXTENSION_DOM",
                analysis_mode="EXTENSION_ENHANCED", extractor_version="taobao-extension-dom.v1")
    return dict(source_url=source, extraction_status=evidence_status(data), supplier_data=data,
                raw_payload=dict(source_url=source, captured_at=timestamp, provenance="USER_PROVIDED_BROWSER_EVIDENCE",
                                 selected_fields=fields.model_dump(exclude_none=True)), reviews=reviews)
