"""Alibaba public evidence from audited detailData and shopBizData layouts.

Inline JSON is decoded as data, never executed. The retained paths are selected
public claims, with supplier metrics and offer quotes kept in their own scopes.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html import unescape
import json
import math
import re
import time
from urllib.parse import urlsplit

from .contracts import (
    EVIDENCE_FIELDS, assemble_supplier_data, evidence_status, evidence_present as _present,
)
from .fetch import bounded_extract, _public_dns
from .evidence import (
    MalformedPage, field as _field, object as _object, string as _string,
    text as _text, validate_json_evidence as _validate_json_evidence,
)
from .dom import (
    tree as _tree, active as _active, scripts as _scripts, prune_dom as _prune_dom,
    stylesheet_hidden as _stylesheet_hidden, login_page as _login_page,
)
from .urls import normalize_alibaba_url, alibaba_identity, _ALIBABA_PRODUCT, _ALIBABA_STORE

EXTRACTOR_VERSION = "alibaba-http.v1"


def _list(value):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 2000:
        raise MalformedPage
    return value


def _select(value, keys):
    value = _object(value)
    numeric = {'companyJoinYears': True, 'dollarPriceRangeLow': False, 'dollarPriceRangeHigh': False,
               'priceRangeLow': False, 'priceRangeHigh': False, 'averageStar': False,
               'totalReviewCount': True, 'rating': False, 'reviewCount': True, 'count': True,
               'ordAmt6m': False, 'ordCnt6m': True, 'minQuantity': True,
               'maxQuantity': True, 'processPeriod': True, 'moq': True, 'price': False}
    selected = {key: value[key] for key in keys if key in value}
    for key, item in selected.items():
        if key in {'sku', 'productId'} and item is not None:
            _product_id(item)
        elif key in numeric:
            _number(item, integer=numeric[key])
        else:
            _string(item)
    return selected


def _number(value, *, integer=False, maximum=None):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise MalformedPage
    try:
        approximate = float(value)
        exact = Decimal(str(value)) if integer else None
    except (ValueError, OverflowError, InvalidOperation) as exc:
        raise MalformedPage from exc
    if not math.isfinite(approximate) or approximate < 0 or integer and exact != exact.to_integral_value():
        raise MalformedPage
    number = int(exact) if integer else approximate
    if maximum is not None and number > maximum:
        raise MalformedPage
    return number


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MalformedPage
        result[key] = value
    return result


def _json(content):
    return json.JSONDecoder(object_pairs_hook=_unique, parse_constant=lambda value: (_ for _ in ()).throw(MalformedPage())).raw_decode(content)


def _mask(content):
    # Position-preserving lexical masking prevents quoted examples and comments
    # from becoming assignments. Template interpolations are conservatively
    # rejected if they mention the source model.
    tokens = r'''//[^\r\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`'''
    def replace(match):
        value = match[0]
        if value.startswith('`') and '${' in value and any(name in value for name in ('detailData', 'shopBizData')):
            raise MalformedPage
        return value if value in {'"detailData"', "'detailData'", '"shopBizData"', "'shopBizData'"} else ' ' * len(value)
    return re.sub(tokens, replace, content)


def _model(tree, name):
    found = []
    remaining = []
    target = rf"(?:(?:window|globalThis|self)\s*(?:\.\s*{name}\b|\[\s*['\"]{name}['\"]\s*\])|\b{name}\b)"
    for script in _scripts(tree):
        content = script.text()
        code = _mask(content)
        assignments = list(re.finditer(target + r"\s*=(?!=)\s*", code))
        consumed = []
        for match in assignments:
            # Only the observed direct inline assignment is an accepted wrapper.
            if not re.match(rf"window\.{name}\s*=\s*", content[match.start():]):
                raise MalformedPage
            prefix = code[:match.start()].rstrip()
            # The audited assignments execute at script top level. Conditional,
            # function and expression wrappers cannot establish an effective
            # source model without executing the page.
            stack = []
            pairs = {')': '(', ']': '[', '}': '{'}
            for token in prefix:
                if token in '([{':
                    stack.append(token)
                elif token in pairs:
                    if not stack or stack.pop() != pairs[token]:
                        raise MalformedPage
            if stack or prefix and prefix[-1] != ';' or re.search(r'\b(?:throw|return)\b', prefix):
                raise MalformedPage
            start = match.end()
            # Masked whitespace can include quoted text; derive the JSON offset
            # from the real assignment rather than the masked match end.
            start = match.start() + re.match(rf"window\.{name}\s*=\s*", content[match.start():]).end()
            value, end = _json(content[start:])
            if not re.match(r"\s*;", content[start + end:]):
                raise MalformedPage
            consumed.append((match.start(), start + end))
            found.append(_object(value))
        for start, end in reversed(consumed):
            code = code[:start] + ' ' * (end - start) + code[end:]
        remaining.append(code)
    code = '\n'.join(remaining)
    chain = r"(?:\s*\.[A-Za-z_$][\w$]*|\s*\[[^\]]+\])*"
    roots, aliases = {'window', 'globalThis', 'self'}, {name}
    # Aliases can span inline scripts. Track simple observed references, then
    # reject writes through them rather than trying to evaluate their effects.
    while True:
        root = '(?:' + '|'.join(re.escape(item) for item in sorted(roots)) + ')'
        target = rf"(?:{root}\s*(?:\.\s*{name}\b|\[\s*['\"]{name}['\"]\s*\])|\b(?:{'|'.join(re.escape(item) for item in sorted(aliases))})\b)"
        new_roots = {match[1] for match in re.finditer(rf'\b([A-Za-z_$][\w$]*)\s*=(?!=)\s*{root}\s*(?=[;,\n]|$)', code)}
        new_aliases = {match[1] for match in re.finditer(rf'\b([A-Za-z_$][\w$]*)\s*=(?!=)\s*{target}{chain}\s*(?=[;,\n]|$)', code)}
        if new_roots <= roots and new_aliases <= aliases:
            break
        roots.update(new_roots)
        aliases.update(new_aliases)
    operators = r"(?:(?:\|\||&&|\?\?|>>>|>>|<<|\*\*|[+*/%&|^\-])?=(?!=)|\+\+|--)"
    if (re.search(target + chain + r'\s*' + operators, code)
            or re.search(r"(?:delete\s+|(?:Object\.(?:assign|defineProperty)|Reflect\.set)\s*\(\s*)" + target, code)
            or re.search(target + chain + r"\s*\.\s*(?:push|pop|shift|unshift|splice|sort|reverse|fill|copyWithin)\s*\(", code)
            or re.search(rf"(?:Object\.defineProperty|Reflect\.set)\s*\(\s*{root}\s*,\s*['\"]{name}['\"]", code)
            or re.search(rf"Object\.assign\s*\(\s*{root}\s*,[^;]*?(?:\b{name}\b|['\"]{name}['\"])\s*:", code)):
        raise MalformedPage
    if len(found) != 1:
        raise MalformedPage
    return found[0]


def _product_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r"[1-9][0-9]{0,19}", str(value)):
        raise MalformedPage
    return str(value)


def _hint(url, expected):
    # Locale product metadata may corroborate an ID without approving that host
    # for fetching. Credentials, ports, malformed paths and other hosts fail.
    text = _string(url) or ''
    parsed = urlsplit('https:' + text if text.startswith('//') else text)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port or parsed.fragment:
        raise MalformedPage
    if expected[0] == 'product':
        match = re.fullmatch(r"/product-detail/[A-Za-z0-9][A-Za-z0-9-]{0,199}[_-]([1-9][0-9]{0,19})\.html", parsed.path)
        if not re.fullmatch(r"(?:www|[a-z]{2,20})\.alibaba\.com", parsed.netloc) or not match or match[1] != expected[1]:
            raise MalformedPage
    elif alibaba_identity(url) != expected:
        raise MalformedPage
    return {'hostname': parsed.hostname, 'path': parsed.path}


def _supplier_host(value):
    text = _string(value)
    if not text:
        return None
    if '://' in text or text.startswith('//'):
        parsed = urlsplit('https:' + text if text.startswith('//') else text)
        if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port or parsed.fragment or parsed.path not in {'', '/', '/index.html', '/company_profile.html'}:
            raise MalformedPage
        text = parsed.netloc
    if not _ALIBABA_STORE.fullmatch(text):
        raise MalformedPage
    return text


def _access(html, *, has_public_evidence=False):
    tree = _tree(html)
    _stylesheet_hidden(tree)
    challenge = any(_active(node) for node in tree.css('punish-component, #nc-container'))
    _prune_dom(tree)
    visible = (_text(tree.css_first('body')) or '')[:2000].lower()
    title = (_text(tree.css_first('title')) or '').lower()
    markers = ('captcha', 'verify you are human', 'security verification', 'access denied', '安全验证', '滑动验证')
    if challenge or any(marker in title for marker in markers) or not has_public_evidence and any(marker in visible for marker in markers):
        return 'BLOCKED', 'ACCESS_CHALLENGE'
    if _login_page(tree, has_public_evidence=has_public_evidence) or not has_public_evidence and tree.css_first('form input[type="password"]') is not None:
        return 'AUTH_REQUIRED', 'LOGIN_REQUIRED'
    return None


def _metric(label, value, scope, description=None):
    label, value = _string(label), _string(value)
    if not label or not value:
        return None
    result = dict(label=label, value=value, scope=scope)
    if description:
        result['description'] = _string(description)
    return result


def _parse(html, source_url, mode, extracted_at, page_bytes):
    expected = alibaba_identity(source_url)
    kind, identity = expected
    tree = _tree(html)
    _stylesheet_hidden(tree)
    for node in tree.css('link, meta'):
        if not _active(node):
            continue
        if 'canonical' in (node.attributes.get('rel') or '').lower().split():
            _hint(node.attributes.get('href'), expected)
        if (node.attributes.get('property') or '').lower() == 'og:url':
            _hint(node.attributes.get('content'), expected)
    model = _model(tree, 'detailData' if kind == 'product' else 'shopBizData')
    ld = []
    if kind == 'product':
        for script in tree.css('script[type="application/ld+json"]'):
            if not _active(script):
                continue
            values, end = _json(script.text().lstrip())
            if script.text().lstrip()[end:].strip():
                raise MalformedPage
            ld.extend(_list(values) if isinstance(values, list) else [_object(values)])
    _prune_dom(tree)
    evidence = dict.fromkeys(EVIDENCE_FIELDS)
    raw = {}
    reviews = []
    if kind == 'product':
        g = _object(model.get('globalData'))
        product = _object(g.get('product'))
        if _product_id(product.get('productId')) != identity:
            raise MalformedPage
        main_ld = [item for item in ld if _object(item).get('@type') == 'Product']
        if len(main_ld) > 1:
            raise MalformedPage
        selected_ld = []
        for item in main_ld:
            if 'sku' in item and _product_id(item['sku']) != identity:
                raise MalformedPage
            offers = item.get('offers')
            selected_offers = []
            for offer in _list(offers) if isinstance(offers, list) else [_object(offers)]:
                offer = _object(offer)
                if offer.get('url') is not None:
                    selected_offers.append(_hint(offer['url'], expected))
            selected_ld.append(_select(item, ('sku',)) | {'offers': selected_offers})
        raw['product_identity'] = product.get('productId')
        raw['jsonld_identity'] = selected_ld
        seller = _object(g.get('seller'))
        hosts = [_supplier_host(seller.get(key)) for key in ('subDomain', 'companyProfileUrl', 'homeUrl') if seller.get(key) is not None]
        hosts = [host for host in hosts if host]
        if len(set(hosts)) > 1:
            raise MalformedPage
        supplier_host = hosts[0] if hosts else None
        for link in tree.css('.module_unifed_company_card a[href]'):
            href = link.attributes['href']
            if not isinstance(href, str):
                raise MalformedPage
            parsed = urlsplit('https:' + href if href.startswith('//') else href)
            if parsed.netloc.endswith('.en.alibaba.com') and not parsed.netloc.endswith('.m.en.alibaba.com') and parsed.path in {'', '/', '/company_profile.html'}:
                if _supplier_host(href) != supplier_host:
                    raise MalformedPage
        evidence['supplier_name'] = _string(seller.get('companyName'))
        raw['seller'] = _select(seller, ('subDomain', 'companyProfileUrl', 'companyName', 'companyBusinessType', 'companyRegisterCountry', 'companyJoinYears', 'localCompanyJoinYears'))
        if seller.get('companyProfileUrl') is not None:
            parsed_profile = urlsplit(seller['companyProfileUrl'])
            raw['seller']['companyProfileUrl'] = f'https://{_supplier_host(seller["companyProfileUrl"])}{parsed_profile.path}'
        if seller.get('homeUrl') is not None:
            home = seller['homeUrl']
            parsed_home = urlsplit('https:' + home if home.startswith('//') else home)
            raw['seller']['home_identity'] = {'hostname': _supplier_host(home), 'path': parsed_home.path}
        evidence['company_information'] = {key: value for key, value in [('company_name', evidence['supplier_name']), ('business_type', _string(seller.get('companyBusinessType'))), ('register_country', _string(seller.get('companyRegisterCountry')))] if value} or None
        evidence['years_active'] = _number(seller.get('companyJoinYears'), integer=True, maximum=200)
        attributes = []
        for name in ('productBasicProperties', 'productKeyIndustryProperties', 'productOtherProperties'):
            selected = [_select(item, ('attrName', 'attrValue')) for item in _list(product.get(name))]
            raw[name] = selected
            for item in selected:
                label, value = _string(item.get('attrName')), _string(item.get('attrValue'))
                if label and value and dict(name=label, value=value) not in attributes:
                    attributes.append(dict(name=label, value=value))
        raw['subject'] = product.get('subject')
        title = _string(product.get('subject'))
        evidence['products'] = [dict(offer_id=identity, title=title, source_url=source_url, attributes=attributes)] if title else None
        paths = _list(_field(g, 'seo', 'breadCrumb', 'pathList'))
        raw['breadcrumb_names'] = [_field(item, 'hrefObject', 'name') for item in paths]
        evidence['categories'] = list(dict.fromkeys(value for value in (_string(v) for v in raw['breadcrumb_names']) if value)) or None
        price = _object(product.get('price'))
        ranges = _object(price.get('productRangePrices'))
        raw['offer_price'] = dict(productRangePrices=_select(ranges, ('dollarPriceRangeLow', 'dollarPriceRangeHigh', 'priceRangeLow', 'priceRangeHigh', 'priceRangeText')), unit=price.get('unit'), moq=product.get('moq'))
        low, high = (_number(ranges.get(key)) for key in ('dollarPriceRangeLow', 'dollarPriceRangeHigh'))
        if low is not None and high is not None and low > high:
            raise MalformedPage
        quote = {key: value for key, value in dict(minimum=str(ranges['dollarPriceRangeLow']) if low is not None else None, maximum=str(ranges['dollarPriceRangeHigh']) if high is not None else None, currency='USD' if low is not None or high is not None else None, display_text=_string(ranges.get('priceRangeText')), unit=_string(price.get('unit')), minimum_order_quantity=_number(product.get('moq'), integer=True)).items() if value is not None}
        evidence['price_information'] = quote if low is not None or high is not None or quote.get('display_text') else None
        store = _object(_field(g, 'review', 'storeReview'))
        raw['storeReview'] = _select(store, ('averageStar', 'totalReviewCount', 'reviewRatingText'))
        evidence['rating'] = _number(store.get('averageStar'), maximum=5)
        count = _number(store.get('totalReviewCount'), integer=True)
        raw['tradeHalfYear'] = _select(seller.get('tradeHalfYear'), ('ordAmt', 'ordAmt6m', 'ordCnt6m'))
        metrics = []
        retained_fields = []
        fields = _list(_field(model, 'nodeMap', 'module_unifed_company_card', 'privateData', 'onlinePerformance', 'fields'))
        for item in fields:
            item = _object(item)
            label = _string(item.get('title')) or ''
            if label in {'Top buyers served ⓘ', 'Online revenue ⓘ', 'Dispute rate ⓘ', 'Response time ⓘ', 'On-time dispatch rate ⓘ', 'Average dispatch time ⓘ'}:
                retained_fields.append(_select(item, ('title', 'value', 'desc')))
                metric = _metric(label, item.get('value'), 'supplier performance', item.get('desc'))
                if metric:
                    metrics.append(metric)
        raw['onlinePerformance'] = retained_fields
        trade = raw['tradeHalfYear']
        if trade.get('ordAmt') is not None:
            metric = _metric('Online order amount (past 6 months)', trade['ordAmt'], 'supplier tradeHalfYear')
            if metric:
                metrics.append(metric)
        for key, label in [('ordAmt6m', 'Online order amount (past 6 months)'), ('ordCnt6m', 'Online orders (past 6 months)')]:
            if trade.get(key) is not None:
                value = _number(trade[key], integer=key == 'ordCnt6m')
                metrics.append(dict(label=label, value=str(value), scope='supplier tradeHalfYear'))
        transaction = [m for m in metrics if m['label'] not in {'Response time ⓘ', 'On-time dispatch rate ⓘ', 'Average dispatch time ⓘ'}]
        evidence['transaction_signals'] = ({'review_count': count} if count is not None else {}) | ({'source_metrics': transaction} if transaction else {}) or None
        raw['delivery'] = dict(ladderPeriodList=[_select(item, ('minQuantity', 'maxQuantity', 'processPeriod')) for item in _list(_field(g, 'trade', 'leadTimeInfo', 'ladderPeriodList'))], **_select(_field(g, 'trade', 'logisticInfo'), ('packagingDesc', 'unitSize', 'unitWeight')), **_select(seller, ('supplierOnTimeDeliveryRate', 'responseTimeText')))
        delivery_metrics = [m for m in metrics if m['label'] in {'Response time ⓘ', 'On-time dispatch rate ⓘ', 'Average dispatch time ⓘ'}]
        for key, label in [('packagingDesc', 'Packaging'), ('unitSize', 'Package size'), ('unitWeight', 'Package weight'), ('supplierOnTimeDeliveryRate', 'On-time dispatch rate'), ('responseTimeText', 'Response time')]:
            metric = _metric(label, raw['delivery'].get(key), 'supplier performance' if key.startswith('supplier') or key == 'responseTimeText' else 'main product packaging')
            if metric:
                delivery_metrics.append(metric)
        lead_times = []
        for item in raw['delivery']['ladderPeriodList']:
            selected = {key: _number(item.get(key), integer=True) for key in ('minQuantity', 'maxQuantity', 'processPeriod')}
            if all(value is not None for value in selected.values()):
                if selected['minQuantity'] > selected['maxQuantity']:
                    raise MalformedPage
                lead_times.append(selected)
        evidence['delivery_information'] = ({'source_metrics': delivery_metrics} if delivery_metrics else {}) | ({'lead_times': lead_times} if lead_times else {}) or None
        retained_reviews = []
        for node in tree.css('.product-review .product-review-list div.r-relative.r-whitespace-normal'):
            original = node.text()
            text = original[:4096].strip()[:2000]
            review = dict(text=text, source_url=source_url)
            if text and review not in reviews and len(reviews) < 20:
                reviews.append(review)
                retained_reviews.append(dict(text=original[:4096], source_url=source_url, original_length=len(original), truncated=len(original) > 4096))
        raw['review_bodies'] = retained_reviews
        evidence['reviews'] = reviews or None
    else:
        supplier_host = _supplier_host(_field(model, 'globalData', 'esiteSubDomain', 'value'))
        if supplier_host != f'{identity}.en.alibaba.com':
            raise MalformedPage
        raw['esiteSubDomain'] = supplier_host
        modules = {}
        allowed = {'supplierPerformance', 'supplierActionBar', 'factoryCapability', 'tradeCapacityMarkets', 'certifications'}
        for item in _list(model.get('pageModuleMap')):
            item = _object(item)
            name = item.get('moduleName')
            if name in allowed:
                if name in modules:
                    raise MalformedPage
                modules[name] = _object(item.get('moduleData'))
        performance, action = (modules.get(name, {}) for name in ('supplierPerformance', 'supplierActionBar'))
        names = [_string(value) for value in [performance.get('companyName'), action.get('companyName')] if value is not None]
        if len(set(names)) > 1:
            raise MalformedPage
        evidence['supplier_name'] = names[0] if names else None
        raw['supplierPerformance'] = dict(companyName=performance.get('companyName'))
        raw['supplierActionBar'] = _select(action, ('companyName', 'rating', 'reviewCount'))
        years = _object(performance.get('years'))
        raw['supplierPerformance']['years'] = _select(years, ('label', 'value'))
        tenure = _string(years.get('value'))
        if tenure:
            match = re.fullmatch(r'([0-9]{1,3}) yrs?', tenure)
            if not match:
                raise MalformedPage
            evidence['years_active'] = int(match[1])
        company = {'company_name': evidence['supplier_name']} if evidence['supplier_name'] else {}
        capabilities = []
        for card in _list(_field(modules.get('factoryCapability', {}), 'cards')):
            for item in _list(_object(card).get('items')):
                item = _object(item)
                if item.get('fieldName') in {'employee_count', 'factory_area_sqm', 'production_line_count', 'rd_team_count', 'qc_staff_count', 'export_experience_years', 'total_new_products_annual'}:
                    selected = _select(item, ('fieldName', 'label', 'type', 'value'))
                    capabilities.append(selected)
                    label, value = _string(item.get('label')), _string(item.get('value'))
                    if label and value:
                        company[label] = value
        raw['factoryCapability'] = capabilities
        markets = [_select(item, ('name', 'percentage')) for item in _list(_field(modules.get('tradeCapacityMarkets', {}), 'markets'))]
        raw['markets'] = markets
        markets_text = [' '.join([_string(m.get('name')) or '', _string(m.get('percentage')) or '']).strip() for m in markets]
        if markets_text:
            company['markets_display_text'] = ' · '.join(markets_text)
        card_text = [node.text(separator=' ', strip=True) for node in tree.css('.company-card') if _text(node)]
        if card_text:
            raw['company_card_text'] = card_text
            # Avoid retaining whole cards which may include contacts. Select only
            # the audited business type/country tokens as public claims.
            raw.pop('company_card_text')
            for label in ('Custom Manufacturer', 'CN'):
                if any(re.search(r'\b' + re.escape(label) + r'\b', text) for text in card_text):
                    raw.setdefault('company_card_claims', []).append(label)
                    company['business_type' if label != 'CN' else 'register_country'] = label
        evidence['company_information'] = company or None
        categories = []
        raw_categories = []
        for link in tree.css('a.menu-link[href*="/productgrouplist-"]'):
            parsed = urlsplit(link.attributes['href'])
            if parsed.scheme not in {'', 'https'} or parsed.netloc and parsed.netloc != supplier_host:
                raise MalformedPage
            original = link.text()
            label = unescape(original).strip()
            if label and label not in categories:
                categories.append(label)
                raw_categories.append(dict(text=original, href=link.attributes['href']))
        raw['categories'] = raw_categories
        evidence['categories'] = categories or None
        certificates = [_select(item, ('name', 'category')) for item in _list(_field(modules.get('certifications', {}), 'items'))]
        raw['certifications'] = certificates
        evidence['certifications'] = list(dict.fromkeys(f"{_string(item.get('name'))} ({_string(item.get('category'))})" for item in certificates if _string(item.get('name')) and _string(item.get('category')))) or None
        products, retained_products = [], []
        for link in tree.css('section[data-module-name="productCategories"] a[href*="/product-detail/"]'):
            url = normalize_alibaba_url(link.attributes['href'])
            product_kind, product_id = alibaba_identity(url)
            if product_kind != 'product':
                raise MalformedPage
            # Audited cards have an image wrapper followed by a text wrapper.
            wrappers = [node for node in link.iter() if node.parent == link and node.tag == 'div']
            if len(wrappers) < 2:
                continue
            text_wrapper = wrappers[1]
            text_nodes = [node for node in text_wrapper.iter() if node.parent == text_wrapper and node.tag == 'div']
            texts = [node.text() for node in text_nodes]
            if not texts:
                continue
            original = texts[0]
            title = unescape(original).strip()
            if title and not any(item['offer_id'] == product_id for item in products) and len(products) < 20:
                quote_nodes = [node for node in text_nodes[1].iter() if node.parent == text_nodes[1] and node.tag == 'div'] if len(text_nodes) > 1 else []
                selected = dict(offer_id=product_id, title=original, source_url=url, price_display_text=quote_nodes[0].text() if quote_nodes else None, minimum_order_display_text=quote_nodes[1].text() if len(quote_nodes) > 1 else None)
                retained_products.append(selected)
                products.append({key: unescape(value).strip() if isinstance(value, str) and key not in {'offer_id', 'source_url'} else value for key, value in selected.items()})
        raw['products'] = retained_products
        evidence['products'] = products or None
        rating = _object(performance.get('reviews'))
        raw['supplierPerformance']['reviews'] = _select(rating, ('value', 'count', 'label'))
        evidence['rating'] = _number(rating.get('value'), maximum=5)
        count = _number(rating.get('count'), integer=True)
        # Action-bar values are retained as separately scoped display evidence;
        # the performance module remains the documented aggregate precedence.
        metrics, delivery = [], []
        for name in ('onlineTransactions', 'bigBuyerCount', 'reorderRate', 'shippingDays', 'responseTime'):
            item = _object(performance.get(name))
            raw['supplierPerformance'][name] = _select(item, ('amount', 'value', 'label'))
            metric = _metric(item.get('label'), item.get('amount', item.get('value')), 'supplier performance')
            if metric:
                (delivery if name in {'shippingDays', 'responseTime'} else metrics).append(metric)
        action_rating = _number(action.get('rating'), maximum=5)
        if action_rating is not None:
            metrics.append(dict(label='Rating', value=str(action_rating), scope='supplier action bar'))
        evidence['transaction_signals'] = ({'source_metrics': metrics} if metrics else {}) | ({'review_count': count} if count is not None else {}) or None
        evidence['delivery_information'] = {'source_metrics': delivery} if delivery else None
    if not evidence['supplier_name'] and not evidence['products']:
        raise MalformedPage
    timestamp = (extracted_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    data = assemble_supplier_data(evidence, platform='ALIBABA', source_url=source_url, offer_id=identity if kind == 'product' else None,
                platform_supplier_id=supplier_host, extracted_at=timestamp, extraction_method='PUBLIC_HTTP', analysis_mode=mode,
                extractor_version=EXTRACTOR_VERSION)
    raw_payload = dict(source_url=source_url, captured_at=timestamp, html_sha256=sha256(page_bytes if page_bytes is not None else html.encode('utf-8')).hexdigest(), public_fields=raw)
    _validate_json_evidence(data)
    _validate_json_evidence(raw_payload)
    return dict(source_url=source_url, extraction_status=evidence_status(data), supplier_data=data, raw_payload=raw_payload, reviews=reviews)


def parse_alibaba_page(html, source_url, *, analysis_mode='ACCOUNT_PUBLIC', extracted_at=None, page_bytes=None):
    if analysis_mode not in {'ACCOUNT_PUBLIC', 'GUEST_PUBLIC'}:
        raise ValueError('Invalid Alibaba extraction provenance')
    source_url = normalize_alibaba_url(source_url)
    result, failure = None, 'MALFORMED_PAGE'
    try:
        result = _parse(html, source_url, analysis_mode, extracted_at, page_bytes)
    except (MalformedPage, RecursionError, ValueError, TypeError) as exc:
        failure = 'PARSER_LIMIT' if isinstance(exc, RecursionError) else 'MALFORMED_PAGE'
    access = _access(html, has_public_evidence=result is not None)
    return dict(source_url=source_url, extraction_status=access[0], reason=access[1]) if access else result if result is not None else dict(source_url=source_url, extraction_status='PARSE_FAILED', reason=failure)


def _login_destination(url):
    parsed = urlsplit(url)
    return parsed.scheme == 'https' and parsed.netloc == 'login.alibaba.com' and parsed.path == '/login.htm' and not parsed.fragment


def extract_alibaba(source_url, *, analysis_mode='ACCOUNT_PUBLIC', client=None, dns_check=_public_dns, clock=time.monotonic, sleep=time.sleep, browser_fallback=False, browser_renderer=None):
    try:
        canonical = normalize_alibaba_url(source_url)
    except ValueError:
        return dict(source_url=source_url, extraction_status='UNSUPPORTED_PAGE', reason='INVALID_URL')
    return bounded_extract(source_url, normalize=normalize_alibaba_url, identity=alibaba_identity, parse=parse_alibaba_page,
                           classify_access=_access, login_destination=_login_destination, allowed_hosts=(urlsplit(canonical).netloc,),
                           accept_cookies=False,
                           mismatch_reason='SOURCE_MISMATCH', analysis_mode=analysis_mode, client=client, dns_check=dns_check, clock=clock, sleep=sleep,
                           browser_fallback=browser_fallback, browser_renderer=browser_renderer)
