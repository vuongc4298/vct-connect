from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

os.environ.setdefault('DEVELOPER_MODE', 'true')
os.environ.setdefault('DATABASE_URL', 'postgresql://unused')

from backend.app.extraction.alibaba import extract_alibaba, parse_alibaba_page, _model, _number
from backend.app.extraction.renormalize import UnsupportedRawEvidence, renormalize_public_fields
from backend.app.extraction.contracts import EVIDENCE_FIELDS
from backend.app.extraction.offer1688 import MalformedPage
from backend.app.extraction.taobao import _tree
from backend.app.extraction.urls import normalize_alibaba_url, alibaba_identity, source_platform
from backend.app.extraction.fetch import MAX_HTML_BYTES, PublicOnlyBackend, UnsafeDestination
from backend.app.main import Submission
from backend.worker.main import _compute_claim

PRODUCT = 'https://www.alibaba.com/product-detail/100-Cotton-180gsm-T-shirts-Men_1600147809763.html'
PROFILE = 'https://dgxuandele.en.alibaba.com/company_profile.html'
AT = datetime(2026, 10, 1, tzinfo=timezone.utc)


def capture(profile=False):
    return (Path(__file__).parent / 'fixtures' / ('alibaba_profile_dgxuandele.html' if profile else 'alibaba_product_1600147809763.html')).read_text(encoding='utf-8')


@pytest.mark.parametrize('profile', [False, True])
def test_saved_alibaba_shapes_replay_from_selected_fields(profile):
    url = PROFILE if profile else PRODUCT
    original = parse_alibaba_page(capture(profile), url, extracted_at=AT)
    data = original['supplier_data']
    replay = renormalize_public_fields(raw_payload=original['raw_payload'], source_url=url,
        extraction_method='PUBLIC_HTTP', analysis_mode='ACCOUNT_PUBLIC', extracted_at=data['extracted_at'],
        source_snapshot_id=uuid4(), source_extractor_version=data['extractor_version'])
    assert replay['supplier_data']['extractor_version'] == 'alibaba-raw.v2'
    assert replay['supplier_data']['missing_fields'] == data['missing_fields']
    assert replay['supplier_data']['completeness'] == data['completeness']
    assert replay['reviews'] == original['reviews']
    assert {key: replay['supplier_data'][key] for key in EVIDENCE_FIELDS} == {
        key: data[key] for key in EVIDENCE_FIELDS
    }
    fields = original['raw_payload']['public_fields']
    fields['esiteSubDomain' if profile else 'product_identity'] = 'other.en.alibaba.com' if profile else '1'
    with pytest.raises(UnsupportedRawEvidence):
        renormalize_public_fields(raw_payload=original['raw_payload'], source_url=url,
            extraction_method='PUBLIC_HTTP', analysis_mode='ACCOUNT_PUBLIC', extracted_at=data['extracted_at'],
            source_snapshot_id=uuid4(), source_extractor_version=data['extractor_version'])


def test_alibaba_more_than_twenty_reviews_are_bounded_without_coverage_inflation():
    card = '<div class="r-relative r-whitespace-normal">Review {}</div>'
    html = capture().replace('<div class="product-review-list">',
                             '<div class="product-review-list">' + ''.join(card.format(i) for i in range(25)))
    result = parse_alibaba_page(html, PRODUCT, extracted_at=AT)
    assert result['extraction_status'] == 'PARTIAL'
    assert len(result['reviews']) == 20
    assert len(result['raw_payload']['public_fields']['review_bodies']) == 20
    assert len({item['text'] for item in result['reviews']}) == 20
    assert result['supplier_data']['completeness'] == 0.8333


@pytest.mark.parametrize('identity', ['supplier', 'sku', 'offer'])
def test_alibaba_raw_replay_rejects_conflicting_retained_identities(identity):
    original = parse_alibaba_page(capture(), PRODUCT, extracted_at=AT)
    fields = original['raw_payload']['public_fields']
    if identity == 'supplier':
        fields['seller']['companyProfileUrl'] = 'https://other.en.alibaba.com/company_profile.html'
    elif identity == 'sku':
        fields['jsonld_identity'] = [{'sku': '1', 'offers': []}]
    else:
        fields['jsonld_identity'] = [{'offers': [{'hostname': 'www.alibaba.com',
                                                 'path': '/product-detail/Other_1.html'}]}]
    with pytest.raises(UnsupportedRawEvidence):
        renormalize_public_fields(raw_payload=original['raw_payload'], source_url=PRODUCT,
            extraction_method='PUBLIC_HTTP', analysis_mode='ACCOUNT_PUBLIC',
            extracted_at=original['supplier_data']['extracted_at'],
            source_snapshot_id=uuid4(), source_extractor_version=original['supplier_data']['extractor_version'])


