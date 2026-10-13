from backend.app.intelligence.assessment import build_assessment
from backend.app.intelligence.assessment_policy import supplier_score_inputs
from backend.app.intelligence.interpretation import interpret_supplier_data
from backend.tests.test_complete_assessment import FakeProvider, supplier_fixture
from backend.tests.test_supplier_dimension_scoring import assessment, provider_with


def sample(count=10):
    descriptions = ['blue stitching', 'red handle', 'folding mechanism', 'black fabric',
                    'green strap', 'small button', 'large canopy', 'wooden grip',
                    'white lining', 'metal frame']
    return [{'text': 'Buyer describes ' + text, 'rating': 4} for text in descriptions[:count]]


def test_ten_reviews_support_preliminary_credibility_without_overall_safety():
    data = supplier_fixture() | {'reviews': sample()}
    bundle = build_assessment(data, provider=FakeProvider(), model='fixture')
    dim = next(x for x in bundle.risk.dimensions if x.dimension == 'REVIEW_MANIPULATION')
    assert dim.risk == 35
    assert 0 < dim.effective_confidence <= 0.45
    evidence = next(x for x in bundle.evidence if x['evidence_id'] == 'review-sample:credibility')
    assert len(evidence['payload']['evidence_ids']) == 10
    assert evidence['payload']['independently_verified'] is False
    assert bundle.risk.scoring_version == 'v0.2.1'
    assert bundle.risk.overall_risk is None
    assert 'AFTER_SALES' in bundle.risk.missing_dimensions


def test_nine_stay_unknown_and_duplicates_override_clean_sample():
    for reviews, expected in [(sample(9), None), ([{'text': 'Excellent product'}] * 10, 100)]:
        bundle = build_assessment(supplier_fixture() | {'reviews': reviews}, provider=FakeProvider(), model='fixture')
        assert next(x for x in bundle.risk.dimensions if x.dimension == 'REVIEW_MANIPULATION').risk == expected
        assert not any(x['evidence_id'] == 'review-sample:credibility' for x in bundle.evidence)


def test_one_specific_after_sales_complaint_supports_bounded_concern():
    data = supplier_fixture() | {'reviews': [{'text': 'Refund refused after a defective item'}]}
    run = interpret_supplier_data(data, provider=provider_with(
        assessment('AFTER_SALES', 'HIGH', 'reviews', 'Refund refused')), model='fixture')
    dimensions, evidence = supplier_score_inputs(run)
    assert dimensions[0].signals[0].severity == 80
    assert dimensions[0].confidence == 0.4
    assert evidence[0]['payload']['preliminary'] is True


def test_policy_scores_but_one_positive_review_does_not_generalize():
    data = supplier_fixture() | {'company_information': {'returns': 'Return within 7 days'}}
    run = interpret_supplier_data(data, provider=provider_with(
        assessment('AFTER_SALES', 'LOW', 'company_information', 'Return within 7 days')), model='fixture')
    assert supplier_score_inputs(run)[0][0].confidence == 0.6
    data['reviews'] = [{'text': 'Support promptly refunded my order'}]
    run = interpret_supplier_data(data, provider=provider_with(
        assessment('AFTER_SALES', 'LOW', 'reviews', 'Support promptly refunded')), model='fixture')
    assert supplier_score_inputs(run) == ([], [])
