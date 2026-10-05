# Source units and qualified claims — 2026-10-06

Approved offline correction completed. Prompt vi-text.v8 distinguishes tissue pulls (抽 / lượt rút) from sheets (张 / tờ) and layers without inferring packaging or multiplying quantities. It preserves member-group qualifiers such as 88VIP and the positive-review metric instead of broad satisfaction, retains a reviewer's continued use without inventing repeat purchases, and includes title price/shipping wording as an attributed unverified seller claim. Title claims remain separate from displayed starting prices, selected variants and unknown final fees. Compact limits and prior grounding guidance remain.

Only prompt guidance and its version changed in production code. Source projection, text-report.v2 schema, vi-prose.v4 validator, saved-evidence.v1 pipeline, model, deadlines, token limits, privacy and confidence semantics are unchanged. No semantic entailment validator was added. The local v7 accepted text supplied concrete evidence for the correction; missing rejected cloud wording still cannot be assigned a cause.

The authentic Taobao fake-provider settlement test now retains pull count/layers, title shipping attribution, qualified prices, product time window, shop/member metrics and both accessible review meanings. It asserts source values survive the minimized projection with stable E1–E6 references, excludes private fields, preserves generated findings and source data, labels confidence as uncalibrated, and prevents a second dispatch. Four independent differently worded and numbered Vietnamese clauses probe full-validator compatibility. No prompt-substring tests claim model effectiveness.

Independent quick review found one medium verification gap: the corrected clauses had only been settled in MemoryStore, while the authentic PostgreSQL reopen test used earlier unqualified text. Patched that database test to persist/reopen corrected pull-count, title shipping, 88VIP and continued-use statements, qualified prices and the other review, while retaining its exact-source quotation control. It asserts identical findings, resolved citations, v8 metadata, confidence provenance, repeated owned reads, source preservation, owner isolation and one dispatch. Reviewer rechecked the patch and reported no remaining findings. Thorough review lenses were skipped for this small correction; nothing deferred.

Verification: 309 focused tests pass locally and in the final non-root backend image with network disabled and scripts mounted read-only; 13 isolated PostgreSQL fake-provider tests pass after the review patch. Existing unrelated Starlette/httpx deprecation warning only. Final tested local image ID: sha256:107b7e1178af2ca36f5753e89dd672cc8f1a0e417db4472cd20501a0b95cd605, user vct. Verification artifact: tmp/story31-grounding-v8-offline-verification.json.

Prior local READY analysis 62bdcdb7-d56b-4834-9402-c2f4d82b72c3 reopens identically, retains prompt vi-text.v7 / validator vi-prose.v4 and one dispatch. Canonical report hash remains 67647f8a0499c02be1f50526b4645ec2512417209fd6935a78fe1466886c9f8d. No saved report was rewritten or regenerated. No paid request, rejected-content capture, registry push, cloud deployment or Git push ran; reservations remain combined $0.05554185. Dev remains v7/v4 at API18/dispatcher27.

The next actual generated report must meet this semantic rubric in addition to existing citation, confidence, ownership and cost checks:

| Source meaning | Required interpretation | Failing counterexample |
|---|---|---|
| 100抽, 3层 | Title states 100 pulls and three layers | 100 sheets, 300 sheets, or invented box count |
| 88VIP好评率97% | Shop positive-review rate for 88VIP retains population and rate | All-buyer satisfaction rate or product rate |
| 一直都用的这款抽纸 | Reviewer says they continue using this tissue product | Only quality praise, or invented repeated purchases/duration |
| Title 2元包邮 | Unverified seller-title claim of 2 yuan with shipping included, separate from starting prices/final fees | Verified payable price/free shipping, or omission of the title claim |

These fake-provider tests establish compatibility and persistence, not model adherence or passed substantive acceptance. Story 3.1 remains partial. Recommended next step: release the reviewed v8 image to dev with preservation/health checks; scope and authorize any fresh paid acceptance separately. No further paid request is authorized by this offline work.
