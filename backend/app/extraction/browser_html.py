"""Parse sanitized rendered HTML without executing scripts or fetching assets."""
import copy
from hashlib import sha256
import json
from urllib.parse import urlsplit
from .dom import tree, active
from .extension_merge import reject_sensitive_page_state, _merge_review_cards
from .contracts import evidence_coverage, evidence_status

MAX_HTML_BYTES = 2_000_000
MAX_HTML_BUNDLE_BYTES = 8_000_000


def enrich_browser_html(result, sources, *, shop_url=None, factory_url=None, accessible_pages=None, shop_company_name=None):
    result = copy.deepcopy(result)
    data = result["supplier_data"]
    records = []
    for source in sources:
        page, url, html = source.page, source.source_url, source.html
        encoded = html.encode("utf-8")
        if len(encoded) > MAX_HTML_BYTES:
            raise ValueError("HTML source exceeds 2 MB")
        expected = {"PRODUCT": result["source_url"], "SHOP": shop_url, "FACTORY": factory_url}[page]
        if not expected or url != expected:
            raise ValueError("HTML source is not linked to this collection")
        parsed = tree(html)
        # HTML is data only. The browser and backend independently reject private state.
        if parsed.css("script,style,iframe,form,input,textarea,select,button,object,embed,svg,img,video,audio,source,canvas,template,noscript"):
            raise ValueError("HTML snapshot contains forbidden source state")
        nodes = parsed.css("*")
        if len(nodes) > 30_000: raise ValueError("HTML snapshot has too many elements")
        for node in nodes:
            if any(key not in {"id", "class", "href", "rel", "charset"} for key in node.attributes):
                raise ValueError("HTML snapshot contains unsupported attributes")
            href = node.attributes.get("href")
            if href:
                p = urlsplit(href)
                if p.scheme != "https" or p.username or p.password or p.port or not (p.hostname == "1688.com" or (p.hostname or "").endswith(".1688.com")):
                    raise ValueError("HTML snapshot contains an unsafe link")
        canonicals = parsed.css('link[rel="canonical"]')
        if len(canonicals) != 1 or canonicals[0].attributes.get("href") != url:
            raise ValueError("HTML canonical identity conflicts")
        reject_sensitive_page_state(parsed.text())

        def text(node, limit=800):
            return " ".join(node.text(separator=" ").split())[:limit] if node and active(node) else None

        before = copy.deepcopy(data)
        content_scope = None
        if page == "PRODUCT":
            links = {n.attributes["href"] for n in parsed.css("#shopNavigation a.shop-company-name[href]")}
            if shop_url and links != {shop_url}:
                raise ValueError("HTML product shop identity conflicts")
            products = data.get("products") or []
            if products:
                product = products[0]
                for selector, key in (("#description", "description_display_text"), ("#productPackInfo", "packaging_display_text"),
                                      ("#sizeChart", "size_chart_display_text"), ("#productWarning", "warning_display_text"),
                                      ("#officialInspection", "inspection_display_text"), ("#mainServices", "services_display_text")):
                    value = text(parsed.css_first(selector))
                    if value: product[key] = value
                attributes = product.setdefault("attributes", [])
                for label in parsed.css("#productAttributes th.ant-descriptions-item-label")[:100]:
                    value_node = label.next
                    if value_node and "ant-descriptions-item-content" in value_node.attributes.get("class", "").split():
                        name, value = text(label, 80), text(value_node, 240)
                        pair = {"name": name, "value": value}
                        if name and value and pair not in attributes and len(attributes) < 100: attributes.append(pair)
                if not attributes: product.pop("attributes", None)
            reviews = [{"text": value, "source_url": url} for n in parsed.css("#vct-review-bodies .review-item")[:20]
                       if (value := text(n, 2000))]
            if reviews: data["reviews"], _ = _merge_review_cards(data.get("reviews") or [], reviews)
        elif page == "SHOP":
            credits = [n for n in parsed.css("#bd_2_container_0 a[href]")
                       if n.attributes["href"] == url + "page/creditdetail.html"]
            names = parsed.css("#pcMainCompanyNameV2")
            name = text(names[0], 240) if len(names) == 1 else None
            if shop_company_name is not None and name != shop_company_name:
                raise ValueError("HTML shop company header conflicts with selected name")
            if len(credits) > 1 or (not credits and not name):
                raise ValueError("HTML shop lacks its own company identity")
            company = data.get("company_information") or {}
            company["shop_source_url"] = url
            if name: company["shop_company_name_display_text"] = name
            headers = {}
            for selector, key in (("#pcV2SellerTagYear", "platform_tenure"), ("#pcV2MainCateLabel", "main_categories"),
                                  ("#pcV2ServiceScoreLabel", "service_score_label"), ("#pcV2ServiceScoreValue", "service_score")):
                value = text(parsed.css_first(selector), 240)
                if value: headers[key] = value
            if headers: company["shop_header_claims_display_text"] = headers
            if credits:
                module = credits[0]
                while module and "module-wrapper" not in module.attributes.get("class", "").split(): module = module.parent
                value = text(module, 1600)
                if not value: raise ValueError("HTML company introduction is unavailable")
                company["shop_introduction_display_text"] = value
                content_scope = "SHOP_HEADER_AND_INTRODUCTION"
            else:
                content_scope = "SHOP_HEADER_ONLY"
            company["shop_evidence_scope"] = content_scope
            data["company_information"] = company
        else:
            links = {n.attributes["href"] for n in parsed.css("#pc_card_baseinfo a[href]")}
            if shop_url not in links:
                raise ValueError("HTML factory lacks matching shop backlink")
            company = data.get("company_information") or {}
            for title in parsed.css("#pc_card_exhibition div"):
                if text(title) == "工厂展厅":
                    value = text(title.next, 1600)
                    if value: company["factory_description_html_display_text"] = value
            data["company_information"] = company or None
        # Keep normalized evidence inside the existing LLM input budget.
        budget_limited = len(json.dumps(data, ensure_ascii=False).encode("utf-8")) > 48_000
        if budget_limited: data = before
        records.append({"page": page, "source_url": url, "html_sha256": sha256(encoded).hexdigest(),
                        "html_bytes": len(encoded), "status": "BUDGET_LIMIT" if budget_limited else "PARSED",
                        "provenance": "SANITIZED_RENDERED_BROWSER_HTML", **({"content_scope": content_scope} if content_scope else {})})
    captured = {record["page"] for record in records}
    for page in sorted((accessible_pages or set()) - captured):
        records.append({"page": page, "source_url": {"PRODUCT": result["source_url"], "SHOP": shop_url, "FACTORY": factory_url}[page],
                        "status": "NOT_CAPTURED", "provenance": "SANITIZED_RENDERED_BROWSER_HTML"})
    data.update(evidence_coverage(data))
    data["html_capture_status"] = records
    result["supplier_data"] = data
    result["reviews"] = data.get("reviews") or []
    result["extraction_status"] = evidence_status(data)
    result["raw_payload"]["html_sources"] = records
    return result
