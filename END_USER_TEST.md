# VCT Connect end-user acceptance test

Updated: October 11, 2026 (Asia/Bangkok). Run against the updated local checkout first. An automated or synthetic-provider pass is not live-model, Chrome-extension or Azure acceptance.

## Start the application

Current local session: PostgreSQL, the production web build (port 3000), API (port 8000) and continuous local worker are running. The operator explicitly approved queued and newly submitted supplier evidence being processed through YEScale. Do not start duplicate services. If a service stops, use the commands below to restart it.

Use PowerShell from `C:\Users\eidel\Desktop\VCT Connect`. Existing dependencies and Clerk configuration are present on this machine. For another machine, follow README setup first.

For scored reports, put a valid `YESCALE_API_KEY` in the ignored root `.env`. Keep it server-only. Restart the worker after changing it. `YESCALE_MODEL` defaults to `gpt-4o-mini`; `YESCALE_EMBEDDING_MODEL` is optional for semantic review analysis. The operator configured `deepseek-v4.1-flash`; the approved saved 1688 sample completed a real YEScale report on October 11. DeepSeek V4 structured requests now disable thinking, and the supplier prompt requests concise grounded JSON within the existing token limit.

Verified sample: analysis `1591350c-8239-4945-ad1c-f85ecde61f9e`. Reopen it from **Lịch sử** to inspect the existing report without another model call. It displays **Chưa đủ thông tin**, no overall risk score, 48% confidence and 50% coverage. Source references, browser refresh, History and Watchlist save/reopen/deduplication were checked. The operator-submitted extension capture `37c466a0-037d-4c53-bd13-2b9e3d5fb464` also completed on its first worker attempt, displaying 44% confidence and 50% coverage. Watchlist removal, another account, full Chrome popup/account switching and fresh public-source/cloud checks remain separate acceptance steps.

Start PostgreSQL:

```powershell
docker compose up -d db
```

In the API terminal, load the existing environment, select the local queue, migrate and start the API:

```powershell
Get-Content .env,.env.clerk | ForEach-Object {
  if ($_ -match '^([^#=]+)=(.*)$') {
    [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
  }
}
$env:QUEUE_TRANSPORT = 'local'
$env:API_RUNTIME = 'local'
$env:DEVELOPER_MODE = 'true'
.venv/Scripts/python.exe -m backend.app.init_db
.venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, repeat the environment-loading block and three settings above, then run:

```powershell
$env:WORKER_MODE = 'combined'
.venv/Scripts/python.exe -m backend.worker.main
```

In a third terminal:

```powershell
$env:API_INTERNAL_ORIGIN = 'http://127.0.0.1:8000'
npm run dev --prefix frontend
```

Open **http://127.0.0.1:3000**. Keep these terminals open. If the audit already left these services running, use them instead of starting duplicates. After application changes, restart the API and worker; frontend development changes normally reload automatically. Ctrl+C stops each process.

If port 8000 is reserved, use 8080 for Uvicorn and the matching `API_INTERNAL_ORIGIN` in the frontend terminal. Use the exact `127.0.0.1` origin consistently for Clerk and extension sync.

## Retest the expanded 1688 extension (October 11 fix)

### Saved shop and factory enrichment verified October 11

Open `http://127.0.0.1:3000/?analysis=d0bc536b-5e16-4bd2-a794-2b3ba79a20f7` in the signed-in account used for the product capture. This is a new completed report combining ten captured product reviews with the operator-saved supplier profile. Old reports retain their original evidence.

1. In **Nguồn và bằng chứng**, find `supplier:factory_profile` and `supplier:company_information`. Confirm establishment date `2025-07-14`, employees `11~50人`, custom MOQ `2000件`, private-label MOQ `5000件`, foreign-trade orders `不支持` and VAT invoice `无`. The description says `经销批发` (wholesale/distribution). These are platform claims, not independently verified legal facts.
2. Confirm `supplier:years_active` is `1`, calculated as completed years since that date. The separate `入驻2Year` platform membership label is retained and must not be mistaken for the establishment date.
3. Expect ten reviews and only `certifications` / `activity_history` missing from source fields. Certification badges on recommended suppliers and a link to enterprise annual reports do not fill those fields.
4. Expect **Chưa đủ thông tin**, no overall score, 44% confidence and 15% risk coverage on this persisted run. Source-field completeness is 83.33%, but only the review-manipulation dimension has scored evidence. Populated source fields do not establish all seven risk dimensions. Saved-page age is unknown and receives no freshness credit.

