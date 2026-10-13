"""Strict selected browser evidence for one linked 1688 collection."""
from datetime import datetime, timezone
import json
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .contracts import evidence_coverage, evidence_status
from .extension1688 import DomCapture, NamedValue, normalize_capture
from .extension_merge import reject_sensitive_page_state
from .evidence import validate_json_evidence
from .browser_html import enrich_browser_html, MAX_HTML_BUNDLE_BYTES
from .shop1688_identity import shop_identity
from .factory1688_identity import factory_identity
from .factory_claims import FACTORY_FIELDS, normalize_factory_claims

MAX_BUNDLE_BYTES = 32_768


class ShopSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_url: str = Field(max_length=2048)
    credit_url: str | None = Field(default=None, max_length=2048)
    company_name: str | None = Field(default=None, min_length=1, max_length=240)
    factory_url: str | None = Field(default=None, max_length=2048)


class FactorySelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_url: str = Field(max_length=2048)
    canonical_url: str = Field(max_length=2048)
    shop_url: str = Field(max_length=2048)
    claims: list[NamedValue] = Field(max_length=32)
    description: str | None = Field(default=None, max_length=1000)


class CollectionOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    page: str = Field(pattern=r"^(SHOP|FACTORY)$")
    status: str = Field(pattern=r"^(OK|NO_PERMISSION|LINK_UNAVAILABLE|UNAVAILABLE|TIMEOUT)$")


class SupplierBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: UUID
    product: DomCapture
    shop_url: str | None = Field(default=None, max_length=2048)
    shop: ShopSelection | None = None
    factory: FactorySelection | None = None
    outcomes: list[CollectionOutcome] = Field(default_factory=list, max_length=2)
    html_sources: list["HtmlSource"] = Field(default_factory=list, max_length=3)
    html_capture_requested: bool = Field(default=False, strict=True)
    guided: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def unique_outcomes(self):
        if len({x.page for x in self.outcomes}) != len(self.outcomes):
            raise ValueError("Duplicate collection outcome")
        if len({x.page for x in self.html_sources}) != len(self.html_sources):
            raise ValueError("Duplicate HTML source")
        return self


class HtmlSource(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    page: str = Field(pattern=r"^(PRODUCT|SHOP|FACTORY)$")
    source_url: str = Field(max_length=2048)
    html: str = Field(min_length=1, max_length=2_000_000)


SupplierBundle.model_rebuild()


def normalize_bundle(bundle: SupplierBundle, *, at=None):
    selected_bytes = json.dumps(bundle.model_dump(mode="json", exclude={"html_sources"}), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(selected_bytes) > MAX_BUNDLE_BYTES:
        raise ValueError("Selected evidence exceeds 32 KB independently of HTML")
    validate_json_evidence(bundle.model_dump(mode="json"))
    reject_sensitive_page_state(bundle.model_dump(mode="json"))
    at = at or datetime.now(timezone.utc)
    result = normalize_capture(bundle.product)
    if result["extraction_status"] not in {"SUCCESS", "PARTIAL"}:
        raise ValueError("Collect a usable product before starting analysis")
    expected_shop = shop_identity(bundle.shop_url) if bundle.shop_url else None
    if bundle.shop:
        if not expected_shop or shop_identity(bundle.shop.source_url) != expected_shop:
            raise ValueError("Shop does not match product supplier link")
        if bundle.shop.credit_url is not None and bundle.shop.credit_url != expected_shop + "page/creditdetail.html":
            raise ValueError("Shop's own company identity is unavailable")
        if bundle.shop.credit_url is None and (not bundle.shop.company_name or not bundle.shop.company_name.strip()
                or not any(source.page == "SHOP" for source in bundle.html_sources)):
            raise ValueError("Header-only shop requires its company name and captured HTML")
        if bundle.shop.factory_url:
            factory_identity(bundle.shop.factory_url)
    if bundle.factory:
        if (not bundle.shop or not bundle.shop.factory_url) and not (bundle.guided and expected_shop and not bundle.shop):
            raise ValueError("Factory must be linked from collected shop or user-opened company profile")
        profile = factory_identity(bundle.factory.source_url)
        if ((bundle.shop and factory_identity(bundle.shop.factory_url) != profile) or
                bundle.factory.canonical_url != profile or
                shop_identity(bundle.factory.shop_url) != expected_shop):
            raise ValueError("Factory identity does not match supplier shop")
        data = result["supplier_data"]
        claims = {}
        permitted = FACTORY_FIELDS
        for item in bundle.factory.claims:
            if item.name not in permitted:
                raise ValueError("Unsupported factory field")
            if item.name in claims and claims[item.name] != item.value:
                raise ValueError("Conflicting factory field")
            claims[item.name] = item.value
        if not claims:
            raise ValueError("No factory claims collected")
        company = data.get("company_information") or {}
        company.update(shop_source_url=expected_shop, factory_profile_source_url=profile,
                       factory_profile_claims_display_text="; ".join(f"{k}: {v}" for k, v in claims.items()))
        company.update(normalize_factory_claims(claims))
        if bundle.factory.description:
            company["factory_description_display_text"] = bundle.factory.description
        if claims.get("成立时间"):
            founded = datetime.strptime(claims["成立时间"], "%Y.%m.%d").date()
            if founded > at.date():
                raise ValueError("Future factory establishment date")
            data["years_active"] = at.year - founded.year - ((at.month, at.day) < (founded.month, founded.day))
            company.update(established_date_claim=founded.isoformat(),
                           age_basis="Completed years since platform-displayed establishment date; not independently verified")
        data["company_information"] = company
        data.update(evidence_coverage(data))
        result["extraction_status"] = evidence_status(data)
    data = result["supplier_data"]
    if bundle.outcomes:
        states = {x.page: x.status for x in bundle.outcomes}
        if set(states) != {"SHOP", "FACTORY"} or any(
                (states[page] == "OK") != bool(selection)
                for page, selection in (("SHOP", bundle.shop), ("FACTORY", bundle.factory))):
            raise ValueError("Collection outcomes do not match selected pages")
        data["collection_status"] = bundle.model_dump(mode="json")["outcomes"]
    data["extractor_version"] = "1688-linked-browser-bundle.v2" if bundle.html_sources or bundle.html_capture_requested else "1688-linked-browser-bundle.v1"
    result["raw_payload"]["linked_collection"] = bundle.model_dump(mode="json", exclude={"product", "job_id", "html_sources"})
    if bundle.html_sources or bundle.html_capture_requested:
        if any((source.page == "SHOP" and not bundle.shop) or (source.page == "FACTORY" and not bundle.factory)
               for source in bundle.html_sources):
            raise ValueError("HTML requires an accessible linked source")
        result = enrich_browser_html(result, bundle.html_sources, shop_url=expected_shop,
                                     factory_url=factory_identity(bundle.factory.source_url) if bundle.factory else None,
                                     shop_company_name=bundle.shop.company_name if bundle.shop else None,
                                     accessible_pages={"PRODUCT"} | ({"SHOP"} if bundle.shop else set()) | ({"FACTORY"} if bundle.factory else set()))
    if len(json.dumps(result["supplier_data"], ensure_ascii=False).encode("utf-8")) > 48_000:
        raise ValueError("Normalized evidence exceeds the assessment input budget")
    return result
