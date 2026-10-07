---
title: 'Compute versioned Risk, Confidence, and Coverage'
type: 'story'
ticket: '5'
created: '2026-10-07'
status: 'built'
baseline_revision: 'bdcb0c7e97184f31afed78eb0ae4838d2780f4fb'
route: 'full'
review: 'thorough'
---

<frozen-after-approval reason="user/product owner approved proceeding with Epic 3 Story 3.5 on 2026-10-07">

## Intent

**Problem:** Stories 3.2-3.4 produce review and identity evidence, but VCT Connect still lacks the deterministic, versioned supplier-risk engine defined in Technical Specification section 14.

**Approach:** Implement scoring version v0.1.0 with seven fixed risk-dimension weights, reliability-weighted signal aggregation, dimension confidence, separate overall confidence and data coverage, the documented Low/Moderate/High thresholds, insufficient-information gates, review-manipulation confidence adjustments, and a conservative critical-floor policy.

## Source-locked scoring rules

Technical Specification section 14 defines:

- Product Quality 25%
- Supplier Identity 15%
- Delivery 15%
- Review Manipulation 15%
- After-sales 15%
- Pricing 10%
- Communication 5%
- dimension risk = sum(signal importance * reliability * severity) / sum(signal importance * reliability)
- overall risk = sum(dimension weight * dimension confidence * dimension risk) / sum(dimension weight * dimension confidence)
- confidence contributions: data coverage 40%, source reliability 25%, sample adequacy 20%, data freshness 15%
- LOW 0-34, MODERATE 35-64, HIGH 65-100
- INSUFFICIENT INFORMATION when coverage <45% OR confidence <40%
- missing evidence is UNKNOWN, never zero risk
- review manipulation reduces confidence in review-derived Quality, Delivery, and After-sales evidence
- every assessment stores scoring_version

## Product-owner-approved conservative critical policy

The technical specification requires strict critical evidence rules but deliberately does not supply numerical eligibility. For v0.1.0, a signal can impose a minimum overall risk floor of 65 only when all conditions hold:

1. signal is explicitly marked as a critical candidate;
2. severity >= 90/100;
3. reliability >= 0.90;
4. source is VERIFIED_DOCUMENT;
5. evidence is independently verified;
6. at least two corroborating evidence items are recorded;
7. signal is not review-derived.

One angry or ambiguous review can therefore never trigger a critical floor, even if its model severity is high. Failing any eligibility rule fails closed and applies no override.

## Review manipulation adjustment

For Product Quality, Delivery, and After-sales only:

effective_dimension_confidence =
base_dimension_confidence * (1 - review_derived_share * review_manipulation_fraction * 0.50)

This makes the maximum confidence reduction 50% when the dimension is entirely review-derived and Review Manipulation risk is 100. Non-review evidence is not downweighted by review manipulation.

This adjustment is an explicit v0.1.0 engineering heuristic and must be calibrated during the trial.

## Boundaries & Constraints

**Always:** Keep Risk, Confidence, and Coverage separate. Preserve unknown/missing dimensions. Version all scoring behavior. Keep signal evidence IDs. Make the same fixed input reproduce the same output.

**Never:** Let an LLM directly choose the final risk score. Do not treat trader status as risk. Do not convert absent evidence into zero risk. Do not let a single review trigger a critical override. Do not persist worker assessment state yet; Story 3.7 owns durable integration.

</frozen-after-approval>

## Verification

- fixtures lock the seven exact dimension weights and four confidence-factor weights
- reliability-weighted signal formula and confidence-weighted dimension formula reproduce expected values
- 0/34, 35/64, and 65/100 label boundaries are exact
- coverage <45% or confidence <40% returns INSUFFICIENT INFORMATION
- missing dimensions remain null/unknown rather than zero-risk
- manipulation risk reduces only review-derived Quality/Delivery/After-sales confidence
- mixed review/non-review dimensions receive proportional adjustment
- only fully eligible independently verified critical evidence applies the 65 floor
- a single angry/ambiguous review cannot trigger a critical floor