This import is an operator CLI workflow; the normal extraction button does not automatically collect these linked supplier pages. Direct shop navigation was blocked by browser site-safety controls, so verification used the HTML files supplied by the operator. Live automatic link-following and a web multi-page upload flow remain unimplemented. The saved shop's navigation did not contain a static factory hyperlink; the operator-supplied factory URL is checked against the profile canonical and shop backlink.

To repeat the offline workflow, first load `.env` / `.env.clerk` and the local settings as shown above. From the repository root, run the command below without `--submit` for a dry run. Add `--submit` only to create another analysis and consume the normal account quota and configured model credits:

```powershell
.venv/Scripts/python.exe -m backend.app.extraction.import_factory1688 `
  --base-analysis bce82bde-2634-4ee5-b959-b6828b6d245b `
  --product-html "sample webpages/1688 Wholesale High-Quality Men's T-Shirts 400g American-Style Printed Heavy-Duty Pure Cotton Short-Sleeve Shirts, Sufficient Supply for Export - 阿里巴巴.html" `
  --shop-html 'sample webpages/东莞市长安海绣服装厂店铺推荐.html' `
  --factory-html 'sample webpages/东莞市长安海绣服装厂-企业信息查询黄页-阿里巴巴.html' `
  --factory-url 'https://sale.1688.com/factory/card.html?memberId=b2b-222030383828763a1d&facMemId=b2b-222030383828763a1d'
```

The base analysis must be completed and customer-owned. This command requires trusted operator database access; it is not an end-user HTTP endpoint. It verifies linked source identities, excludes scripts/account state and recommendations, then queues selected evidence for the existing assessment worker.

The updated extension is built at `C:\Users\eidel\Desktop\VCT Connect\frontend\apps\extension\build`; the API and continuous worker were restarted with the expanded contract. Existing reports retain their original evidence.

1. In Chrome, open `chrome://extensions`, locate **VCT Connect Source Evidence**, and click **Reload**. For a new installation use **Load unpacked** with the build folder above.
2. Refresh `https://detail.1688.com/offer/1027322610455.html`. Use the same Chrome profile signed in to VCT Connect at `http://127.0.0.1:3000`.
3. Let the supplier information, specifications, SKU, shipping and review sections load. Scroll through them so any lazy sections render, then open the extension and click **Analyze this page** once.
   For the review-drawer fix, first open **View reviews** and leave the drawer open while clicking the extension. The saved drawer contains ten loaded review cards, including three identical text entries; all ten now survive capture and an owned-snapshot merge. The extension captures the loaded page (up to 20 reviews within the size limit), not all paginated 40+ reviews. Buyer names and avatars are excluded. Image/video interpretation is not connected to this capture path yet.
4. Follow the newly opened analysis. Expect it to finish; inspect source evidence in the report instead of reopening the old analysis. In the saved-page regression, extraction includes 41 attributes, both Style values, four supplier metrics, nine dropshipping metrics, SKU price and inventory, shipping, product rating 4.6, the approximate 40+ review display and one review snippet. A fresh page can contain different values or fewer loaded sections.
5. Confirm that **coupon ¥0.10** and **¥8.70 minimum-order/loyalty price** retain their context; **¥8.7 / inventory 790** belongs to a SKU. Platform membership is not verified founding age; shipping origin is not company headquarters; dropshipping metrics are not whole-company capacity.
6. Inspect both the **400g title** and the **300g–350g specification** from this saved sample. The extractor preserves this contradiction instead of choosing one claim. Report source completeness and risk coverage are separate measures; do not expect either to reach 100%.

Verified so far: sanitized saved-page capture in a real browser, strict API admission, normalization, existing report projection and PostgreSQL capture regressions. A new full Chrome capture/report remains the end-user acceptance step. This captures selected visible text, not all paginated reviews, image-only descriptions or off-page supplier records.