def model_page(model, profile=False):
    return '<script>window.' + ('shopBizData' if profile else 'detailData') + ' = ' + json.dumps(model) + ';</script>'


@pytest.mark.parametrize('url', [PRODUCT, PRODUCT+'?spm=tracking&id=1', PROFILE, PROFILE+'?spm=tracking'])
def test_audited_forms_admitted_without_tracking(url):
    assert Submission(source_url=url).source_url == normalize_alibaba_url(url)
    assert source_platform(url) == 'ALIBABA'


@pytest.mark.parametrize('url', [PRODUCT+'#fragment', PRODUCT+'#', PRODUCT.replace('https:', 'http:'), PRODUCT.replace('www.alibaba.com','www.alibaba.com:443'),
    PRODUCT.replace('www.alibaba.com','user@www.alibaba.com'), PRODUCT.replace('www.alibaba.com','www.alibaba.com.evil.test'),
    PRODUCT.replace('_1600147809763','_0'), PRODUCT.replace('_1600147809763','_'+'1'*21), PRODUCT.replace('www.alibaba.com','m.alibaba.com'),
    PRODUCT.replace('100-Cotton','%31-Cotton'), PRODUCT.replace('100-Cotton','中文'), PRODUCT.replace('www.alibaba.com','www.alibaba.com\n'),
    PROFILE.replace('dgxuandele','-store'), PROFILE.replace('dgxuandele','store-'), PROFILE.replace('dgxuandele','a'*64),
    PROFILE.replace('/company_profile.html','/'), 'https://www.alibaba.com/', 'https://s.alibaba.com/link', ' '+PRODUCT, PROFILE+'\x7f'])
def test_unsupported_and_unsafe_forms_rejected(url):
    with pytest.raises(ValueError): normalize_alibaba_url(url)


@pytest.mark.parametrize('profile,coverage', [(False,0.8333),(True,0.75)])
def test_audited_evidence_and_selected_raw_values(profile, coverage):
    html=capture(profile); source=PROFILE if profile else PRODUCT
    result=parse_alibaba_page(html,source,extracted_at=AT,page_bytes=html.encode())
    data=result['supplier_data']; raw=result['raw_payload']
    assert result['extraction_status']=='PARTIAL'
    assert data['platform']=='ALIBABA' and data['extraction_method']=='PUBLIC_HTTP' and data['extractor_version']=='alibaba-http.v1'
    assert data['completeness']==coverage and len(data['completeness_denominator'])==12
    assert data['extracted_at']==AT.isoformat() and data['years_active']==6 and data['rating']==4.7
    assert data['platform_supplier_id']==('dgxuandele.en.alibaba.com' if profile else 'beautiy.en.alibaba.com')
    assert raw['html_sha256']==sha256(html.encode()).hexdigest()
    assert data['activity_history'] is None
    serialized=json.dumps(result)
    for forbidden in ['csrf','chatToken','contactName','accountFirstName','reviewer','cna','traceInfo','avgValue','deltaPercent','photo','mediaItems']:
        assert forbidden not in serialized
    if profile:
        assert len(data['products'])==16 and data['price_information'] is None and data['reviews'] is None
        assert data['transaction_signals']['review_count']==39
        assert data['company_information']['Total employees']=='43'
        assert data['company_information']['Years exporting']=='8'
        assert 'RoHS (PRODUCT)' in data['certifications'] and 'RoHS (INSPECTION_REPORT)' in data['certifications']
        assert "Men's" in data['products'][0]['title']
        assert data['products'][0]['price_display_text'] and data['products'][0]['minimum_order_display_text']
        assert {'label':'Online revenue','value':'US $100K − $200K','scope':'supplier performance'} in data['transaction_signals']['source_metrics']
        assert {'label':'Top buyers served','value':'35','scope':'supplier performance'} in data['transaction_signals']['source_metrics']
        assert {'label':'Reorder rate','value':'43.9%','scope':'supplier performance'} in data['transaction_signals']['source_metrics']
        assert {'label':'Response time','value':'≤2h','scope':'supplier performance'} in data['delivery_information']['source_metrics']
        assert {'label':'Average dispatch time','value':'25.6d','scope':'supplier performance'} in data['delivery_information']['source_metrics']
    else:
        assert data['supplier_name']=='Lanxi Beauty Clothing Firm'
        assert data['offer_id']=='1600147809763' and len(data['products'])==1
        assert data['price_information']['minimum']=='3.26' and data['price_information']['maximum']=='4.59'
        assert data['price_information']['currency']=='USD' and data['price_information']['minimum_order_quantity']==2
        assert {'name':'MOQ','value':'10 Piece'} in data['products'][0]['attributes']
        assert data['transaction_signals']['review_count']==214
        assert result['reviews']==[{'text':'Nice product','source_url':PRODUCT}]
        assert data['delivery_information']['lead_times'][0]=={'minQuantity':1,'maxQuantity':50,'processPeriod':7}


