---
title: 'Verify report evidence and access boundaries'
type: 'story'
ticket: '5'
created: '2026-10-08'
status: 'built'
baseline_revision: 'b92c06c6b3744fc3aa3ceaa452c6ea4595ed637c'
route: 'full'
review: 'thorough'
---

## Intent

**Problem:** The reporting pipeline is functional, but the final report path needs explicit verification that material claims remain traceable, stale evidence is visible, contradictory evidence stays represented as uncertainty/risk rather than being flattened, and guest/customer access boundaries cannot be crossed.

**Approach:** Harden report construction and presentation at the provenance boundary, then exercise the resulting behavior with focused backend/auth/frontend fixtures.

## Evidence integrity

Newly generated reports fail closed if a material risk or positive finding cites an evidence ID that is absent from the report evidence set. This prevents a buyer-facing material claim from being persisted with a broken provenance chain.

Risk-dimension `evidence_ids` are scorer signal references, not necessarily raw evidence IDs. The UI now hyperlinks only IDs that actually exist in the report evidence set. Non-resolving scorer IDs are labeled as internal `tham chiếu chấm điểm` rather than being rendered as fake source anchors.

For defensive compatibility with historical/damaged report payloads, a finding-level evidence ID that is absent from the payload is rendered visibly as `thiếu nguồn`, not as a clickable anchor.

## Freshness

A shared frontend freshness classifier marks report snapshots stale at 30 days.

Full reports show:
- the actual collection timestamp;
- an explicit stale-data warning when the snapshot is 30+ days old;
- `DỮ LIỆU CŨ` on evidence freshness labels.

Guest previews show the collection timestamp and the same stale-state warning without exposing protected report content.

Stale evidence does not change Risk/Confidence/Coverage in the browser; it is a buyer-visible provenance warning only.

## Contradiction and missing data

- contradictory review media remains a material risk only when the persisted `MEDIA_CONSISTENCY` finding is `CONTRADICTS`;
- the contradiction fixture must resolve both the media and linked review evidence IDs;
- missing source fields remain in `missing_data` and trigger the existing limitation that unknown values are not assumed safe;
- `INSUFFICIENT_INFORMATION` behavior from Stories 4.2–4.4 remains unchanged.

## Access boundaries

- full `report.v1` remains CUSTOMER/owner-only; a guest key cannot authenticate to it;
- guest preview remains guest-browser-key scoped; a customer bearer token does not substitute for the guest key;
- foreign guest keys receive the same non-disclosing 404 behavior.

## Verification

- dangling material finding evidence causes report construction to fail;
- contradictory media stays evidence-traceable;
- missing source data is explicitly preserved as unknown;
- stale full/guest snapshots are visibly labeled;
- internal scoring references cannot become fake evidence links;
- historical missing evidence links are visibly marked;
- full/guest authorization boundaries remain disjoint;
- repository CI remains the merge gate.