For a repeatable browser fixture regression, from the repository root run `node frontend/tests/build-1688-harness.cjs`, serve `tmp` on a local port, open `1688-capture-harness.html` and click **Run capture regression**. Expect **PASS: 14 fixture checks**. The fixture excludes scripts, account state and buyer identifiers.

Run the same builder with `--drawer` to include the sanitized drawer fixture; expect **PASS: 17 fixture checks**, ten review entries and no buyer sentinel in the capture output.

## 1. Guest queue check (no AI key needed)

1. While signed out, use the sample URL `https://detail.1688.com/offer/123456789012.html` and click **Thử demo khách**.
2. Expect queued/processing followed by an explicit synthetic fixture completion message.
3. Expect **no real risk score and no report-backed preview** for this URL. Its result is only a queue tracer. The decorative landing report is labeled illustrative.
4. The fixture must not claim a real report is ready or finish with an unexplained `Preview not found` error.

This verifies web → API → database queue → worker → persisted status. It does not verify extraction, model interpretation or report creation.

## 2. Main buyer test: saved evidence → report

This path avoids a live platform login/challenge while testing the application with repeatable evidence. It still needs the configured AI worker. The repository HTML is a saved historical sample, not fresh live supplier evidence.

1. Click **Đăng nhập** and use a test account. In Clerk development settings, the session token audience must be `vct-connect-api`.
2. Open **Phân tích mới**. Replace the default tracer URL with:

   ```text
   https://detail.1688.com/offer/996518024136.html
   ```

3. Under **Trang 1688 / Taobao đã lưu (HTML, tùy chọn)**, choose:

   ```text
   C:\Users\eidel\Desktop\VCT Connect\backend\tests\fixtures\1688_offer_996518024136.html
   ```

4. Click **Nhập trang đã lưu** once. Expect **Đang đánh giá bằng chứng**, then reporting/completion. Very fast intermediate states may not be visible between polls.
5. Expect a persisted Vietnamese report for the same source/analysis, not just an extraction card. Partial evidence may legitimately produce **Chưa đủ thông tin** and a blank overall risk score.
6. Check that **Risk**, **Độ tin cậy** and **Độ phủ dữ liệu** are separate. Missing evidence must not be shown as zero risk or LOW.
7. Click a finding's evidence reference. Its source card should show retained source values/text separately from interpretation. Missing source values remain unknown. Review text is only available if the saved page actually contains reviews; the 1688 sample does not.
8. Check limitations and recommended pre-order verification. The saved-page capture time is unknown; importing today does not prove the source was captured today.

Optional Taobao repeat: source URL `https://item.taobao.com/item.htm?id=1076425861755`; select `backend\tests\fixtures\taobao_item_1076425861755.html`. Alibaba saved-page import is unsupported and must be rejected clearly.

## 3. History and reopening

1. Open **Lịch sử**. Expect your submitted analyses, actual state and report availability, without the old synthetic seeded history.
2. Find the imported analysis and click **Mở báo cáo**.
3. Confirm that the report, source URL input and analysis ID match the selected entry, and that an earlier selected HTML file has been cleared.
4. Refresh the page. The `?analysis=<id>` URL should reopen the same authorized analysis/report.
5. Sign out and sign in again. Reopen it from history. A browser refresh or account session change must not erase server history.

## 4. Watchlist and account

1. On a completed report, click **Lưu vào Watchlist**.
2. Open **Watchlist**. Expect one supplier entry. Reopen the report, save the same supplier again, and confirm no duplicate.
3. Open the saved item; verify the source input/report refer to the same supplier.
4. Click **Xoá** on your test item. Confirm it disappears from Watchlist and stays removed after refresh; the analysis remains in history.
5. Open **Tài khoản**. Check the persisted plan, trial state and current-window usage. A new account may be Free; a trial is not automatically granted by sign-up.
6. If an operator has granted a local test trial, its quota must apply equally to URL, saved HTML and extension submissions. Expired/future trials must not grant active access. Do not expect charging, auto-renewal or a payment flow.

## 5. Ownership and guest boundaries