@pytest.mark.parametrize('profile', [False,True])
def test_original_hash_uses_response_bytes(profile):
    original=b'original response bytes'
    assert parse_alibaba_page(capture(profile),PROFILE if profile else PRODUCT,page_bytes=original)['raw_payload']['html_sha256']==sha256(original).hexdigest()


@pytest.mark.parametrize('profile', [False,True])
def test_conflicting_identity_binding_fails_without_snapshot(profile):
    html=capture(profile).replace('dgxuandele.en.alibaba.com','other.en.alibaba.com') if profile else capture().replace('1600147809763','1600147809764')
    result=parse_alibaba_page(html,PROFILE if profile else PRODUCT)
    assert result['extraction_status']=='PARSE_FAILED' and 'supplier_data' not in result


@pytest.mark.parametrize('hint', [PRODUCT.replace('1600147809763','1'), 'https://evil.test/product-detail/test_1600147809763.html', PRODUCT.replace('_1600147809763','_invalid'), PROFILE])
def test_metadata_hints_cannot_change_product(hint):
    for metadata in [f'<link rel="canonical" href="{hint}">',f'<meta property="og:url" content="{hint}">']:
        assert parse_alibaba_page(capture().replace('<head>','<head>'+metadata),PRODUCT)['extraction_status']=='PARSE_FAILED'


def test_locale_metadata_corrobates_only_not_fetch_admission():
    url='//indonesian.alibaba.com/product-detail/100-Cotton-180gsm-T-Shirts-Men-1600147809763.html'
    assert parse_alibaba_page(capture(),PRODUCT)['extraction_status']=='PARTIAL'
    with pytest.raises(ValueError): normalize_alibaba_url('https:'+url)


def test_product_seller_identity_conflict():
    html=capture().replace('https://beautiy.en.alibaba.com/company_profile.html','https://other.en.alibaba.com/company_profile.html')
    assert parse_alibaba_page(html,PRODUCT)['extraction_status']=='PARSE_FAILED'


@pytest.mark.parametrize('profile', [False,True])
def test_sparse_bound_evidence_remains_partial(profile):
    model=_model(_tree(capture(profile)), 'shopBizData' if profile else 'detailData')
    if profile:
        model['pageModuleMap']=[{'moduleName':'supplierPerformance','moduleData':{'companyName':'Public supplier'}}]
    else:
        model={'globalData':{'product':{'productId':'1600147809763','subject':'Public product'}}}
    data=parse_alibaba_page(model_page(model,profile),PROFILE if profile else PRODUCT)['supplier_data']
    assert data['completeness']==(0.1667 if profile else 0.0833) and data['reviews'] is None and data['rating'] is None


@pytest.mark.parametrize('integer', [False, True])
def test_numeric_overflow_is_a_fixed_malformed_failure(integer):
    with pytest.raises(MalformedPage):
        _number(10**400, integer=integer)
    model=_model(_tree(capture()),'detailData')
    model['globalData']['product']['moq']=10**400
    assert parse_alibaba_page(model_page(model),PRODUCT)['extraction_status']=='PARSE_FAILED'


@pytest.mark.parametrize('value', [9007199254740993, '9007199254740993'])
def test_integer_moq_and_review_count_remain_exact(value):
    model=_model(_tree(capture()),'detailData')
    model['globalData']['product']['moq']=value
    model['globalData']['review']['storeReview']['totalReviewCount']=value
    result=parse_alibaba_page(model_page(model),PRODUCT)
    assert result['supplier_data']['price_information']['minimum_order_quantity']==9007199254740993
    assert result['supplier_data']['transaction_signals']['review_count']==9007199254740993
    assert result['raw_payload']['public_fields']['offer_price']['moq']==value


