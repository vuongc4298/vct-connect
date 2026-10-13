import json
import pytest
from backend.app.extraction.page_context import select_context, matching_context_sections, MAX_CONTEXT_BYTES
from backend.app.intelligence.interpretation import interpret_supplier_data
from backend.app.intelligence.assessment_policy import supplier_score_inputs
from backend.tests.test_browser_html import html_sources
from backend.tests.test_supplier_bundle import selected, normalize, SHOP
from backend.tests.test_complete_assessment import supplier_fixture
from backend.tests.test_supplier_dimension_scoring import assessment, provider_with
from backend.app.reporting.builder import build_report


POLICY = 'Return damaged items within 7 days for a full refund.'
def section(text=POLICY):
    return {'section_id': 'shop:policy', 'page': 'SHOP', 'source_url': SHOP,
            'heading': 'Returns policy', 'text': text, 'html_sha256': 'a' * 64}


def test_html_context_recovers_policy_beyond_old_field_limit_without_fabricating_facts():
    value = selected()
    value['html_sources'] = html_sources(value)
    source = value['html_sources'][1]
    source['html'] = source['html'].replace('Company introduction: wholesaler.', 
        '<p>' + 'Background text. ' * 200 + '</p><p>' + POLICY + '</p>')
    result = normalize(value)
    context = result['supplier_data']['page_context']
    assert any(POLICY in item['text'] for item in context['sections'])
    assert 'UNRELATED_RECOMMENDED_SUPPLIER' not in json.dumps(context)
    assert result['supplier_data']['certifications'] is None
    assert len(result['supplier_data']['completeness_denominator']) == 12
    assert all(item['source_url'] == SHOP for item in context['sections'] if item['page'] == 'SHOP')


def test_context_retrieval_prioritizes_policies_and_bounds_multibyte_payload():
    generic = [section('Generic information ' + '厚' * 900) | {'section_id': str(i)} for i in range(100)]
    packet = select_context(generic + [section()])
    assert packet['sections'][0]['text'] == POLICY
    assert len(json.dumps(packet, ensure_ascii=False).encode()) <= MAX_CONTEXT_BYTES
    assert packet['truncated'] is True
    assert len(packet['sections']) <= 24


def test_context_supported_after_sales_keeps_exact_quote_and_source_provenance():
    data = supplier_fixture() | {'page_context': select_context([section()])}
    provider = provider_with(assessment('AFTER_SALES', 'LOW', 'page_context', POLICY))
    run = interpret_supplier_data(data, provider=provider, model='fixture')
    assert run.input_payload['evidence']['page_context']['sections'][0]['text'] == POLICY
    dimensions, evidence = supplier_score_inputs(run)
    assert dimensions[0].confidence == 0.6
    assert evidence[0]['payload']['context_sources'][0]['source_url'] == SHOP
    assert evidence[0]['payload']['evidence_quotes']['page_context'] == POLICY


@pytest.mark.parametrize('quote', ['shop:policy', SHOP, 'Invented refund guarantee for all orders'])
def test_metadata_and_hallucinated_context_quotes_do_not_score(quote):
    data = supplier_fixture() | {'page_context': select_context([section()])}
    run = interpret_supplier_data(data, provider=provider_with(
        assessment('AFTER_SALES', 'LOW', 'page_context', quote)), model='fixture')
    assert run.interpretation.dimension_assessments[0].severity == 'UNKNOWN'
    assert supplier_score_inputs(run) == ([], [])


def test_generic_service_and_ambiguous_return_rate_do_not_bypass_policy():
    for text in ['Service score 4.0 suggests helpful employees', 'Store return rate is 27% on this supplier']:
        data = supplier_fixture() | {'page_context': select_context([section(text)])}
        run = interpret_supplier_data(data, provider=provider_with(
            assessment('AFTER_SALES', 'LOW', 'page_context', text)), model='fixture')
        assert supplier_score_inputs(run) == ([], [])


def test_large_context_shrinks_before_structured_input_gate_and_preserves_reviews():
    data = supplier_fixture()
    data['page_context'] = {'sections': [section('Return policy ' + '厚' * 5000) | {'section_id': str(i)} for i in range(50)]}
    run = interpret_supplier_data(data, provider=provider_with(), model='fixture')
    assert len(json.dumps(run.input_payload, ensure_ascii=False).encode()) <= 65536
    assert run.input_payload['evidence']['reviews'] == data['reviews']
    assert data['completeness_denominator'] == run.input_payload['completeness_denominator']


def test_context_survives_assessment_and_report_source_projection():
    from backend.app.intelligence.assessment import build_assessment
    data = supplier_fixture() | {'page_context': select_context([section()])}
    item = assessment('AFTER_SALES', 'LOW', 'page_context', POLICY)
    provider = provider_with(item)
    provider.output['positive_signals'].append({'statement_vi': 'Nguồn công bố chính sách đổi trả.',
        'evidence_fields': ['page_context'], 'evidence_quotes': {'page_context': POLICY}, 'confidence': 0.6})
    bundle = build_assessment(data, provider=provider, model='fixture')
    report = build_report(analysis_id='context-report', source_url=data['source_url'],
        snapshot={'normalized_data': data}, assessment={'risk_assessment': bundle.risk.model_dump(mode='json'),
        'supplier_interpretation': bundle.supplier_run.interpretation.model_dump(mode='json')},
        findings=bundle.findings, evidence=bundle.evidence, raw_reviews=[])
    source = next(x for x in report.evidence if x.evidence_id == 'supplier:page_context')
    assert source.payload['value']['sections'][0]['text'] == POLICY
    assert any('supplier:page_context' in x.evidence_ids for x in report.positive_signals)
    assert any('Ngữ cảnh trang' in x for x in report.limitations_vi)