1. Copy the first account's `?analysis=<id>` URL.
2. In a separate browser profile/private window, sign in with another test account and open it. Expect a non-disclosing not-found/access response and **no supplier evidence or report** from account one.
3. Check that account two's history and Watchlist contain only its own items.
4. For a real guest preview, sign out, enter a non-tracer supported public URL in the guest form and submit. The worker must have an AI key, and the source must be accessible.
5. If a report is available, expect only the limited preview: Confidence, Coverage, missing-data/uncertainty context and registration guidance. Expect no overall risk score, detailed findings, evidence payloads or full action list.
6. A blocked public source is a valid explicit access outcome, not a successful report test. A report-less result must explain the limit without inventing a risk verdict.
7. Opening the guest result in another browser without its original guest cookie must reveal no result. Signing up does not automatically transfer a prior guest report to the account; submit evidence under that account for a full report.

## 6. Live source and failure behavior

Use a supported URL that you can actually open. Do not use the synthetic tracer as a live supplier.

- 1688: `https://detail.1688.com/offer/<numeric-id>.html`
- Taobao item: `https://item.taobao.com/item.htm?id=<numeric-id>`
- Taobao shop: `https://shop<numeric-id>.taobao.com/`
- Alibaba product: `https://www.alibaba.com/product-detail/<name>_<numeric-id>.html`
- Alibaba company: `https://<store>.en.alibaba.com/company_profile.html`

Submit once. Expect either a report backed by extracted evidence, or a clear blocked/login/partial/timeout/insufficient outcome with recovery instructions. A blocked source must not display a fabricated LOW risk score. For 1688/Taobao, recover using permitted visible-page extension evidence or matching saved HTML. Alibaba currently supports public URL extraction only.

Try an unsupported domain such as `https://example.com/`: expect rejection without queueing work. An oversized HTML file above 2,000,000 bytes must be rejected. With local test quotas lowered by an operator, an extra submission must return a limit message and create no work. Do not clear cookies to bypass a test limit; the shared guest limit still applies.

## 7. Chrome extension

Follow `frontend/apps/extension/README.md` for Clerk Native API/origin setup and **Load unpacked**. Use Chrome; the in-app browser does not establish extension acceptance.

1. Build with `npm run build --prefix frontend/apps/extension`; load `frontend/apps/extension/build` through `chrome://extensions`. Reload the extension after rebuilding.
2. Sign in on VCT Connect in the same Chrome profile and exact configured web origin. Open a supported 1688/Taobao page.
3. Open the popup. Expect signed-in supported-page state and **Analyze this page**. Unsupported pages or signed-out state must not permit enhanced submission.
4. For 1688, follow the guided two-click journey below; product capture pauses until company capture or product-only completion. Taobao retains one-click capture and an automatically opened web result.
5. Close and reopen the popup. Expect the current owner's last result to load automatically, with correct progress or condensed Risk/Confidence/Coverage. **Open web result** and **Reload last result** remain usable.
6. Switch VCT accounts and reopen. Account one's persisted result must not become visible under account two.
7. In an extension network inspection, check that capture JSON contains selected source fields, cleaned public HTML for linked 1688 collection and VCT authorization; source-platform cookies, tokens, passwords, storage and original full-page HTML must not be included. Alibaba capture is unsupported.

## Record acceptance

### Guided 1688 product → company capture (extension 0.4.0)