@pytest.mark.parametrize('path', [
    ('seller','localCompanyJoinYears'), ('product','price','productRangePrices','priceRangeLow'),
    ('product','price','productRangePrices','priceRangeHigh'), ('review','storeReview','reviewRatingText')])
@pytest.mark.parametrize('value', [{'session':'PRIVATE_STATE'}, ['PRIVATE_STATE'], True])
def test_retained_scalar_selections_reject_private_nested_and_invalid_shapes(path,value):
    model=_model(_tree(capture()),'detailData'); item=model['globalData']
    for key in path[:-1]: item=item[key]
    item[path[-1]]=value
    result=parse_alibaba_page(model_page(model),PRODUCT)
    assert result['extraction_status']=='PARSE_FAILED' and 'raw_payload' not in result
    assert 'PRIVATE_STATE' not in json.dumps(result)


def test_profile_unused_retained_scalar_is_validated():
    model=_model(_tree(capture(True)), 'shopBizData')
    action=next(item['moduleData'] for item in model['pageModuleMap'] if item['moduleName']=='supplierActionBar')
    action['reviewCount']={'session':'PRIVATE_STATE'}
    assert parse_alibaba_page(model_page(model,True),PROFILE)['extraction_status']=='PARSE_FAILED'


def test_jsonld_and_home_only_bindings_retain_no_navigation_or_session_queries():
    html=capture().replace('1600147809763.html"','1600147809763.html?session=PRIVATE_URL_STATE&tracking=1"')
    result=parse_alibaba_page(html,PRODUCT)
    binding=result['raw_payload']['public_fields']['jsonld_identity'][0]
    assert binding['sku']=='1600147809763'
    assert binding['offers']==[{'hostname':'indonesian.alibaba.com','path':'/product-detail/100-Cotton-180gsm-T-Shirts-Men-1600147809763.html'}]
    assert 'PRIVATE_URL_STATE' not in json.dumps(result)
    model=_model(_tree(capture()),'detailData')
    seller=model['globalData']['seller']; seller.pop('subDomain'); seller.pop('companyProfileUrl')
    seller['homeUrl']='https://beautiy.en.alibaba.com/index.html?session=PRIVATE_URL_STATE&from=detail'
    result=parse_alibaba_page(model_page(model),PRODUCT)
    assert result['supplier_data']['platform_supplier_id']=='beautiy.en.alibaba.com'
    assert result['raw_payload']['public_fields']['seller']['home_identity']=={'hostname':'beautiy.en.alibaba.com','path':'/index.html'}
    assert 'PRIVATE_URL_STATE' not in json.dumps(result)


@pytest.mark.parametrize('mutation', [
    'window.detailData = {};', 'window["detailData"] = {};', 'window.detailData.globalData.product = {};',
    'window.detailData ||= {};', 'Object.assign(window.detailData, {});', 'Object.defineProperty(window, "detailData", {});',
    'delete window.detailData.globalData;', 'window.detailData.globalData.product.productId++;',
    '`test ${window.detailData = {}}`;',
    'detailData = {};', 'globalThis.detailData = {};', 'Object.defineProperty(window.detailData, "globalData", {});',
    'window.detailData.globalData.product.productBasicProperties.push({});',
    'const alias = window.detailData; alias.globalData.product.productId = "1";',
    'let alias = window.detailData.globalData; Object.assign(alias, {product:{}});',
    'var root = window; root.detailData = {};',
    'Reflect.set(window, "detailData", {});', 'Reflect.set(window.detailData.globalData, "product", {});',
    'Object.assign(window, {detailData:{}});', 'Object.assign(window, {"detailData":{}});',
    'window.detailData &= {};', 'window.detailData <<= 1;', 'window.detailData >>= 1;',
    'window.detailData >>>= 1;', 'window.detailData ^= 1;', 'window.detailData **= 1;',
])
def test_ambiguous_effective_source_model_rejected(mutation):
    assert parse_alibaba_page(capture()+'<script>'+mutation+'</script>',PRODUCT)['extraction_status']=='PARSE_FAILED'


def test_quoted_examples_and_nonexecutable_assignments_do_not_bind():
    assert parse_alibaba_page('<script>var text="window.detailData = {};"; // window.detailData = {};</script>'+capture(),PRODUCT)['extraction_status']=='PARTIAL'
    model=_model(_tree(capture()),'detailData')
    for wrapper in ['<template>{}</template>','<noscript>{}</noscript>']:
        assert parse_alibaba_page(wrapper.format(model_page(model)),PRODUCT)['extraction_status']=='PARSE_FAILED'


