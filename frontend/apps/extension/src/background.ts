import { createClerkClient } from "@clerk/chrome-extension/background";
import { assertPermittedEvidence, captureSelectedDom, supportedOffer, type LegacyCapture } from "./capture";
import { showCompanyGuidance } from "./company-guidance";
import { capturePublicHtml, MAX_HTML_BUNDLE_BYTES, type HtmlSource } from "./html-capture";
import { captureLinkedDom, factoryUrl, shopUrl, restoreCollectionJob, type CollectionJob, type FactorySelection, type ShopSelection, type SupplierBundle } from "./linked-capture";

const JOB_KEY = "collectionJob";
const ORIGINS = ["https://*.1688.com/*"];
let running = false;

async function authenticate(ownerId: string): Promise<string> {
  const clerk = await createClerkClient({ publishableKey: VCT_CLERK_PUBLISHABLE_KEY, syncHost: VCT_CLERK_SYNC_HOST });
  if (clerk.user?.id !== ownerId || !clerk.session) throw new Error("Account changed");
  const token = await clerk.session.getToken({ skipCache: true });
  if (!token) throw new Error("Sign in first");
  return token;
}

async function post(phase: "begin" | "finish", bundle: SupplierBundle, ownerId: string): Promise<void> {
  const body = JSON.stringify(bundle);
  if (new TextEncoder().encode(body).length > (bundle.html_sources?.length ? MAX_HTML_BUNDLE_BYTES : 32_768)) throw new Error("Collection too large");
  for (let attempt = 0; attempt < 2; attempt++) {
    const token = await authenticate(ownerId);
    try {
      const response = await fetch(`${VCT_WEB_ORIGIN}/api/v1/analyses/collection/${phase}`, {
        method: "POST", credentials: "omit", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body, signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) {
        if (response.status >= 500 && attempt === 0) continue;
        if (response.status >= 500 && phase === "begin") {
          await chrome.storage.local.set({ lastCapture: { analysisId: bundle.job_id, ownerId, sourceUrl: bundle.product.source_url } });
          throw Object.assign(new Error("Reservation response lost"), { reservationUncertain: true });
        }
        throw Object.assign(new Error(response.status === 422
          ? "The captured evidence was rejected. Reload the extension, then analyze this product again to capture fresh evidence."
          : `Collection request failed (${response.status})`), { reservationRejected: phase === "begin" && response.status === 422 });
      }
      return;
    } catch (error) {
      if (!(error instanceof Error) || !["TimeoutError", "TypeError"].includes(error.name)) throw error;
      if (attempt === 1) {
        if (phase === "begin") {
          // Preserve the same reservation ID if a committed begin response was lost.
          await chrome.storage.local.set({ lastCapture: { analysisId: bundle.job_id, ownerId, sourceUrl: bundle.product.source_url } });
          throw Object.assign(new Error("Reservation response lost"), { reservationUncertain: true });
        }
        throw error;
      }
    }
  }
  throw new Error("Collection request failed");
}

type GuidedSession = { job: CollectionJob; bundle: SupplierBundle; reserved: boolean };
const SESSION_KEY = "guidedCollection";

async function selected<T>(tabId: number, mode: Parameters<typeof captureLinkedDom>[0], expected?: string): Promise<T | null> {
  const [result] = await chrome.scripting.executeScript({ target: { tabId }, func: captureLinkedDom,
    args: expected === undefined ? [mode] : [mode, expected] });
  return result?.result as T | null;
}

async function saveSession(session: GuidedSession) {
  await chrome.storage.local.set({ [SESSION_KEY]: session, [JOB_KEY]: session.job });
}

async function captureHtml(tabId: number, page: HtmlSource["page"], source: string, session: GuidedSession) {
  try {
    const [result] = await chrome.scripting.executeScript({ target: { tabId }, func: capturePublicHtml, args: [page, source] });
    const html = result?.result as HtmlSource | null;
    if (!html || html.page !== page || html.source_url !== source) return { captured: false, downloaded: false };
    assertPermittedEvidence(html);
    await authenticate(session.job.ownerId);
    const sources = (session.bundle.html_sources || []).filter(item => item.page !== page);
    sources.push(html);
    const next = { ...session.bundle, html_sources: sources };
    if (new TextEncoder().encode(JSON.stringify(next)).length > MAX_HTML_BUNDLE_BYTES) return { captured: false, downloaded: false };
    session.bundle.html_sources = sources;
    let downloaded = false;
    try {
      await chrome.downloads.download({ url: "data:text/html;charset=utf-8," + encodeURIComponent(html.html),
        filename: `VCT Connect/${session.job.id}/${page.toLowerCase()}.html`, saveAs: false, conflictAction: "uniquify" });
      downloaded = true;
    } catch { /* Upload does not depend on a disk download. */ }
    return { captured: true, downloaded };
  } catch { return { captured: false, downloaded: false }; }
}

async function finishSession(session: GuidedSession) {
  if (!session.reserved) {
    // Reconcile a lost begin response with the identical durable reservation.
    await post("begin", session.bundle, session.job.ownerId);
    session.reserved = true;
  }
  session.bundle.outcomes = [
    { page: "SHOP", status: session.bundle.shop ? "OK" : session.bundle.shop_url ? "UNAVAILABLE" : "LINK_UNAVAILABLE" },
    { page: "FACTORY", status: session.bundle.factory ? "OK" : "UNAVAILABLE" },
  ];
  session.job = { ...session.job, stage: "FINISHING" };
  await saveSession(session); // Preserve exactly the submitted evidence for response-loss recovery.
  await post("finish", session.bundle, session.job.ownerId);
  session.job = { ...session.job, stage: "ASSESSING", error: session.job.error?.includes("download did not start") ? session.job.error : undefined, reservationUncertain: false };
  await saveSession(session);
  try { await chrome.tabs.create({ url: `${VCT_WEB_ORIGIN}/?analysis=${encodeURIComponent(session.job.id)}` }); } catch { /* Popup keeps the result link. */ }
}

async function guided(type: string, tabId: number, ownerId: string, sourceUrl?: string) {
  if (running) throw new Error("Capture is already running. Reopen the popup when it finishes.");
  running = true;
  let session: GuidedSession | undefined;
  let retryingStoredReservation = false;
  try {
    await authenticate(ownerId);
    const stored = await chrome.storage.local.get([SESSION_KEY, JOB_KEY]);
    const candidate = stored[SESSION_KEY] as GuidedSession | undefined;
    const job = restoreCollectionJob(candidate?.job, ownerId);
    const pending = job && ["STARTING", "WAITING_COMPANY", "WAITING_FACTORY", "FINISHING", "ERROR"].includes(job.stage)
      && Boolean(candidate?.bundle?.guided) && (job.expiresAt || 0) > Date.now();
    if (pending) session = candidate;
    if (type === "FINISH_GUIDED") {
      if (!session) throw new Error("No pending product capture. Start a fresh product analysis.");
      await finishSession(session); return { id: session.job.id };
    }
    const tab = await chrome.tabs.get(tabId);
    if (type === "START_COLLECTION") {
      if (session) {
        if (!session.reserved && session.job.sourceUrl === sourceUrl) {
          retryingStoredReservation = true;
          await post("begin", session.bundle, ownerId); session.reserved = true;
          session.job = { ...session.job, stage: "WAITING_COMPANY", error: undefined, reservationUncertain: false };
          await saveSession(session);
          await chrome.storage.local.set({ lastCapture: { analysisId: session.job.id, ownerId, sourceUrl: session.job.sourceUrl } });
          return { id: session.job.id };
        }
        throw new Error("A product is waiting for company evidence. Open its company page or finish the saved evidence first.");
      }
      if (supportedOffer(tab.url || "")?.sourceUrl !== sourceUrl) throw new Error("The active product changed.");
      const [injected] = await chrome.scripting.executeScript({ target: { tabId }, func: captureSelectedDom });
      const product = injected?.result as LegacyCapture | undefined;
      if (!product || !("offer_id" in product) || product.source_url !== sourceUrl) throw new Error("Product evidence is not ready.");
      const link = await selected<string>(tabId, "PRODUCT_LINK", sourceUrl);
      if (supportedOffer((await chrome.tabs.get(tabId)).url || "")?.sourceUrl !== sourceUrl) throw new Error("The active product changed.");
      const company = link ? shopUrl(link) : null;
      const startedAt = Date.now();
      const job: CollectionJob = { id: crypto.randomUUID(), ownerId, sourceUrl: sourceUrl!, startedAt,
        expiresAt: startedAt + 30 * 60_000, stage: "STARTING", ...(company ? { companyUrl: company } : {}) };
      session = { job, reserved: false, bundle: { job_id: job.id, product, guided: true,
        ...(company ? { shop_url: company } : {}), outcomes: [], html_capture_requested: true } };
      assertPermittedEvidence(session.bundle);
      await captureHtml(tabId, "PRODUCT", sourceUrl!, session);
      await saveSession(session); // Durable identical begin payload before sending.
      await post("begin", session.bundle, ownerId); session.reserved = true;
      session.job = { ...job, stage: "WAITING_COMPANY" };
      await saveSession(session);
      await chrome.storage.local.set({ lastCapture: { analysisId: job.id, ownerId, sourceUrl } });
      if (company) {
        try { await chrome.scripting.executeScript({ target: { tabId }, func: showCompanyGuidance, args: ["SHOP", company] }); } catch { /* Popup retains the link. */ }
      } else await finishSession(session);
      return { id: job.id };
    }
    if (!session || !session.reserved) throw new Error("Capture a product first, or retry its pending reservation.");
    if (session.job.stage === "FINISHING") { await finishSession(session); return { id: session.job.id }; }
    const company = session.bundle.shop_url;
    if (!company) throw new Error("No company link was found on the product.");
    if (["WAITING_COMPANY", "WAITING_FACTORY"].includes(session.job.stage) && factoryUrl(tab.url || "")) {
      const profile = factoryUrl(tab.url || "")!;
      if (session.job.factoryUrl && session.job.factoryUrl !== profile) throw new Error("Open the factory profile linked from the captured shop.");
      const factory = await selected<FactorySelection>(tabId, "FACTORY");
      if (!factory || factory.source_url !== profile || factory.canonical_url !== profile || factory.shop_url !== company ||
          factoryUrl((await chrome.tabs.get(tabId)).url || "") !== profile) {
        throw new Error("Factory company evidence is not visible or belongs to another supplier. Close the CAPTCHA with X if possible, wait for the company content, and retry Save factory HTML.");
      }
      session.bundle.factory = factory;
      const snapshot = await captureHtml(tabId, "FACTORY", profile, session);
      if (!snapshot.captured) throw new Error("No usable factory HTML was captured. Close the overlay and retry when company content is visible.");
      if (!snapshot.downloaded) session.job = { ...session.job, error: "Factory HTML was uploaded, but its browser download did not start." };
      if (session.bundle.shop) session.bundle.shop.factory_url = profile;
      await saveSession(session); await finishSession(session);
      return { id: session.job.id };
    }
    if (["WAITING_COMPANY", "WAITING_FACTORY"].includes(session.job.stage)) {
      if (shopUrl(tab.url || "") !== company) throw new Error("Open this product's linked shop, close the CAPTCHA with X if possible, and choose Save shop HTML.");
      const shop = await selected<ShopSelection>(tabId, "SHOP");
      if (!shop || shop.source_url !== company || (shop.credit_url !== undefined && shop.credit_url !== company + "page/creditdetail.html") || (!shop.credit_url && !shop.company_name) ||
          shopUrl((await chrome.tabs.get(tabId)).url || "") !== company) {
        throw new Error("No supported supplier header or company introduction was detected. Scroll to the company section and retry Save shop HTML; a CAPTCHA solution is not required for visible content.");
      }
      session.bundle.shop = shop;
      const snapshot = await captureHtml(tabId, "SHOP", company, session);
      if (!snapshot.captured) throw new Error("No usable shop HTML was captured. Close the overlay and retry when the company introduction is visible.");
      session.job = { ...session.job, stage: "WAITING_FACTORY", factoryUrl: shop.factory_url,
        error: snapshot.downloaded ? undefined : "Shop HTML is stored for upload, but the browser download did not start. You can retry Save shop HTML." };
      await saveSession(session);
      try { await chrome.scripting.executeScript({ target: { tabId }, func: showCompanyGuidance, args: ["FACTORY", company] }); } catch { /* Popup retains next-step guidance. */ }
      return { id: session.job.id };
    }
    throw new Error("Company capture is already finished. Start a fresh product analysis for new evidence.");
  } catch (error) {
    if (session && !session.reserved) {
      if (error && typeof error === "object" && "reservationRejected" in error && error.reservationRejected) {
        session.job = { ...session.job, stage: "ERROR", reservationUncertain: false,
          error: "Evidence rejected before reservation. Analyze the product again to capture fresh evidence." };
        await chrome.storage.local.set({ [SESSION_KEY]: null, [JOB_KEY]: session.job });
        if (retryingStoredReservation && type === "START_COLLECTION") {
          running = false;
          return await guided(type, tabId, ownerId, sourceUrl);
        }
        throw error;
      }
      session.job = { ...session.job, stage: "ERROR", reservationUncertain: true,
        error: "Product reservation may have been saved. Retry the same product; the analysis ID will be reused." };
      await saveSession(session);
    }
    throw error;
  } finally { running = false; }
}

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== chrome.runtime.id || !sender.url?.endsWith("/popup.html") ||
      !["START_COLLECTION", "CONTINUE_GUIDED", "FINISH_GUIDED", "SHOW_GUIDANCE"].includes(message?.type)) return;
  if (!Number.isInteger(message.tabId) || typeof message.ownerId !== "string" || !message.ownerId.startsWith("user_") ||
      (message.type === "START_COLLECTION" && !/^https:\/\/detail\.1688\.com\/offer\/[0-9]{6,20}\.html$/.test(message.sourceUrl || ""))) {
    respond({ error: "Invalid collection request" }); return;
  }
  if (message.type === "SHOW_GUIDANCE") {
    void guideTab(message.tabId, message.ownerId).then(() => respond({ ok: true })).catch(() => respond({ ok: false }));
    return true;
  }
  void guided(message.type, message.tabId, message.ownerId, message.sourceUrl)
    .then(respond).catch(error => respond({ error: error instanceof Error ? error.message : "Capture failed" }));
  return true;
});

