---
title: 'Render the full Vietnamese report'
type: 'story'
ticket: '2'
created: '2026-10-08'
status: 'built'
baseline_revision: 'e62b42da6f37fda72566abcc93c8d5c955924388'
route: 'full'
review: 'thorough'
---

## Intent

**Problem:** Story 4.1 persists an owner-authorized `report.v1`, but the signed-in web workspace still needs a buyer-readable Vietnamese presentation of that payload.

**Approach:** Fetch the immutable report through the authenticated web proxy and render the persisted values directly. Keep Risk, Confidence, Coverage, missing information, source freshness, and evidence linkage visible. Do not recompute scoring or invent report meaning in the frontend.

## UI contract

The full report presents:

- supplier/platform identity and extraction time;
- overall Risk separately from Confidence and Coverage;
- all seven frozen `v0.1.0` risk dimensions;
- factory/trader likelihood and confidence;
- review-analysis summary;
- evidence-linked key risks and positive signals;
- recommended pre-order actions;
- missing source fields, missing risk dimensions, and uncertainties;
- limitations and source/evidence cards with stable evidence anchors.

The frontend consumes `report.v1` as produced by Story 4.1. It does not call YEScale, recalculate risk, infer missing values, or turn absent evidence into a positive signal.

## Risk and uncertainty presentation

`INSUFFICIENT_INFORMATION` is a first-class state. Its overall score is shown as unavailable rather than low risk, and the interface explicitly states that insufficient evidence must not be interpreted as safety.

The seven scoring dimensions remain exactly:

- PRODUCT_QUALITY
- SUPPLIER_IDENTITY
- DELIVERY
- REVIEW_MANIPULATION
- AFTER_SALES
- PRICING
- COMMUNICATION

Unknown dimension risk remains visibly unknown.

## Evidence traceability and safety

Each finding evidence ID links to the corresponding evidence card. Evidence cards show source kind, source field when present, and the report snapshot freshness. The outbound source link is passed through the existing safe-source URL guard; unsafe/private URLs are not rendered as clickable links.

## Workspace integration

When a signed-in analysis reaches `COMPLETED`, the workspace requests its persisted report. The report endpoint remains owner-only. A missing/unavailable report produces a clear fallback message and preserves the extraction-evidence view rather than fabricating a report.

Guest preview remains outside this story and is owned by Story 4.3.

## Verification

- component fixture renders real Risk, Confidence, Coverage, scoring version, factory/trader values, review summary, actions, and evidence anchors;
- insufficient-information fixture never renders a low-risk label or default numeric risk;
- unsafe source URLs do not become outbound links;
- frozen Pricing and Communication dimensions render Vietnamese labels rather than raw enum names;
- report loading/error integration preserves existing extraction evidence fallback;
- repository CI remains the merge gate.
