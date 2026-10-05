# Evidence-supported shipping/service screen correction

One approved local diagnostic consumed under $0.01; no post-correction paid acceptance yet.

Diagnostic analysis 389ab9bb-b4ad-43c7-890a-84be838eaa9a, snapshot 7b6c370a-346b-463c-9e1b-a587e5a5e3c1, dispatch 538ce92d-15f0-49f3-b7ae-25b1af417abb, request 20261005200102344098824W2738bvD. FAILED / INVALID_OUTPUT / NON_VIETNAMESE_PROSE / findings.text. Strict schema passed. Prompt vi-text.v5; exact expected model deepseek-v4-1-flash-260910, thinking disabled, 120-second deadline and 2400 output cap unchanged. Input1597/output943 tokens, latency21812ms; reservation $0.00251655; usage estimate $0.00080535; displayed billing charge $0.0006, rounded balance $0.0828. Actual invoice cost unknown/null. Source extraction preserved, exactly one dispatch, no retry/replay.

The first retained field is Vietnamese seller-attributed shipping/service wording. The small lexicon recognized13/28 words against14 required. Missing ordinary shipping/service words caused this new local false positive. The earlier cloud rejection has no retained prose and cannot be retroactively assigned this cause.

Added only the evidenced vocabulary, preserving thresholds, per-sentence cues and foreign script/word rejection. Added validation_version vi-prose.v2 metadata; compact prompt remains vi-text.v5, report schema remains text-report.v2. Retained exact field now passes offline. Two synthetic equivalent Vietnamese examples and foreign-language negatives added; rejected prose remains private/Git-excluded. All149 report tests pass locally and in the non-root image without networking; independent quick review found no concrete issues.

Local code commit2124b19537a96a1447be153cc45371136200ba63, not pushed. Backend digest sha256:0648a30832e6206f312bc9b99c9662b1d6fc6e9467a10d006e643b011f91ffc9. Dev release completed. API vct-connect-dev-api--0000014 and dispatcher vct-connect-dev-dispatcher--0000023 are Healthy / Provisioned / Running; analysis and migration job templates use the same digest. Effective settings, secrets and web image preserved. Read-only cloud preflight: seven retained dispatches / $0.01550865 reserved, zero pending.

Combined retained reservations after diagnostic: cloud $0.01550865 plus local $0.02385210 = $0.03936075, within $0.09. Single diagnostic authorization consumed. Story3.1 still needs a complete accepted owner-scoped live report, substantive fixture-grounded interpretation, confidence labeling and identical reopen. No further paid request is included in this completed diagnostic.

A separate one-request owned cloud acceptance authorization has been requested after the reviewed release. It is pending and no additional provider request has run. The exact local diagnostic failure remains preserved, not relabeled or replayed.