@pytest.mark.parametrize('wrapper', ['if (false) {{{}}}', 'function deferred() {{{}}}', 'if (false) {}', 'false && {}', 'setTimeout(() => {{{}}}, 1);'])
def test_unexecuted_or_conditional_assignment_wrapper_cannot_supply_evidence(wrapper):
    model=_model(_tree(capture()),'detailData')
    assignment='window.detailData = '+json.dumps(model)+';'
    assert parse_alibaba_page('<script>'+wrapper.format(assignment)+'</script>',PRODUCT)['extraction_status']=='PARSE_FAILED'


def test_throw_before_assignment_cannot_supply_effective_model():
    assert parse_alibaba_page(capture().replace('window.detailData =','throw new Error("PRIVATE_ERROR"); window.detailData ='),PRODUCT)=={'source_url':PRODUCT,'extraction_status':'PARSE_FAILED','reason':'MALFORMED_PAGE'}
    assert parse_alibaba_page(capture().replace('window.detailData =','// throw new Error("example");\n window.detailData ='),PRODUCT)['extraction_status']=='PARTIAL'


def test_hidden_and_near_miss_review_content_excluded():
    html=capture().replace('Nice product','Nice product<span hidden>PRIVATE_HIDDEN</span><span style="opacity:0">PRIVATE_INVISIBLE</span><script>var secret="PRIVATE_SCRIPT";</script>')
    html += '<div class="r-relative r-whitespace-normal">UNRELATED</div><div class="product-review-list"><div class="r-relative">REVIEWER</div><div hidden class="r-relative r-whitespace-normal">PRIVATE_REVIEW</div></div>'
    result=parse_alibaba_page(html,PRODUCT)
    assert result['reviews']==[{'text':'Nice product','source_url':PRODUCT}]
    assert all(word not in json.dumps(result) for word in ['PRIVATE','REVIEWER','UNRELATED'])


def test_matching_review_metadata_decoys_outside_original_component_are_excluded():
    html=capture()+'<aside class="product-review-list"><div class="r-relative r-whitespace-normal">PRIVATE_METADATA</div></aside>'
    result=parse_alibaba_page(html,PRODUCT)
    assert result['reviews']==[{'text':'Nice product','source_url':PRODUCT}]
    assert 'PRIVATE_METADATA' not in json.dumps(result)


def test_inline_stylesheet_hides_scoped_review_container():
    html=capture().replace('<head>', '<head><style>.secret {display:none}</style>').replace('class="product-review-list"','class="product-review-list secret"')
    result=parse_alibaba_page(html,PRODUCT)
    assert result['extraction_status']=='PARTIAL' and result['reviews']==[]
    assert 'Nice product' not in json.dumps(result)


@pytest.mark.parametrize('hint', ['<link hidden rel="canonical" href="https://www.alibaba.com/product-detail/Other_1.html">', '<meta style="display:none" property="og:url" content="https://www.alibaba.com/product-detail/Other_1.html">'])
def test_inactive_conflicting_identity_hint_is_excluded(hint):
    assert parse_alibaba_page(capture().replace('<head>','<head>'+hint),PRODUCT)['extraction_status']=='PARTIAL'


def test_public_account_fields_are_excluded_even_if_malformed():
    model=_model(_tree(capture()),'detailData')
    model['globalData']['buyer']={'csrf':'SECRET','malformed':'\x00'}
    model['globalData']['seller']['contactName']='SECRET'
    result=parse_alibaba_page(model_page(model),PRODUCT)
    assert result['extraction_status']=='PARTIAL' and 'SECRET' not in json.dumps(result)


@pytest.mark.parametrize('value', ['\x00','\ud800', float('nan'), [], {'private':'value'}])
def test_malformed_retained_values_fail_safely(value):
    model=_model(_tree(capture()),'detailData'); model['globalData']['product']['subject']=value
    result=parse_alibaba_page(model_page(model),PRODUCT)
    assert result['extraction_status']=='PARSE_FAILED' and set(result)=={'source_url','extraction_status','reason'}