1. Reload VCT Connect in `chrome://extensions`. Its unpacked directory is `C:\Users\eidel\Desktop\VCT Connect\frontend\apps\extension\build`. Confirm version **0.4.2** and that API, worker, web and database are running.
2. Open the product in the signed-in Chrome profile. Load its review drawer before opening the extension. Click **Analyze this page** once. Expect **Product captured · company evidence needed**, a green outline around its supplier/company name, and an instruction card on the product. Note the analysis ID. No automatic company navigation should occur.
3. Close the popup and click the highlighted company name, or use **Open linked company page**. Complete login/CAPTCHA yourself. Wait until the company introduction is visible. For founding date/employee/MOQ details, navigate to the company's **Factory profile / 工厂档案** before the second click instead. Reopen VCT Connect and click **Analyze this page** again.
4. Expect company HTML capture/upload and an automatically opened web result for the **same analysis ID**. After assessment, check company introduction/source evidence, product details and retained reviews. Confirm one quota slot was consumed. Unknown certificates/activity history/factory-only claims must remain unknown.
5. Check Chrome Downloads for `VCT Connect/<analysis ID>/product.html` and `shop.html` (or `factory.html` when the profile was chosen). Report HTML records should show `PARSED`, source URLs, byte counts and hashes, or explicit missing/capped limitations. Downloaded copies should exclude scripts, account controls, buyer identities, hidden content and embedded media.
6. Before step 3, close/reopen the popup or Chrome. Expect the pending capture to restore for the same VCT account. On another supplier's shop, **Analyze this page** must remain disabled. On a login/challenge page, complete access yourself and return to the linked shop; retries must not reserve another quota slot.
7. For product-only completion, choose **Finish with product evidence only**. If collection is abandoned, the continuous worker processes the stored product after **30 minutes**, with timeout limitations. This is a collection deadline, not a promise of completed LLM assessment.
8. If the final upload response is interrupted, expect **Retry saved upload**. It must reuse the saved payload/analysis ID without re-reading changed source content. Switch VCT accounts and verify that the other account's pending capture/result is hidden.

Local verification: 43 targeted backend tests, 148 frontend tests, TypeScript and extension build; an offline browser check verifies the company-link highlight and visible login/CAPTCHA/second-click instructions. Actual Chrome permission/download/session and live source acceptance remain operator checks. Factory profiles are captured only when the user opens one before the second click; canonical identity and its company backlink must match. Automatic traversal is removed. The saved factory import also remains available.

Automated checks cover saved-DOM extraction, mocked Chrome navigation, popup restoration, PostgreSQL ownership/idempotency and deadline recovery. Real Chrome/Clerk permission and session acceptance must be recorded by the operator; fixture checks do not establish a live-source pass. Photos/video and review pagination remain outside this milestone.

Record the app revision, environment, account label (no credentials), analysis ID, source/evidence origin, observed outcome, duration, screenshot and pass/fail for each test. Mark a blocked prerequisite **not tested**, rather than passed.

A buyer-ready local pass requires the saved-evidence report, source inspection, history refresh, Watchlist deduplication/removal and cross-account isolation. A deployed release additionally needs this journey on the deployed web app with live Clerk/YEScale/Service Bus, persisted report and cost/provenance, plus real Chrome extension acceptance. The guest tracer smoke alone does not meet that gate.

Internal reviewer functionality currently covers blind text labels and their annotation fields at `/internal/review`; it requires an INTERNAL_REVIEWER account and retained review-interpretation cases. Media review, adjudication, benchmark dashboards and pilot measurements remain unfinished and are not end-user acceptance claims.

### SVG regression retest — extension 0.4.1

Reload extension 0.4.1, open product 1009411929167 and click Analyze this page again. Expect its supplier link to resolve to shop05n8n645901d1.1688.com and company guidance to appear. A prior definitively rejected cached capture is discarded and recaptured; ambiguous responses still preserve the reservation. Downloaded product HTML must exclude SVG/foreign-namespace elements. Follow the guided company capture above.

Regression verification: browser-generated capture for product 1009411929167 was accepted by the normalizer and authenticated PostgreSQL begin endpoint. Ten collection API tests and nine extension background lifecycle tests passed; full frontend suite passed 149 tests before the final cached-rejection regression was added.

### Company injection serialization retest — extension 0.4.2

Reload extension 0.4.2, return to the linked company or its matching factory profile, reopen the popup and click Analyze this page. A pending product capture remains usable within its 30-minute deadline; no new product submission is needed. SHOP/FACTORY script arguments now omit the absent optional product URL instead of sending undefined, which Chrome rejects. Nine background lifecycle tests with a strict serialization guard and TypeScript passed; extension build completed.


### Visual report acceptance — 2026-10-11

