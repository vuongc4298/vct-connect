---
title: Review private image and video evidence
type: story
ticket: 3
status: in-progress
created: 2026-10-08
---

## Safety-first implementation checkpoint

This story is not complete merely because an image URL can be displayed. The existing
media-intelligence module saves **provenance only** (opaque private refs, hashes and video
frame timestamps); image data URLs are transient and are **not** persisted for replay.
Do not silently expose source URLs, model input, raw image bytes, or external media URLs
to the evaluation API.

The initial migration provides `review_media` and `review_media_annotations` with
per-run/per-review scope, independent per-reviewer annotations, bounded notes and optional
video ranges. These tables contain only private storage keys and hashes, never media bytes,
secrets or remote URLs. Migration 0017 is intentionally a storage foundation; it does
**not** authorize a production media-viewing flow.

## Required to complete

1. Approved private storage with explicit retention, deletion and source-term policy.
2. Trusted ingestion that ties each media item to a persisted run/review ordinal and
   verifies SHA-256, MIME and allowed formats. Do not let clients register arbitrary
   private refs or supply server-side fetch destinations.
3. Signed short-lived **reviewer-bound** access checked again at redemption; no open
   redirect, arbitrary URI fetch, shared public link, or credentials in cache/logs.
4. Blind case API must expose safe metadata only (media ID/type, optional timestamp),
   never model result, storage key, other labels, or model provenance pre-submit.
5. Transactionally save media annotations with the independent text-review label
   before revealing pinned model output; enforce ownership, validity, uniqueness,
   bounds, and video-range consistency.
6. Tests: 401/403, forged ID, cross-review/cross-run, expired/replayed/revoked token,
   missing storage object, invalid MIME/type, and failure to leak model output or media
   through error paths. Include real PostgreSQL migration apply/rollback/reapply.
7. Reviewer UI: image notes, video frame/time-window annotation and independent
   media-consistency judgment; clear evidence-unavailable state. Avoid opening remote
   media URLs directly from the review case.

Production rollout is blocked until item 1 is decided. Keep pilot fixtures private
and ensure no raw media is ever exposed to customer or guest routes.