async function guideTab(tabId: number, ownerId?: string) {
  const stored = await chrome.storage.local.get(SESSION_KEY);
  const session = stored[SESSION_KEY] as GuidedSession | undefined;
  if (!session || !session.reserved || (ownerId && session.job.ownerId !== ownerId)) return;
  const job = restoreCollectionJob(session.job, session.job.ownerId);
  if (!job || !["WAITING_COMPANY", "WAITING_FACTORY"].includes(job.stage) || (job.expiresAt || 0) <= Date.now()) return;
  const tab = await chrome.tabs.get(tabId);
  const company = session.bundle.shop_url;
  if (!company) return;
  if (shopUrl(tab.url || "") !== company && !factoryUrl(tab.url || "")) return;
  await authenticate(job.ownerId);
  let mode: "SHOP_CAPTURE" | "FACTORY_CAPTURE" | "FACTORY";
  if (shopUrl(tab.url || "") === company) mode = job.stage === "WAITING_FACTORY" ? "FACTORY" : "SHOP_CAPTURE";
  else {
    const profile = factoryUrl(tab.url || "");
    if (!profile || (job.factoryUrl && profile !== job.factoryUrl)) return;
    const factory = await selected<FactorySelection>(tabId, "FACTORY");
    if (!factory || factory.shop_url !== company || factory.source_url !== profile || factory.canonical_url !== profile) return;
    mode = "FACTORY_CAPTURE";
  }
  await chrome.scripting.executeScript({ target: { tabId }, func: showCompanyGuidance, args: [mode, company] });
}
chrome.tabs.onUpdated.addListener((tabId, change) => {
  if (change.status === "complete") void guideTab(tabId).catch(() => {});
});
