# Offline Vietnamese prose coverage

Scope: approved offline coverage work and supported correction; no paid provider request.

Added backend/tests/fixtures/vietnamese_report_prose.jsonl:33 agent-curated synthetic Vietnamese examples and24 foreign/mixed-language/ambiguous negatives. Language labels do not validate factual claims or supplier safety. Topics cover packaging, paper texture, source-attributed title/review claims, prices/currency, sales/review metrics, shipping/service, evidence coverage/freshness, sample/verification actions and model interpretation confidence. One positive uses decomposed Unicode accents. Existing quotation, injection, confidence/score, citation, credential and truncation/no-retry tests remain in the suite.

Baseline vi-prose.v2 misclassified3 positives (packaging, packaging_touch, decomposed) and0 negatives. Other30 positive examples already passed. Added only six missing packaging vocabulary terms; per-sentence recognition thresholds, diacritic requirements, foreign words/script checks and all report guards preserved. Validation version vi-prose.v3; prompt vi-text.v5 and schema text-report.v2 unchanged. No new runtime dependency, external corpus or private rejected sample used.

All57 corpus cases now pass. All206 focused report tests pass locally and in the built non-root image with networking disabled. These results cover the curated examples, not a calibrated language benchmark, generalization guarantee or substantive live translation acceptance. Previous cloud rejection causes remain unknown because rejected prose was not retained.

Independent quick review found no actionable issues and checked corpus labels/Unicode behavior. All13 isolated PostgreSQL settlement tests also pass, using fake providers only. Dev-release evidence recorded below when complete. Story3.1 remains partial pending a fresh complete accepted owned live report, substantive fixture-grounded interpretation, confidence labeling and identical reopen. No new paid generation, ledger reset, replay or Git push is part of this work. Prior combined retained reservations remain $0.04187730 within $0.09.


## Verified dev release

Code commit a5450c00c4348c177813afb85df9040deb4b38b2, local only. Backend digest sha256:133854cae873213dd430f7757dc2f2ae2a979753070791401e7e0669e633e6a3. API vct-connect-dev-api--0000015 and dispatcher vct-connect-dev-dispatcher--0000024 are Healthy / Provisioned / Running. Analysis and migration job templates use the same digest. Effective environment settings, secret references, model, deadline, output cap and web image were preserved.

Read-only ledger verification still shows8 retained cloud dispatches / $0.01802520 reserved, zero pending. Local reservations unchanged at $0.02385210; combined $0.04187730. No provider request was dispatched by this offline work. Prior failed/uncertain jobs and private Git-excluded captures preserved; no accepted vi-prose.v3 live report exists yet. Tracked tree clean after recording release evidence; operational build/review artifacts remain local.


The subsequent separately approved single live acceptance ran once under vi-prose.v3: analysis d44fb0b5-b30b-4830-8723-e40b8e77ff49 completed at937 output tokens but failed UNSUPPORTED_SCORE/self_reported_confidence.basis. No rejected cloud prose retained, so exact wording/true violation versus false positive remains unknown; no retry ran. Owned reopening preserves the failure and source. Displayed charge $0.0006, invoice actual unknown; cloud9/$0.02054175, pending0; combined retained reserves $0.04439385. Authorization consumed, Story3.1 still partial. Next: offline confidence-basis prompt/guard contract coverage before any separately approved bounded live diagnostic. See story31-screen3-live-acceptance-result.md. No code changes or Git push in this acceptance.