@pytest.mark.parametrize('body,status', [
    ('<punish-component></punish-component><script>window._config_={captcha:true,baxia:true};</script>','BLOCKED'),
    ('<div id="nc-container"></div>','BLOCKED'), ('<title>Access denied</title>','BLOCKED'),
    ('<title>Sign in</title><form><input type="password"></form>','AUTH_REQUIRED'),
    ('<form><input type="password"></form>','AUTH_REQUIRED'), ('<body>Unavailable</body>','PARSE_FAILED')])
def test_access_and_changed_content_have_no_snapshot(body,status):
    result=parse_alibaba_page(body,PRODUCT)
    assert result['extraction_status']==status and 'supplier_data' not in result


def test_harmless_sign_in_navigation_and_security_scripts_do_not_block():
    html=capture().replace('<body>','<body><nav>Sign in Please log in</nav><script>var sdk="captcha baxia AWSC x5sec";</script>')
    assert parse_alibaba_page(html,PRODUCT)['extraction_status']=='PARTIAL'
    assert parse_alibaba_page(capture()+'<punish-component></punish-component>',PRODUCT)['extraction_status']=='BLOCKED'


@pytest.mark.parametrize('title,status', [('Sign in','AUTH_REQUIRED'),('Login required','AUTH_REQUIRED'),('Access denied','BLOCKED'),('Security verification','BLOCKED')])
def test_explicit_gate_titles_override_usable_or_stale_evidence(title,status):
    result=parse_alibaba_page(capture().replace('<head>','<head><title>'+title+'</title>'),PRODUCT)
    assert result['extraction_status']==status and 'supplier_data' not in result
    assert parse_alibaba_page(capture()+'<form><input type="password"></form>',PRODUCT)['extraction_status']=='PARTIAL'


def test_saved_from_comment_and_unrelated_cards_cannot_establish_identity():
    assert parse_alibaba_page('<!-- saved from '+PRODUCT+' --><h1>Unrelated product</h1>',PRODUCT)['extraction_status']=='PARSE_FAILED'


def test_valueless_html_attributes_do_not_escape_failure_contract():
    assert parse_alibaba_page(capture()+'<link rel><meta property><script type>var sdk=true;</script><div style>Public</div>',PRODUCT)['extraction_status']=='PARTIAL'
    html=capture()+'<div class="module_unifed_company_card"><a href>Unusable hint</a></div>'
    result=parse_alibaba_page(html,PRODUCT)
    assert result['extraction_status']=='PARSE_FAILED' and 'supplier_data' not in result


def test_sanitized_observed_challenge_fixture():
    html=(Path(__file__).parent/'fixtures'/'alibaba_access_challenge.html').read_text(encoding='utf-8')
    assert parse_alibaba_page(html,PRODUCT)=={'source_url':PRODUCT,'extraction_status':'BLOCKED','reason':'ACCESS_CHALLENGE'}


def test_profile_duplicate_modules_and_ambiguous_assignments_fail():
    model=_model(_tree(capture(True)), 'shopBizData')
    model['pageModuleMap'].append(model['pageModuleMap'][0])
    assert parse_alibaba_page(model_page(model,True),PROFILE)['extraction_status']=='PARSE_FAILED'
    assert parse_alibaba_page(capture(True)+capture(True),PROFILE)['extraction_status']=='PARSE_FAILED'


def test_jsonld_sku_conflict_cannot_override_main_product():
    html=capture().replace('"sku": "1600147809763"','"sku": "1"')
    assert parse_alibaba_page(html,PRODUCT)['extraction_status']=='PARSE_FAILED'


@pytest.mark.parametrize('target,status,reason', [
    (PRODUCT.replace('100-Cotton','Cotton'),'PARTIAL',None), (PRODUCT.replace('1600147809763','1'),'BLOCKED','SOURCE_MISMATCH'),
    (PROFILE,'BLOCKED','SOURCE_MISMATCH'), ('https://evil.test/','BLOCKED','UNSAFE_REDIRECT'),
    ('https://login.alibaba.com/login.htm?redirect=1','AUTH_REQUIRED','LOGIN_REQUIRED'),
    ('https://login.alibaba.com:443/login.htm','BLOCKED','UNSAFE_REDIRECT')])
def test_fetch_redirects_preserve_identity_and_never_contact_rejected_target(target,status,reason):
    calls=[]
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(302,headers={'location':target}) if len(calls)==1 else httpx.Response(200,headers={'content-type':'text/html'},text=capture())
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=extract_alibaba(PRODUCT,client=client,dns_check=lambda host:True)
    assert result['extraction_status']==status and result.get('reason')==reason
    assert len(calls)==(2 if reason is None else 1)


