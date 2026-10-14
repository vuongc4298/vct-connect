"""Identity-bound public Alibaba product/store/company-overview browser capture."""
from datetime import datetime, timezone
from collections import Counter
from hashlib import sha256
import json
import re
from urllib.parse import urlsplit

from .browser_html import validated_snapshot
from .contracts import EVIDENCE_FIELDS, assemble_supplier_data, evidence_status, evidence_coverage
from .dom import active
from .extension_merge import _merge_review_cards
from .page_context import collect_context, select_context
from .urls import normalize_alibaba_url, alibaba_identity

CLAIM_KEYS = {
    "Business type": "business_type", "Country / Region": "location", "Main Products": "main_products_display_text",
    "Total employees": "employee_count_display_text", "Total Annual Revenue": "annual_revenue_display_text",
    "Year established": "established_year_display_text", "Main Markets": "markets_display_text",
    "Factory Size": "factory_area_display_text", "Factory Country/Region": "factory_location_display_text",
    "No. of Production Lines": "production_line_count_display_text", "Contract Manufacturing": "processing_methods_display_text",
    "Annual Output Value": "annual_output_display_text", "Average Lead Time": "lead_time_display_text",
    "Accepted Delivery Terms": "delivery_terms_display_text", "Accepted Payment Currency": "payment_currency_display_text",
    "Accepted payment methods": "payment_methods_display_text",
}


def alibaba_company_url(value, *, profile=False):
    if not isinstance(value, str) or len(value) > 2048 or re.search(r"[\s\\#]", value):
        raise ValueError("Invalid Alibaba supplier identity")
    p = urlsplit(value)
    host = re.fullmatch(r"([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.(?:m\.)?en\.alibaba\.com", p.netloc)
    if p.scheme != "https" or p.username or p.password or not host or p.path not in {"/", "/index.html", "/company_profile.html"}:
        raise ValueError("Invalid Alibaba supplier identity")
    if profile and p.path != "/company_profile.html":
        raise ValueError("Open this supplier's Company overview")
    return f"https://{host[1]}.en.alibaba.com/" + ("company_profile.html" if profile else "")


def normalize_company_claims(claims, at):
    company = {CLAIM_KEYS[k]: v for k, v in claims.items()}
    company["company_profile_claims"] = claims
    for label, field in (("No. of Production Lines", "production_line_count"), ("Total employees", "employee_count")):
        value = claims.get(label, "")
        if re.fullmatch(r"[1-9][0-9]{0,8}", value):
            company[field] = int(value)
    year = claims.get("Year established")
    if year:
        if not re.fullmatch(r"(?:19|20)[0-9]{2}", year) or int(year) > at.year:
            raise ValueError("Invalid company establishment year")
        company["age_basis"] = "Platform-displayed establishment year; exact date and completed operating years are unknown"
    return company


