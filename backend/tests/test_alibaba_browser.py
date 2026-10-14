from datetime import datetime, timezone
import json
from pathlib import Path
import re
import pytest
from backend.app.extraction.alibaba_browser import alibaba_company_url
from backend.app.extraction.supplier_bundle import SupplierBundle, normalize_bundle
from backend.app.intelligence.identity import assess_supplier_identity

FIXTURE = Path(__file__).parent / 'fixtures' / 'alibaba_guided_yiheng.json'


def selected():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def normalize(value):
    return normalize_bundle(SupplierBundle.model_validate(value), at=datetime(2026, 10, 14, tzinfo=timezone.utc))


def test_saved_alibaba_product_store_and_overview_preserve_scoped_source_facts():
    result = normalize(selected())
    data = result['supplier_data']
    assert data['platform'] == 'ALIBABA' and data['extraction_method'] == 'EXTENSION_DOM'
    assert data['price_information']['minimum_order_quantity'] == 1
    assert '₫744,638' in data['price_information']['display_text']
    assert 'PayPal' in data['price_information']['payment_methods_display_text']
    assert data['price_information']['terms_source_url'].endswith('/company_profile.html')
    assert data['rating'] == 4.8
    assert data['transaction_signals']['review_count'] == 78
    assert data['transaction_signals']['review_scope'] == 'PRODUCT'
    assert len(data['reviews']) == 3
    assert len(data['products'][0]['attributes']) == 24
    assert 'Money-back guarantee' in data['products'][0]['services_display_text']
    assert 'Get your money back for missing deliveries and defective or damaged products' in data['products'][0]['services_display_text']
    assert 'eligibility and fulfillment remain unverified' in data['products'][0]['services_scope']
    company = data['company_information']
    assert company['factory_area_display_text'] == '1,000-3,000 square meters'
    assert 'factory_area_sqm' not in company
    assert company['production_line_count'] == 4
    assert company['established_year_display_text'] == '2026'
    assert company['location'] == 'Guangdong, China'
    assert company['platform_tenure_display_text'] == '1 yr on Alibaba.com'
    assert data['years_active'] is None
    assert company.get('employee_count') is None
    assert data['certifications'] is None
    assert [x['status'] for x in data['html_capture_status']] == ['PARSED'] * 3
    assert all(x['source_url'].startswith('https://') and '.m.en.' not in x['source_url'] for x in data['html_capture_status'])
    assert data['page_context']['sections']
    assert len(json.dumps(data, ensure_ascii=False).encode()) <= 48_000


def test_alibaba_factory_claims_contribute_without_manufacturing_false_certainty():
    identity = assess_supplier_identity(normalize(selected())['supplier_data'])
    ids = {x.evidence_id for x in identity.supporting_evidence}
    assert 'company_information.production_line_count' in ids
    assert 'company_information.factory_area_display_text' in ids
    assert 'company_information.company_profile_source_url' in ids
    assert 'company_information.business_type.factory' in ids
    assert 'company_information.business_type.trader' in ids
    assert identity.classification == 'UNCERTAIN'
    assert identity.confidence > 0


def test_alibaba_begin_and_product_only_finish_do_not_require_hidden_company_information():
    value = selected()
    value.pop('shop'); value.pop('factory')
    value['html_sources'] = value['html_sources'][:1]
    value['outcomes'] = []
    result = normalize(value)
    assert result['supplier_data']['company_information']['platform_tenure_display_text']
    value['outcomes'] = [{'page': 'SHOP', 'status': 'UNAVAILABLE'}, {'page': 'FACTORY', 'status': 'UNAVAILABLE'}]
    assert len(normalize(value)['reviews']) == 3


@pytest.mark.parametrize('change', ['shop', 'profile', 'backlink', 'name', 'canonical', 'field', 'selected-value',
                                    'html-value', 'html-title', 'html-price', 'rating', 'review-total', 'review', 'attribute', 'unsafe-link',
                                    'script', 'private-attribute', 'secret', 'missing-product', 'missing-profile', 'outcome', 'platform'])
