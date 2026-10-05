# Offline language-contract investigation — 2026-10-06

The approved investigation reproduced limitations in vi-prose.v3 without a provider call. Production validation, prompt, deployment, old reports and spending records are unchanged. The exact cause of live analysis0c4823ba-c3ce-4828-aef4-dadc97d2af6e remains unknown because its rejected wording was not retained. Story3.1 substantive acceptance remains open.

Added a synthetic diagnostic fixture and an offline evaluator using both screen_vietnamese and validate_report. The report envelope supplies a valid E1 citation, valid Vietnamese summary/limitations/actions/basis and numeric self-report confidence; no quoted source is supplied. The tool reports direct screening separately from report acceptance, including safe rejection reason/location. It does not call providers or databases, change validation, or silently treat a mismatch as a passing language benchmark. Case labels assess language only, not source truth or safety. Fixture IDs are unique and labels/text types checked.

| Dataset | Vietnamese cases | Foreign/mixed/ambiguous cases | False rejections | False acceptances |
|---|---:|---:|---:|---:|
| Existing curated regression corpus | 33 | 24 | 0 | 0 |
| New targeted boundary probe | 22 | 3 | 6 | 2 |

The new25 cases were deliberately chosen to explore compact v7-style product, price, shipping, scope and review clauses. Three independently authored Vietnamese examples were included after a separate read-only investigation reproduced the issue; both English boundary examples also reproduce through full report validation. These are targeted development samples, not random held-out data or calibrated accuracy estimates. Eight direct-screen mismatches also occur in full report validation. The existing57 examples still match all direct-screen labels; report acceptance also agrees with those labels, but the empty-text case fails SCHEMA_INVALID before language screening, so it is reported separately rather than as language evidence. All247 focused report tests pass, confirming no production regression was introduced by this investigation.

False rejections: review_texture (“Giấy hơi xốp.”), review_daily (“Dùng hằng ngày vẫn ổn.”), review_praise (“Chất lượng tốt, dùng suốt.”), independent_package_price (“Giá mỗi thùng khác giá mỗi gói.”), independent_dispatch (“Hàng thường rời kho sau một ngày.”) and independent_wet_review (“Một nhận xét nói giấy dễ rách khi ướt.”). Each is ordinary Vietnamese but insufficiently covered by the small fixed vocabulary. Recognition requires at least two known words and at least half of each sentence's words; adding surrounding familiar vocabulary can change the result without changing the clause's language.

False acceptances: foreign_inline (“Nguồn hiển thị sản phẩm, shipping guaranteed.”) passes because neither English word is on the small foreign-word list and enough Vietnamese words remain. unprovided_english_quote (“Nguồn hiển thị sản phẩm \"The supplier is reliable\".”) passes because double-quoted contents are stripped regardless of whether they match supplied evidence. Exact-source checking currently constrains ambiguous single quotations, not these double quotations. A semicolon-separated “Shipping guaranteed.” contrast is rejected because it is checked as its own sentence. These results expose known contract boundaries; no claim is made about all possible foreign insertions.

Reproduce from the repository root with PYTHONPATH set to that root:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH=(Get-Location).Path
& 'C:/Users/eidel/Desktop/VCT Connect/.venv/Scripts/python.exe' scripts/evaluate_report_prose.py backend/tests/fixtures/vietnamese_report_prose_probe.jsonl
& 'C:/Users/eidel/Desktop/VCT Connect/.venv/Scripts/python.exe' scripts/evaluate_report_prose.py backend/tests/fixtures/vietnamese_report_prose.jsonl
& 'C:/Users/eidel/Desktop/VCT Connect/.venv/Scripts/python.exe' -m pytest backend/tests/test_text_reports.py -q
```

Recommended next implementation: define and test the language boundary explicitly, including evidence-bound quotation exemptions and short natural Vietnamese clauses, with broader independently authored negatives before choosing a revised screen. A vocabulary-only patch cannot address the demonstrated acceptance weaknesses; lowering recognition thresholds would also need meaningful negative evaluation. No production correction or paid capturing diagnostic is authorized merely by this investigation. Additional live evidence is unnecessary to establish these offline faults, although it would be required to identify the exact missing response's cause.

Independent quick review found one medium diagnostic-classification bug: non-language failures were included in language mismatch counts. Fixed by reporting report_other_rejections separately; two regression cases cover oversized/schema and unsupported-score text. All247 focused tests pass; the25/57 probe results above remain unchanged, with no non-language rejections in the new probe and the existing empty-text case separated as SCHEMA_INVALID. Existing language/quotation limitations are recorded in deferred-work.md for subsequent correction. Thorough review lenses skipped for this small offline tool/evidence change. No deployment or Git push; cloud ledger remains last observed11/$0.02601525, local reservations$0.02385210, combined$0.04986735. No new cloud inspection was needed or run.