def normalize_alibaba_bundle(bundle, *, at=None):
    at = at or datetime.now(timezone.utc)
    source = normalize_alibaba_url(bundle.product.source_url)
    kind, identity = alibaba_identity(source)
    if kind != "product" or bundle.product.offer_id != identity:
        raise ValueError("Alibaba product identity does not match")
    if bundle.product.canonical_url and normalize_alibaba_url(bundle.product.canonical_url) != source:
        raise ValueError("Alibaba canonical conflicts")
    shop = alibaba_company_url(bundle.shop_url) if bundle.shop_url else None
    if bundle.shop_url and bundle.shop_url != shop:
        raise ValueError("Store URL must be canonical")
    profile = shop + "company_profile.html" if shop else None
    if bundle.shop:
        if not shop or bundle.shop.source_url != shop or bundle.shop.credit_url or not bundle.shop.company_name:
            raise ValueError("Alibaba shop does not match product supplier")
        if bundle.shop.factory_url and bundle.shop.factory_url != profile:
            raise ValueError("Alibaba Company overview belongs to another supplier")
    if bundle.factory:
        if (not shop or bundle.factory.source_url != profile or bundle.factory.canonical_url != profile
                or bundle.factory.shop_url != shop or not bundle.factory.company_name):
            raise ValueError("Alibaba company profile identity does not match supplier")
        if not bundle.shop and not bundle.guided:
            raise ValueError("Company overview must follow product supplier")
        if bundle.shop and bundle.shop.company_name != bundle.factory.company_name:
            raise ValueError("Company overview name conflicts with shop")
    fields = bundle.product.fields.model_dump(exclude_none=True)
    if not fields.get("product_title"):
        raise ValueError("No visible Alibaba product evidence")
    name = fields.get("supplier_name")
    linked_name = bundle.shop.company_name if bundle.shop else bundle.factory.company_name if bundle.factory else None
    if name and linked_name and name != linked_name:
        raise ValueError("Supplier company name conflicts with product")
    evidence = dict.fromkeys(EVIDENCE_FIELDS)
    evidence["supplier_name"] = name or linked_name
    evidence["products"] = [{"offer_id": identity, "title": fields["product_title"], "source_url": source,
                              **({"attributes": fields["product_attributes"]} if fields.get("product_attributes") else {})}]
    price = fields.get("price_details") or fields.get("price_text")
    if price:
        evidence["price_information"] = {"display_text": price}
        minimum = re.search(r"\b([0-9][0-9,]*)\s*-\s*[0-9,]+\s+pieces\b", price)
        if minimum:
            evidence["price_information"]["minimum_order_quantity"] = int(minimum[1].replace(",", ""))
    evidence["rating"] = fields.get("rating")
    if "review_count" in fields:
        evidence["transaction_signals"] = {"review_count": fields["review_count"], "review_scope": "PRODUCT"}
    reviews = [{"text": item["text"], "source_url": source} for item in fields.get("reviews", [])]
    evidence["reviews"] = reviews or None
    evidence["company_information"] = {"shop_source_url": shop} if shop else None
    if fields.get("supplier_tenure"):
        evidence["company_information"] = {**(evidence["company_information"] or {}), "platform_tenure_display_text": fields["supplier_tenure"]}
    if fields.get("supplier_metrics"):
        metrics = [{"label": pair["name"], "value": pair["value"], "scope": "SUPPLIER_PLATFORM"} for pair in fields["supplier_metrics"] if pair["name"] != "Business type"]
        data_type = next((pair["value"] for pair in fields["supplier_metrics"] if pair["name"] == "Business type"), None)
        if data_type:
            evidence["company_information"] = {**(evidence["company_information"] or {}), "business_type": data_type}
        if metrics:
            evidence["transaction_signals"] = {**(evidence["transaction_signals"] or {}), "source_metrics": metrics}
    claims = {}
    if bundle.factory:
        for item in bundle.factory.claims:
            if item.name not in CLAIM_KEYS or item.name in claims and claims[item.name] != item.value or item.value == "-":
                raise ValueError("Unsupported or conflicting Alibaba company claim")
            claims[item.name] = item.value
        if not claims:
            raise ValueError("No visible company claims")
        evidence["company_information"].update(normalize_company_claims(claims, at), company_profile_source_url=profile)
        if bundle.factory.description:
            evidence["company_information"]["company_profile_description_display_text"] = bundle.factory.description
    timestamp = at.isoformat()
    data = assemble_supplier_data(evidence, platform="ALIBABA", source_url=source, offer_id=identity,
             platform_supplier_id=urlsplit(shop).netloc if shop else None, extracted_at=timestamp,
             extraction_method="EXTENSION_DOM", analysis_mode="EXTENSION_ENHANCED", extractor_version="alibaba-linked-browser-bundle.v1")
    expected_urls = {"PRODUCT": source, "SHOP": shop, "FACTORY": profile}
    required = {"PRODUCT"} | ({"SHOP"} if bundle.shop else set()) | ({"FACTORY"} if bundle.factory else set())
    if not any(s.page == "PRODUCT" for s in bundle.html_sources):
        raise ValueError("Alibaba collection requires its captured product HTML")
    if any(item.page not in required or item.source_url != expected_urls[item.page] for item in bundle.html_sources):
        raise ValueError("Alibaba HTML source is not linked to this collection")
    # The linked page identities must also appear inside their independently validated snapshots.
    if bundle.shop and not any(s.page == "SHOP" for s in bundle.html_sources) or bundle.factory and not any(s.page == "FACTORY" for s in bundle.html_sources):
        raise ValueError("Linked Alibaba company evidence requires captured HTML")
    records, context = [], []
    for item in bundle.html_sources:
        parsed, encoded = validated_snapshot(item.html, item.source_url, platform="ALIBABA", allowed_urls=set(expected_urls.values()) - {None})
        def text(selector, maximum=1600):
            matches = parsed.css(selector)
            if len(matches) > 1:
                raise ValueError("Ambiguous Alibaba capture region")
            node = matches[0] if matches else None
            return " ".join(node.text(separator=" ").split())[:maximum] if node and active(node) else None
        if item.page == "PRODUCT":
            if text("#vct-alibaba-title", 500) != fields["product_title"]:
                raise ValueError("Product HTML conflicts with selected title")
            links = parsed.css("#vct-alibaba-shop-link[href]")
            if shop and (len(links) != 1 or links[0].attributes.get("href") != shop):
                raise ValueError("Product HTML shop link conflicts")
            supplier_text = text("#vct-alibaba-supplier", 2000) or ""
            if name and name not in supplier_text or any(pair["value"] not in supplier_text for pair in fields.get("supplier_metrics", [])):
                raise ValueError("Product HTML supplier facts conflict")
            html_price = text("#vct-alibaba-price", 1200)
            if price and html_price != price:
                raise ValueError("Product HTML price conflicts")
            summary = text("#vct-alibaba-review-summary", 180) or ""
            rating = re.match(r"([0-5](?:\.[0-9]+)?)\b", summary)
            count = re.search(r"Based on ([0-9,]+) reviews", summary, re.I)
            if ("rating" in fields and (not rating or float(rating[1]) != fields["rating"])) or (
                "review_count" in fields and (not count or int(count[1].replace(",", "")) != fields["review_count"])):
                raise ValueError("Product HTML review totals conflict")
            protection = text("#vct-alibaba-policy", 1800)
            if protection:
                data["products"][0]["services_display_text"] = protection
                data["products"][0]["services_scope"] = "Platform-advertised Alibaba order protection; eligibility and fulfillment remain unverified"
            bodies = [{"text": " ".join(n.text().split())[:2000], "source_url": source} for n in parsed.css("#vct-review-bodies .review-item")[:20] if n.text().strip()]
            selected_bodies = Counter(" ".join(item["text"].split()) for item in reviews)
            if selected_bodies - Counter(item["text"] for item in bodies):
                raise ValueError("Product HTML review bodies conflict")
            html_attrs = []
            for row in parsed.css("#vct-alibaba-attributes dl"):
                labels, values = row.css("dt"), row.css("dd")
                if len(labels) != 1 or len(values) != 1:
                    raise ValueError("Malformed product label/value")
                html_attrs.append({"name": " ".join(labels[0].text().split()), "value": " ".join(values[0].text().split())})
            if any(pair not in html_attrs for pair in fields.get("product_attributes", [])):
                raise ValueError("Product HTML attributes conflict")
            if bodies:
                data["reviews"], _ = _merge_review_cards(data["reviews"] or [], bodies)
        else:
            selected_name = bundle.shop.company_name if item.page == "SHOP" else bundle.factory.company_name
            if text("#vct-alibaba-company-name", 240) != selected_name:
                raise ValueError("Company HTML name conflicts")
            backlinks = parsed.css("#vct-alibaba-own-shop[href]")
            if len(backlinks) != 1 or backlinks[0].attributes.get("href") != shop:
                raise ValueError("Company HTML supplier identity conflicts")
            company = data["company_information"]
            company["company_name"] = selected_name
            introduction = text("#vct-alibaba-introduction")
            if introduction:
                company["shop_introduction_display_text" if item.page == "SHOP" else "company_profile_description_display_text"] = introduction
            if item.page == "SHOP":
                details = text("#vct-alibaba-shop-claims")
                if details:
                    company["shop_header_claims_display_text"] = details
            else:
                captured_claims = {}
                for row in parsed.css("#vct-alibaba-company-claims dl"):
                    labels, values = row.css("dt"), row.css("dd")
                    if len(labels) != 1 or len(values) != 1:
                        raise ValueError("Malformed company label/value")
                    key, value = (" ".join(n.text().split()) for n in (labels[0], values[0]))
                    if key not in CLAIM_KEYS or key in captured_claims and captured_claims[key] != value:
                        raise ValueError("Conflicting company HTML claim")
                    captured_claims[key] = value
                if captured_claims != claims:
                    raise ValueError("Company HTML claims conflict with selected evidence")
                if claims.get("Main Products"):
                    data["categories"] = [claims["Main Products"]]
                terms = {key: claims[label] for label, key in (("Accepted Delivery Terms", "delivery_terms_display_text"),
                         ("Accepted Payment Currency", "payment_currency_display_text"), ("Accepted payment methods", "payment_methods_display_text")) if claims.get(label)}
                if terms:
                    data["price_information"] = {**(data["price_information"] or {}), **terms, "terms_source_url": profile}
        digest = sha256(encoded).hexdigest()
        records.append({"page": item.page, "source_url": item.source_url, "html_sha256": digest,
                        "html_bytes": len(encoded), "status": "PARSED", "provenance": "SANITIZED_RENDERED_BROWSER_HTML",
                        "content_scope": "COMPANY_OVERVIEW" if item.page == "FACTORY" else "PRODUCT" if item.page == "PRODUCT" else "SUPPLIER_STOREFRONT"})
        context.extend(collect_context(parsed, item.page, item.source_url, digest))
    captured = {s.page for s in bundle.html_sources}
    for page in sorted(required - captured):
        records.append({"page": page, "source_url": expected_urls[page], "status": "NOT_CAPTURED", "provenance": "SANITIZED_RENDERED_BROWSER_HTML"})
    if bundle.outcomes:
        states = {x.page: x.status for x in bundle.outcomes}
        if set(states) != {"SHOP", "FACTORY"} or any((states[page] == "OK") != bool(selection) for page, selection in (("SHOP", bundle.shop), ("FACTORY", bundle.factory))):
            raise ValueError("Alibaba collection outcomes conflict")
        data["collection_status"] = bundle.model_dump(mode="json")["outcomes"]
    data.update(evidence_coverage(data))
    data["html_capture_status"] = records
    html_review_count = len(data["reviews"] or [])
    while data["reviews"] and len(json.dumps(data, ensure_ascii=False).encode()) > 47_000:
        data["reviews"].pop()
    if len(data["reviews"] or []) < html_review_count:
        if not data["reviews"]:
            data["reviews"] = None
        data["review_capture_limit"] = {"captured_count": html_review_count, "retained_count": len(data["reviews"] or []),
                                        "reason": "Assessment input byte budget; source review total is unchanged"}
        for record in records:
            if record["page"] == "PRODUCT":
                record["status"] = "BUDGET_LIMIT"
        data.update(evidence_coverage(data))
    remaining = 48_000 - len(json.dumps(data, ensure_ascii=False).encode()) - 32
    if remaining < 0:
        raise ValueError("Normalized Alibaba evidence exceeds assessment budget")
    packet = select_context(context, max_bytes=min(12_000, remaining))
    if packet["sections"]:
        data["page_context"] = packet
    return {"source_url": source, "supplier_data": data, "reviews": data["reviews"] or [], "extraction_status": evidence_status(data),
            "raw_payload": {"source_url": source, "captured_at": timestamp, "provenance": "USER_PROVIDED_BROWSER_EVIDENCE",
              "selected_fields": fields, "linked_collection": bundle.model_dump(mode="json", exclude={"product", "job_id", "html_sources"}), "html_sources": records}}
