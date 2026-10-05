# Offline Vietnamese prose coverage

Scope: approved offline coverage work and supported correction; no paid provider request.

Added backend/tests/fixtures/vietnamese_report_prose.jsonl:33 agent-curated synthetic Vietnamese examples and24 foreign/mixed-language/ambiguous negatives. Language labels do not validate factual claims or supplier safety. Topics cover packaging, paper texture, source-attributed title/review claims, prices/currency, sales/review metrics, shipping/service, evidence coverage/freshness, sample/verification actions and model interpretation confidence. One positive uses decomposed Unicode accents. Existing quotation, injection, confidence/score, citation, credential and truncation/no-retry tests remain in the suite.

Baseline vi-prose.v2 misclassified3 positives (packaging, packaging_touch, decomposed) and0 negatives. Other30 positive examples already passed. Added only six missing packaging vocabulary terms; per-sentence recognition thresholds, diacritic requirements, foreign words/script checks and all report guards preserved. Validation version vi-prose.v3; prompt vi-text.v5 and schema text-report.v2 unchanged. No new runtime dependency, external corpus or private rejected sample used.

All57 corpus cases now pass. All206 focused report tests pass locally and in the built non-root image with networking disabled. These results cover the curated examples, not a calibrated language benchmark, generalization guarantee or substantive live translation acceptance. Previous cloud rejection causes remain unknown because rejected prose was not retained.

Independent quick review found no actionable issues and checked corpus labels/Unicode behavior. All13 isolated PostgreSQL settlement tests also pass, using fake providers only. Dev-release evidence recorded below when complete. Story3.1 remains partial pending a fresh complete accepted owned live report, substantive fixture-grounded interpretation, confidence labeling and identical reopen. No new paid generation, ledger reset, replay or Git push is part of this work. Prior combined retained reservations remain $0.04187730 within $0.09.