@pytest.mark.parametrize('http_status,body,status',[(401,'','AUTH_REQUIRED'),(403,'','BLOCKED'),(429,'','BLOCKED'),(503,'<punish-component></punish-component>','BLOCKED'),(200,'OVERSIZE','PARSE_FAILED')])
def test_access_walls_and_oversize_never_retry(http_status,body,status):
    body = 'x'*(MAX_HTML_BYTES+1) if body == 'OVERSIZE' else body
    calls=[]
    with httpx.Client(transport=httpx.MockTransport(lambda req:calls.append(req) or httpx.Response(http_status,headers={'content-type':'text/html'},text=body))) as client:
        result=extract_alibaba(PRODUCT,client=client,dns_check=lambda host:True)
    assert result['extraction_status']==status and len(calls)==1 and 'supplier_data' not in result


def test_transient_retries_are_bounded_and_private_dns_never_requests():
    calls=[]; delays=[]
    with httpx.Client(transport=httpx.MockTransport(lambda req:calls.append(req) or httpx.Response(503))) as client:
        result=extract_alibaba(PRODUCT,client=client,dns_check=lambda host:True,sleep=delays.append)
        assert result['reason']=='UPSTREAM_UNAVAILABLE' and len(calls)==3 and delays==[0.5,1.0]
        calls.clear()
        result=extract_alibaba(PRODUCT,client=client,dns_check=lambda host:False)
        assert result['reason']=='UNSAFE_DESTINATION' and calls==[]
    with pytest.raises(UnsafeDestination): PublicOnlyBackend(allowed_hosts=('www.alibaba.com',)).connect_tcp('127.0.0.1',443)


def test_worker_routes_alibaba_after_fixture(monkeypatch):
    calls=[]
    monkeypatch.setattr('backend.worker.main.extract_alibaba',lambda url,**kw:calls.append((url,kw)) or {'ok':True})
    assert _compute_claim({'source_url':PRODUCT,'mode':'GUEST_PUBLIC'},None)=={'ok':True}
    assert calls==[(PRODUCT,{'analysis_mode':'GUEST_PUBLIC'})]


@pytest.mark.parametrize('profile',[False,True])
def test_default_transport_pins_public_ip_and_hostname_tls(monkeypatch,profile):
    import socket
    import httpcore
    body=capture(profile).encode(); calls=[]
    class Socket:
        response=b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body
        def read(self, maximum, timeout=None):
            data,self.response=self.response[:maximum],self.response[maximum:]; return data
        def write(self,data,timeout=None): calls.append(('request',data))
        def start_tls(self,context,server_hostname=None,timeout=None): calls.append(('tls',server_hostname)); return self
        def get_extra_info(self,info): return None
        def close(self): pass
    def connect(_self,host,port,*args,**kwargs): calls.append(('connect',host,port)); return Socket()
    monkeypatch.setattr(socket,'getaddrinfo',lambda *args,**kwargs:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))])
    monkeypatch.setattr(httpcore.SyncBackend,'connect_tcp',connect)
    result=extract_alibaba(PROFILE if profile else PRODUCT)
    assert result['extraction_status']=='PARTIAL'
    assert ('connect','93.184.216.34',443) in calls and ('tls','dgxuandele.en.alibaba.com' if profile else 'www.alibaba.com') in calls


def test_failed_stream_discarded_and_shared_deadline_limits_retries():
    class Broken(httpx.SyncByteStream):
        def __iter__(self):
            yield capture().encode()
            raise httpx.ReadError('private transport details')
    calls=[]; delays=[]
    with httpx.Client(transport=httpx.MockTransport(lambda req:calls.append(req) or httpx.Response(200,headers={'content-type':'text/html'},stream=Broken()))) as client:
        result=extract_alibaba(PRODUCT,client=client,dns_check=lambda host:True,sleep=delays.append)
    assert result['extraction_status']=='PARSE_FAILED' and len(calls)==3 and 'supplier_data' not in result
    now=[0]
    def handler(req):
        now[0]=26
        return httpx.Response(200,headers={'content-type':'text/html'},text=capture())
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=extract_alibaba(PRODUCT,client=client,dns_check=lambda host:True,clock=lambda:now[0])
    assert result['extraction_status']=='TIMEOUT' and 'supplier_data' not in result