def test_short_chinese_policy_remains_usable_but_metadata_does_not():
    policy = '7天无理由退货'
    value = selected(); value['html_sources'] = html_sources(value)
    value['html_sources'][1]['html'] = value['html_sources'][1]['html'].replace(
        'Company introduction: wholesaler.', '<p>' + policy + '</p>')
    data = normalize(value)['supplier_data']
    assert matching_context_sections(data['page_context'], policy)
    run = interpret_supplier_data(data, provider=provider_with(
        assessment('AFTER_SALES', 'LOW', 'page_context', policy)), model='fixture')
    assert supplier_score_inputs(run)[0][0].confidence == 0.6


def test_local_metric_label_and_value_are_preserved_together():
    value = selected(); value['html_sources'] = html_sources(value)
    value['html_sources'][1]['html'] = value['html_sources'][1]['html'].replace(
        'Company introduction: wholesaler.',
        '<div><div>Return and exchange experience</div><div>4.7</div></div>')
    data = normalize(value)['supplier_data']
    assert matching_context_sections(data['page_context'], 'Return and exchange experience 4.7')


def test_fact_first_context_omits_generic_price_definitions_and_duplicate_moq():
    from backend.app.intelligence.interpretation import _supplier_input, _user_prompt
    data = supplier_fixture()
    data['page_context'] = select_context([
        section('Pre-event price: the standard price excludes platform promotions.') | {'section_id': 'boilerplate'},
        section(str(data['price_information'])) | {'section_id': 'duplicated-price'},
        section(), section() | {'section_id': 'duplicate-policy'},
    ])
    payload = _supplier_input(data)
    sections = payload['evidence']['page_context']['sections']
    assert [item['text'] for item in sections] == [POLICY]
    assert sections[0]['source_url'] == SHOP and sections[0]['html_sha256'] == 'a' * 64
    prompt = _user_prompt(payload)
    assert 'html_sha256' not in prompt and POLICY in prompt
    assert 'Pre-event price:' not in prompt


def test_advertised_product_refund_policy_scores_after_sales_but_generic_product_praise_does_not():
    for quote, expected in [(POLICY, True), ('Excellent comfortable product.', False)]:
        data = supplier_fixture()
        data['products'] = [{'services_display_text': quote}]
        run = interpret_supplier_data(data, provider=provider_with(
            assessment('AFTER_SALES', 'LOW', 'products', quote)), model='fixture')
        dimensions, _ = supplier_score_inputs(run)
        assert bool(dimensions) is expected
        if expected: assert dimensions[0].confidence == 0.6


def test_translated_compensation_policy_can_support_preliminary_after_sales():
    quote = 'Quality discrepancy, guaranteed compensation'
    data = supplier_fixture() | {'page_context': select_context([section(quote)])}
    run = interpret_supplier_data(data, provider=provider_with(
        assessment('AFTER_SALES', 'LOW', 'page_context', quote)), model='fixture')
    assert supplier_score_inputs(run)[0][0].confidence == 0.6


def test_service_leaf_alias_recovers_only_an_exact_captured_policy_quote():
    data = supplier_fixture()
    data['products'] = [{'services_display_text': POLICY, 'description_display_text': 'Price definitions.'}]
    item = assessment('AFTER_SALES', 'LOW', 'products', 'Price definitions.')
    item['evidence_fields'].append('services_display_text')
    item['evidence_quotes']['services_display_text'] = POLICY
    run = interpret_supplier_data(data, provider=provider_with(item), model='fixture')
    assert supplier_score_inputs(run)[0][0].confidence == 0.6
    assert run.interpretation.dimension_assessments[0].evidence_quotes == {'products': POLICY}
    assert run.provider_response.settings['source_field_aliases']['validation'] == 'exact captured service-text quote'


def test_service_leaf_alias_cannot_accept_an_invented_policy():
    data = supplier_fixture()
    data['products'] = [{'services_display_text': POLICY}]
    item = assessment('AFTER_SALES', 'LOW', 'services_display_text', 'All orders refunded forever.')
    with pytest.raises(ValueError, match='schema'):
        interpret_supplier_data(data, provider=provider_with(item), model='fixture')


def test_unverified_positive_protection_alone_is_not_a_material_after_sales_concern():
    data = supplier_fixture()
    quote = 'Quality discrepancy, guaranteed compensation'
    data['products'] = [{'services_display_text': quote}]
    run = interpret_supplier_data(data, provider=provider_with(
        assessment('AFTER_SALES', 'MEDIUM', 'products', quote)), model='fixture')
    assert supplier_score_inputs(run) == ([], [])