def test_unsafe_or_mismatched_alibaba_evidence_is_rejected(change):
    value = selected()
    if change == 'shop': value['shop']['source_url'] = 'https://other.en.alibaba.com/'
    if change == 'profile': value['shop']['factory_url'] = 'https://other.en.alibaba.com/company_profile.html'
    if change == 'backlink': value['factory']['shop_url'] = 'https://other.en.alibaba.com/'
    if change == 'name': value['factory']['company_name'] = 'Different Company'
    if change == 'canonical': value['factory']['canonical_url'] = 'https://other.en.alibaba.com/company_profile.html'
    if change == 'field': value['factory']['claims'].append({'name': 'CCC', 'value': 'unobserved certification'})
    if change == 'selected-value': value['factory']['claims'][0]['value'] = 'Different business type'
    if change == 'html-value': value['html_sources'][2]['html'] = value['html_sources'][2]['html'].replace('1,000-3,000 square meters', '8,000 square meters')
    if change == 'html-title': value['html_sources'][0]['html'] = value['html_sources'][0]['html'].replace('2026 New GEN5', 'Wrong product')
    if change == 'html-price': value['html_sources'][0]['html'] = value['html_sources'][0]['html'].replace('₫744,638', '₫100')
    if change == 'rating': value['product']['fields']['rating'] = 2.0
    if change == 'review-total': value['product']['fields']['review_count'] = 198
    if change == 'review': value['product']['fields']['reviews'][0]['text'] = 'A review that is absent from the captured source'
    if change == 'attribute': value['product']['fields']['product_attributes'][0]['value'] = 'Invented specification'
    if change == 'unsafe-link': value['html_sources'][2]['html'] += '<a href="https://evil.test/">company</a>'
    if change == 'script': value['html_sources'][0]['html'] += '<script>window.privateState={}</script>'
    if change == 'private-attribute': value['html_sources'][0]['html'] += '<div data-account="private">hidden</div>'
    if change == 'secret': value['factory']['description'] = 'access_token=private'
    if change == 'missing-product': value['html_sources'] = value['html_sources'][1:]
    if change == 'missing-profile': value['html_sources'] = value['html_sources'][:2]
    if change == 'outcome': value['outcomes'][1]['status'] = 'UNAVAILABLE'
    if change == 'platform': value['platform'] = '1688'
    with pytest.raises(ValueError): normalize(value)


@pytest.mark.parametrize('url', ['https://a.en.alibaba.com:443/', 'https://user@a.en.alibaba.com/', 'https://a.en.alibaba.com.evil.test/',
                               'https://a.en.alibaba.com/contactinfo.html', 'http://a.en.alibaba.com/', 'https://a.en.alibaba.com/#session',
                               'https://a.en.alibaba.com\\@evil.test/'])
def test_alibaba_supplier_url_rejects_unsafe_identity(url):
    with pytest.raises(ValueError): alibaba_company_url(url)


def test_mobile_company_alias_and_desktop_canonical_share_one_supplier_identity():
    assert alibaba_company_url('https://yihengsportinggoods.m.en.alibaba.com/?productId=1601711788226') == 'https://yihengsportinggoods.en.alibaba.com/'
    assert alibaba_company_url('https://yihengsportinggoods.m.en.alibaba.com/company_profile.html?spm=tracking', profile=True) == 'https://yihengsportinggoods.en.alibaba.com/company_profile.html'


def test_existing_1688_bundle_digest_shape_is_unchanged_by_alibaba_discriminator():
    from backend.tests.test_supplier_bundle import selected as original
    value = original()
    dumped = SupplierBundle.model_validate(value).model_dump(mode='json')
    assert 'platform' not in dumped
    assert 'company_name' not in dumped['factory']


def test_large_unicode_review_sample_is_bounded_and_disclosed_without_changing_total():
    value = selected()
    value['product']['fields']['reviews'] = []
    bodies = '<section id="vct-review-bodies">' + ('<div class="review-item">' + '好' * 2000 + '</div>') * 20 + '</section>'
    value['html_sources'][0]['html'] = re.sub(r'<section id="vct-review-bodies">.*?</section>', lambda _: bodies, value['html_sources'][0]['html'])
    result = normalize(value)
    data = result['supplier_data']
    assert len(json.dumps(data, ensure_ascii=False).encode()) <= 48_000
    assert data['transaction_signals']['review_count'] == 78
    assert 0 < len(data['reviews']) < 20
    assert data['review_capture_limit']['captured_count'] == 20
    assert data['html_capture_status'][0]['status'] == 'BUDGET_LIMIT'