@pytest.mark.parametrize('platform', ['1688', 'TAOBAO', 'ALIBABA'])
def test_all_anonymous_adapters_decline_retry_cookies(monkeypatch, platform):
    from backend.tests.test_browser_fallback import fixture, ADAPTERS
    source, html = fixture(platform)
    adapter = ADAPTERS[platform][0]
    calls=[]; clients=[]
    def handler(request):
        calls.append(request)
        if len(calls)==1:
            return httpx.Response(503,headers={'set-cookie':'source_session=PRIVATE_COOKIE; Path=/; Secure'})
        return httpx.Response(200,headers={'content-type':'text/html','set-cookie':'source_session=PRIVATE_COOKIE; Path=/; Secure'},text=html)
    monkeypatch.setattr('backend.app.extraction.fetch._public_transport',lambda **kwargs:httpx.MockTransport(handler))
    constructor=httpx.Client
    def client_factory(**kwargs):
        instance=constructor(**kwargs); clients.append(instance); return instance
    monkeypatch.setattr('backend.app.extraction.fetch.httpx.Client',client_factory)
    assert adapter(source,dns_check=lambda host:True,sleep=lambda _:None)['extraction_status']=='PARTIAL'
    assert len(calls)==2 and all('cookie' not in request.headers for request in calls)
    assert list(clients[0].cookies.jar)==[]


@pytest.mark.parametrize('platform', ['1688', 'TAOBAO', 'ALIBABA'])
def test_all_injected_anonymous_clients_clear_cookies_and_decline_retry_state(platform):
    from backend.tests.test_browser_fallback import fixture, ADAPTERS
    source, html = fixture(platform)
    adapter = ADAPTERS[platform][0]
    calls=[]
    def handler(request):
        calls.append(request)
        if len(calls)==1:
            return httpx.Response(503,headers={'set-cookie':'source_session=PRIVATE_COOKIE; Path=/; Secure'})
        return httpx.Response(200,headers={'content-type':'text/html','set-cookie':'source_session=PRIVATE_COOKIE; Path=/; Secure'},text=html)
    with httpx.Client(transport=httpx.MockTransport(handler),cookies={'initial':'PRIVATE_COOKIE'},headers={'Cookie':'explicit=PRIVATE_COOKIE'}) as client:
        assert adapter(source,client=client,dns_check=lambda host:True,sleep=lambda _:None)['extraction_status']=='PARTIAL'
        assert len(calls)==2 and all('cookie' not in request.headers for request in calls)
        assert list(client.cookies.jar)==[]


def test_default_anonymous_adapter_declines_source_cookies(monkeypatch):
    calls=[]; clients=[]
    def handler(request):
        calls.append(request)
        if len(calls)==1:
            return httpx.Response(302,headers={'location':PRODUCT.replace('100-Cotton','Cotton'), 'set-cookie':'source_session=PRIVATE_COOKIE; Path=/; Secure'})
        return httpx.Response(200,headers={'content-type':'text/html','set-cookie':'source_session=PRIVATE_COOKIE; Path=/; Secure'},text=capture())
    monkeypatch.setattr('backend.app.extraction.fetch._public_transport',lambda **kwargs:httpx.MockTransport(handler))
    constructor=httpx.Client
    def client_factory(**kwargs):
        instance=constructor(**kwargs); clients.append(instance); return instance
    monkeypatch.setattr('backend.app.extraction.fetch.httpx.Client',client_factory)
    assert extract_alibaba(PRODUCT,dns_check=lambda host:True)['extraction_status']=='PARTIAL'
    assert len(calls)==2 and all('cookie' not in request.headers for request in calls)
    assert list(clients[0].cookies.jar)==[]


def test_injected_anonymous_client_clears_existing_cookies_and_declines_redirect_state():
    calls=[]
    def handler(request):
        calls.append(request)
        if len(calls)==1:
            return httpx.Response(302,headers={'location':PRODUCT.replace('100-Cotton','Cotton'),'set-cookie':'source_session=PRIVATE_COOKIE; Path=/; Secure'})
        return httpx.Response(200,headers={'content-type':'text/html','set-cookie':'source_session=PRIVATE_COOKIE; Path=/; Secure'},text=capture())
    with httpx.Client(transport=httpx.MockTransport(handler),cookies={'initial':'PRIVATE_COOKIE'},headers={'Cookie':'explicit=PRIVATE_COOKIE'}) as client:
        assert extract_alibaba(PRODUCT,client=client,dns_check=lambda host:True)['extraction_status']=='PARTIAL'
        assert len(calls)==2 and all('cookie' not in request.headers for request in calls)
        assert list(client.cookies.jar)==[]