1. Refresh an existing completed report at http://127.0.0.1:3000. Expect circular charts for overall risk, confidence and evidence coverage, followed by a horizontal comparison of risk dimensions. Unknown risk must appear as an empty dashed ring or striped bar, never a zero/low-risk value.
2. Use Tổng quan, Biểu đồ rủi ro, Việc cần làm and Bằng chứng to move between report sections. Open Độ tin cậy & nguồn for the scoring details behind a dimension.
3. In actions, findings, uncertainties or limitations with more than five items, use the arrow controls. Expect at most five text items per list page, accurate ranges, and the remaining items reachable. A different report starts at the first page.
4. Click a source reference beneath a finding. Expect the matching evidence card to open and show its original content. Close it and click the same reference again; it must reopen. Source URLs and timestamps remain inspectable.
5. Check a narrow/mobile window. Charts, section links, tags and source text must fit without horizontal page scrolling. Repeat with a scored report and an insufficient-information report; persisted scores and findings must retain their original meaning.

Verified locally: 153 frontend tests, TypeScript and production web build passed. Browser checks covered synthetic scored/insufficient reports, five-item paging, automatic evidence opening and a 390px responsive viewport without horizontal overflow. Existing signed-in report 37c466a0-037d-4c53-bd13-2b9e3d5fb464 also showed the new charts, five-item action pages and working source links. Proof: tmp/report-redesign-proof.png. No new supplier extraction was required for this presentation change; live Chrome/CAPTCHA acceptance remains separate.


### Dismissible CAPTCHA overlays and guided HTML capture — extension 0.5.0

1. Reload the unpacked extension at `C:\Users\eidel\Desktop\VCT Connect\frontend\apps\extension\build`, confirm version **0.5.0**, and keep local services running. On a product with loaded reviews, click **Analyze this page**. Note the reserved analysis ID and product HTML download.
2. Open the highlighted supplier shop. Close a CAPTCHA overlay with **X** yourself. If the company introduction is visible, open the popup and click **Save shop HTML**. Expect a shop HTML download, **Shop HTML saved · factory evidence next**, and no second quota reservation or final upload yet.
3. Follow the highlighted **Factory profile / 工厂档案** control. Close any dismissible overlay and click **Save factory HTML & analyze** in the popup. Expect the factory HTML download, combined upload under the original ID, and the opened result. Verify original company/source content and factory claims in the report.
4. If the factory is inaccessible, choose **Finish with captured product & shop**. If no usable company content exists, choose product-only completion. A different supplier/profile must not be accepted; an overlay alone must not become company evidence. A download failure must retain uploadable HTML and show a warning.
5. Close/reopen the popup after shop capture and confirm restoration. Inspect Downloads/VCT Connect/<analysis ID> for cleaned product/shop/factory HTML. If final submission is interrupted, retry the saved upload; evidence and reservation must remain the same. Finish within 30 minutes; an abandoned reservation processes only the previously server-stored product.

Local validation: 157 frontend tests, TypeScript, extension production build and 26 selected-bundle/HTML backend tests passed. The offline saved-page browser harness dismissed synthetic overlays, captured 2,960 bytes of shop HTML and 3,894 bytes of factory HTML, verified the factory highlight, and passed both captures through the backend normalizer with eight factory claims, company introduction and unknown certificates preserved. Screenshot: tmp/guided-html-shop-proof.png. This demonstrates dismissible-overlay capture with saved source fixtures; actual Chrome/1688 download and session acceptance remains an operator check.


### Header-only shop retest — extension 0.5.1

Reload extension 0.5.1 and return to the linked shop. If its supplier header is visible but the company-introduction module/credit link is absent, **Save shop HTML** now captures that header. Expect WAITING_FACTORY, a shop HTML download and a factory-navigation cue. Retry the existing reservation within its original 30-minute deadline; otherwise start from the product again. The report source records SHOP_HEADER_ONLY and displayed name/tenure/category/service claims; it must not invent a company introduction or treat platform tenure as registered operating age. Finish with the factory or captured product/shop as before.

Validation: 158 frontend tests, TypeScript, extension build, 31 selected-bundle/HTML backend tests and 11 authenticated PostgreSQL collection checks passed. Offline browser capture with the introduction module removed produced header-only HTML accepted as PARSED with four header claims and unknown registered age. Screenshot: tmp/header-shop-proof.png. The operator's exact Shenzhen page was not available as saved HTML; its screenshot established the visible-header symptom, while fixture checks verify the supported header layout. Local API restarted with the new normalization support.
