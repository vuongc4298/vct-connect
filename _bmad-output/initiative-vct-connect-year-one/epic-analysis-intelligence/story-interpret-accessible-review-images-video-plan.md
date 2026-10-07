---
title: 'Interpret accessible review images and video'
type: 'story'
ticket: '6'
created: '2026-10-07'
status: 'built'
baseline_revision: 'a6c1eb52e2a80c5cadbc55ee8f383d1619e4c790'
route: 'full'
review: 'thorough'
---

<frozen-after-approval reason="user approved Epic 3 Story 3.6 on 2026-10-07">

## Intent

**Problem:** Text review interpretation exists, but accessible review images/video evidence cannot yet be compared with review claims in a structured, auditable way.

**Approach:** Add a provider-neutral multimodal contract and a Story 3.6 media interpreter. Approved images are sent as bounded data URLs. Video is intentionally represented as approved sampled image frames carrying timestamps because the public YEScale material does not define a stable direct-video chat payload. The model returns structured Vietnamese media-consistency findings.

## Contract

- schema: review-media-interpretation.v1
- media types: IMAGE and VIDEO_FRAME
- access states: ACCESSIBLE, MISSING, UNSUPPORTED
- consistency: SUPPORTS, PARTIALLY_SUPPORTS, CONTRADICTS, CANNOT_DETERMINE
- every media item keeps media_id, review_evidence_id, private_ref, access status, MIME type, optional video timestamp, and SHA-256 fingerprint when accessible
- model findings may cite only accessible supplied media IDs and must preserve the media-to-review link and video-frame timestamp
- missing/unsupported media is CANNOT_DETERMINE with confidence 0 and causes no provider call when no accessible media exists
- text-only paths continue without a media dependency

## Privacy and retention boundary

Raw image/frame payloads are transient provider inputs only. Story 3.6 run provenance stores opaque private references and content fingerprints, not data URLs or media bytes. The module rejects arbitrary public/external URLs and accepts only bounded PNG/JPEG/WebP data URLs prepared by trusted backend code.

No media database migration or retention policy is added here. Source terms and final media-retention rules remain open. Story 3.9 owns worker integration after permitted media storage/access policy is finalized.

## Provider boundary

YEScale remains behind the backend-only provider abstraction. The adapter uses the OpenAI-compatible chat-completions content structure for approved image inputs. No live provider request is required in CI; MockTransport/fake providers verify request shape and structured-output validation.

Direct video upload is deliberately not assumed. An approved video must be sampled into timestamped frames by a later trusted media-preparation layer, preserving the uncertainty that events between frames are not observed.

## Safety boundaries

**Always:** Report uncertainty, preserve private provenance, bind media back to its review evidence, retain sampled-video timestamps, and fail closed on malformed or missing media.

**Never:** Guess inaccessible media content, infer events between sampled video frames, let review media create a supplier risk score directly, claim an individual review is fake, persist raw media inside model-run JSON, or fetch arbitrary model-visible URLs.

## Verification

- accessible image and timestamped video-frame fixtures produce Vietnamese consistency findings
- inaccessible media is explicitly missing/CANNOT_DETERMINE without a provider call
- text-only fixture still completes with no media dependency
- raw data URLs never appear in run input_payload/provenance
- model citations to unknown/inaccessible media fail
- model cannot change review linkage or video timestamps
- omitted model findings fail to CANNOT_DETERMINE rather than being guessed
- YEScale mock verifies OpenAI-compatible image content and request provenance
