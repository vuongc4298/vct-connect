import { ClerkProvider, UserButton, useAuth } from "@clerk/chrome-extension";
import { enUS, viVN } from "@clerk/localizations";
import { ApiError, getAnalysis, getReport, submitBrowserEvidence } from "@vct/api-client";
import type { Analysis, ReportV1 } from "@vct/contracts";
import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { assertPermittedEvidence, captureSelectedDom, supportedOffer } from "./capture";
import { loadScopedResult, restoreLastCapture, saveOpenAndLoadResult, type LastCapture } from "./capture-result";
import { canSubmitEnhancedEvidence, classifyExtensionPage, extensionGate, type ExtensionPageState } from "./extension-shell";
import { extensionVerdict } from "./extension-verdict";
import { restoreCollectionJob, type CollectionJob } from "./linked-capture";
import { errorText, uiText, type UiLanguage } from "./ui-language";

const LAST_CAPTURE_KEY = "lastCapture";

function openWebSignIn() {
  return chrome.tabs.create({ url: `${VCT_WEB_ORIGIN}/` });
}

export function App({ initialLanguage = "vi", onLanguageChange }: { initialLanguage?: UiLanguage; onLanguageChange?: (language: UiLanguage) => void } = {}) {
  const [language, setLanguage] = useState<UiLanguage>(initialLanguage);
  const t = (text: string) => uiText(text, language);
  useEffect(() => {
    void chrome.storage.local.get("uiLanguage").then(stored => {
      if (stored.uiLanguage === "vi" || stored.uiLanguage === "en") setLanguage(stored.uiLanguage);
    }).catch(() => {});
  }, []);
  function chooseLanguage(next: UiLanguage) {
    setLanguage(next);
    onLanguageChange?.(next);
    void chrome.storage.local.set({ uiLanguage: next }).catch(() => {});
  }
  const { getToken, isLoaded, isSignedIn, userId } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Analysis | null>(null);
  const [report, setReport] = useState<ReportV1 | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [lastCapture, setLastCapture] = useState<LastCapture | null>(null);
  const [page, setPage] = useState<ExtensionPageState>({ status: "checking" });
  const [signInDelayed, setSignInDelayed] = useState(false);
  const [collectionJob, setCollectionJob] = useState<CollectionJob | null>(null);
  const owner = useRef(userId);
  owner.current = isLoaded && isSignedIn ? userId : null;
  const requestVersion = useRef(0);

  useEffect(() => {
    let active = true;
    void chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) => {
      if (active) setPage(classifyExtensionPage(tab?.url));
    }).catch(() => {
      if (active) setPage({ status: "unsupported" });
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (isLoaded) { setSignInDelayed(false); return; }
    const timer = setTimeout(() => setSignInDelayed(true), 30_000);
    return () => clearTimeout(timer);
  }, [isLoaded]);

  useEffect(() => {
    const restorationVersion = ++requestVersion.current;
    setBusy(false);
    setCollectionJob(null);
    setLastCapture(null);
    setResult(null);
    setReport(null);
    setReportLoading(false);
    setError("");
    if (!isLoaded || !isSignedIn || !userId) { setLastCapture(null); return; }
    let active = true;
    void chrome.storage.local.get([LAST_CAPTURE_KEY, "collectionJob"]).then(stored => {
      if (active) setCollectionJob(restoreCollectionJob(stored.collectionJob, userId));
      const last = restoreLastCapture(stored[LAST_CAPTURE_KEY], userId);
      if (active && requestVersion.current === restorationVersion && last) {
        setLastCapture(last);
        void loadResult(last.analysisId).catch(cause => {
          if (active) setError(cause instanceof Error ? cause.message : "Could not restore result");
        });
      }
    }).catch(() => { if (active) setError("Could not restore the last result link"); });
    return () => { active = false; requestVersion.current++; };
  }, [isLoaded, isSignedIn, userId]);

  useEffect(() => {
    if (!isLoaded || !isSignedIn || !userId) return;
    let active = true;
    let pending = false;
    const timer = setInterval(() => {
      if (pending) return;
      pending = true;
      void chrome.storage.local.get([LAST_CAPTURE_KEY, "collectionJob"]).then(stored => {
        if (!active || owner.current !== userId) return;
        setCollectionJob(restoreCollectionJob(stored.collectionJob, userId));
        const last = restoreLastCapture(stored[LAST_CAPTURE_KEY], userId);
        if (last && last.analysisId !== lastCapture?.analysisId) {
          setLastCapture(last);
          void loadResult(last.analysisId).catch(() => {});
        }
      }).catch(() => {}).finally(() => { pending = false; });
    }, 1000);
    return () => { active = false; clearInterval(timer); };
  }, [isLoaded, isSignedIn, userId, lastCapture?.analysisId]);

  async function loadResult(analysisId: string) {
    const expectedOwner = owner.current;
    const version = ++requestVersion.current;
    const current = () => Boolean(expectedOwner) && owner.current === expectedOwner && requestVersion.current === version;
    if (!current()) return;
    setReportLoading(true);
    try {
      await loadScopedResult(analysisId, {
        current,
        analysis: id => getAnalysis(id, { getToken: () => getToken({ skipCache: true }) }, { origin: VCT_WEB_ORIGIN, timeoutMs: 45_000 }),
        report: id => getReport(id, { getToken: () => getToken({ skipCache: true }) }, { origin: VCT_WEB_ORIGIN, timeoutMs: 45_000 }),
        publish: (analysis, full) => { setResult(analysis); setReport(full); setError(""); },
      });
    } catch (cause) {
      if (!current()) return;
      if (cause instanceof ApiError) {
        if (cause.status === 401 || cause.status === 403 || cause.status === 404) {
          throw new Error("Could not load result. Sign into the same VCT Connect account.");
        }
        if (cause.status === 408) throw new Error("Result lookup timed out. Retry loading the last result.");
      }
      throw cause;
    } finally {
      if (current()) setReportLoading(false);
    }
  }

  async function retryResult() {
    if (!lastCapture) return;
    const expectedOwner = owner.current;
    setBusy(true); setError("");
    try { await loadResult(lastCapture.analysisId); }
    catch (cause) { if (owner.current === expectedOwner) setError(cause instanceof Error ? cause.message : "Could not load result"); }
    finally { if (owner.current === expectedOwner) setBusy(false); }
  }

  const gate = extensionGate({ authLoaded: isLoaded, signedIn: Boolean(isSignedIn), page });
  const verdict = extensionVerdict(result, report);
  const collecting = collectionJob && ["STARTING", "SHOP", "FACTORY"].includes(collectionJob.stage)
    && Date.now() - collectionJob.startedAt < 70_000;

  const guidedWaiting = Boolean(collectionJob && ["WAITING_COMPANY", "WAITING_FACTORY", "FINISHING"].includes(collectionJob.stage)
    && (collectionJob.expiresAt || 0) > Date.now());
  const linkedPage = page.status === "supported" && ["1688-company", "1688-factory"].includes(page.kind);
  const canCapturePage = !linkedPage || Boolean(guidedWaiting && collectionJob && page.status === "supported" &&
    (["WAITING_COMPANY", "WAITING_FACTORY", "FINISHING"].includes(collectionJob.stage) && (page.sourceUrl === collectionJob.companyUrl || (page.kind === "1688-factory" && (!collectionJob.factoryUrl || page.sourceUrl === collectionJob.factoryUrl)))));

  useEffect(() => {
    if (!guidedWaiting || !canCapturePage || !userId) return;
    void chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) => {
      if (tab?.id) return chrome.runtime.sendMessage({ type: "SHOW_GUIDANCE", tabId: tab.id, ownerId: userId });
    }).catch(() => {});
  }, [guidedWaiting, linkedPage, canCapturePage, userId, language]);

  async function finishGuided() {
    const expectedOwner = owner.current;
    setBusy(true); setError("");
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id || !expectedOwner) throw new Error("Sign in first");
      const reply = await chrome.runtime.sendMessage({ type: "FINISH_GUIDED", tabId: tab.id, ownerId: expectedOwner });
      if (owner.current !== expectedOwner) return;
      if (!reply?.id) throw new Error(reply?.error || "Could not finish capture");
      const stored = await chrome.storage.local.get("collectionJob");
      setCollectionJob(restoreCollectionJob(stored.collectionJob, expectedOwner));
      await loadResult(reply.id);
    } catch (cause) { if (owner.current === expectedOwner) setError(cause instanceof Error ? cause.message : "Could not finish capture"); }
    finally { if (owner.current === expectedOwner) setBusy(false); }
  }

  async function capture() {
    const expectedOwner = owner.current;
    const version = ++requestVersion.current;
    const current = () => Boolean(expectedOwner) && owner.current === expectedOwner && requestVersion.current === version;
    setBusy(true); setError(""); setResult(null); setReport(null);
    try {
      if (!canSubmitEnhancedEvidence(gate)) throw new Error("Sign in on a supported source page before analyzing");
      if (linkedPage) {
        if (!canCapturePage) throw new Error("Start on a product, then open its linked company page.");
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab?.id || !current()) return;
        const reply = await chrome.runtime.sendMessage({ type: "CONTINUE_GUIDED", tabId: tab.id, ownerId: userId });
        if (!current()) return;
        if (!reply?.id) throw new Error(reply?.error || "Company capture failed");
        const stored = await chrome.storage.local.get("collectionJob");
        setCollectionJob(restoreCollectionJob(stored.collectionJob, userId!));
        await loadResult(reply.id);
        return;
      }
      // Request optional source access in the button's user gesture. Declining
      // it keeps the product-only collection path available.
      if (page.status === "supported" && page.kind === "1688") {
        await chrome.permissions.request({ origins: ["https://*.1688.com/*"] }).catch(() => false);
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!current()) return;
        if (!tab?.id || supportedOffer(tab.url || "")?.sourceUrl !== page.sourceUrl) throw new Error("The active product changed; try again");
        const reply = await chrome.runtime.sendMessage({ type: "START_COLLECTION", tabId: tab.id,
          ownerId: userId, sourceUrl: page.sourceUrl });
        if (!current()) return;
        if (!reply?.id) throw new Error(reply?.error || "Could not start collection");
        const last = { analysisId: reply.id, sourceUrl: page.sourceUrl, ownerId: userId! };
        setLastCapture(last);
        const stored = await chrome.storage.local.get("collectionJob");
        setCollectionJob(restoreCollectionJob(stored.collectionJob, userId!));
        await loadResult(reply.id);
        return;
      }
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!current()) return;
      const offer = tab?.url ? supportedOffer(tab.url) : null;
      if (!tab?.id || !offer) throw new Error("Open a supported 1688 offer or Taobao item/shop first");
      const token = await getToken({ skipCache: true });
      if (!current()) return;
      if (!token) throw new Error("Sign in before capturing evidence");
      if (!userId) throw new Error("Sign in before capturing evidence");
      const [injected] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: captureSelectedDom });
      if (!current()) return;
      const evidence = injected?.result;
      if (!evidence || offer.offerId !== ("offer_id" in evidence ? evidence.offer_id : evidence.source_id) || offer.sourceUrl !== evidence.source_url) {
        throw new Error("The active offer changed; try again");
      }
      assertPermittedEvidence(evidence);
      let created;
      try {
        created = await submitBrowserEvidence(
          evidence,
          { getToken: async () => token },
          { origin: VCT_WEB_ORIGIN, timeoutMs: 45_000 },
        );
      } catch (cause) {
        if (cause instanceof ApiError && cause.status === 408) {
          throw new Error("Capture timed out. It may have been saved; submitting again may use another quota slot.");
        }
        throw cause;
      }
      if (!current()) return;
      const last = { analysisId: created.id, sourceUrl: evidence.source_url, ownerId: userId };
      setLastCapture(last);
      await saveOpenAndLoadResult(last, {
        save: record => current() ? chrome.storage.local.set({ [LAST_CAPTURE_KEY]: record }) : Promise.resolve(),
        storageFailed: () => { if (current()) setError("Evidence was saved, but the last result link could not be kept. Keep the web result tab open."); },
        open: id => current() ? chrome.tabs.create({ url: `${VCT_WEB_ORIGIN}/?analysis=${encodeURIComponent(id)}` }) : Promise.resolve(),
        load: id => current() ? loadResult(id) : Promise.resolve(),
      });
    } catch (cause) {
      if (owner.current === expectedOwner) setError(cause instanceof Error ? cause.message : "Capture failed");
    } finally { if (owner.current === expectedOwner) setBusy(false); }
  }

  useEffect(() => {
    if (!isSignedIn || !lastCapture || !result || !verdict.poll) return;
    let active = true;
    let pending = false;
    const timer = setInterval(() => {
      if (!active || pending) return;
      pending = true;
      void loadResult(lastCapture.analysisId).catch(cause => {
        if (active) setError(cause instanceof Error ? cause.message : "Could not update analysis");
      }).finally(() => { pending = false; });
    }, 3000);
    return () => { active = false; clearInterval(timer); };
  }, [isSignedIn, lastCapture?.analysisId, result?.status]);

  return <main lang={language}>
    <header className="popup-header"><div><span className="eyebrow">{t("Source evidence")}</span><h1>VCT Connect</h1></div><div className="language-switch" role="group" aria-label="Language / Ngôn ngữ"><button aria-pressed={language === "vi"} onClick={() => chooseLanguage("vi")}>VI</button><button aria-pressed={language === "en"} onClick={() => chooseLanguage("en")}>EN</button></div></header>
    <p className="intro">{t("Capture product, shop and factory evidence for one supplier report.")}</p>
    {page.status === "supported"
      ? <p className="page-state">✓ {t("Supported page")} · {t(page.kind === "1688-company" || page.kind === "taobao-shop" ? "Shop" : page.kind === "1688-factory" ? "Factory" : "Product")}</p>
      : page.status === "unsupported"
        ? <p className="page-state">{t("Open a supported product, shop or linked factory page.")}</p>
        : <p className="page-state">{t("Checking the active page…")}</p>}
    {gate === "loading-auth" ? <>
      <p>{t(signInDelayed ? "Sign-in is taking longer than expected. Sign in on the web, then reopen this popup." : "Checking your VCT Connect session…")}</p>
      {signInDelayed && <button onClick={() => void openWebSignIn()}>{t("Open VCT Connect")}</button>}
    </> : gate === "signed-out" ? <>
      <button onClick={() => void openWebSignIn()}>{t("Sign in on VCT Connect")}</button>
      <p>{t("Sign in on the web, then reopen this extension in the same browser profile.")}</p>
    </> : <>
      <UserButton />
      {gate === "checking-page" && <p>{t("Checking the active page…")}</p>}
      {gate === "unsupported-page" && <p>{t("This page cannot be captured. Open a supported source.")}</p>}
      {gate === "ready" && <p><button className="primary-action" disabled={busy || Boolean(collecting) || !canCapturePage} onClick={() => void capture()}>{t(busy || collecting ? "Working…" : collectionJob?.stage === "FINISHING" ? "Retry saved upload" : linkedPage && page.status === "supported" ? page.kind === "1688-factory" ? "Save factory HTML & analyze" : "Save shop HTML" : "Analyze this page")}</button></p>}
      {gate === "ready" && page.status === "supported" && page.kind === "1688" && !guidedWaiting && <p className="capture-note">{t("Capture the product first. Then follow the supplier cue to save shop and factory HTML. Finish within 30 minutes.")}</p>}
    </>}
    {isSignedIn && linkedPage && !canCapturePage && <p>{t("Start from a product and follow its linked supplier page.")}</p>}
    {isSignedIn && guidedWaiting && collectionJob && <div className="status" aria-live="polite">
      <ol className="capture-steps" aria-label={t("Source evidence")}>{["Product", "Shop", "Factory"].map((step, i) => <li key={step} className={i === (collectionJob.stage === "WAITING_COMPANY" ? 1 : 2) ? "current" : ""}><span>{i + 1}</span>{t(step)}</li>)}</ol>
      <strong>{t(collectionJob.stage === "FINISHING" ? "Capture saved · retry upload" : collectionJob.stage === "WAITING_FACTORY" ? "Shop saved · factory next" : "Product captured · shop next")}</strong>
      <p>{t(collectionJob.stage === "FINISHING" ? "Retry the stored upload. Your evidence and analysis ID are retained." : collectionJob.stage === "WAITING_FACTORY" ? "Open Factory profile / 工厂档案 from the shop. When factory details are visible, save factory HTML to complete the report." : "Open the supplier shop using the link below or the highlighted name. If an overlay covers visible company content, close it with X, then save shop HTML.")}</p>
      {collectionJob.error && <p role="status">{errorText(collectionJob.error, language)}</p>}
      {collectionJob.factoryUrl && <p><a href={collectionJob.factoryUrl} target="_blank" rel="noreferrer">{t("Open linked factory profile")} ↗</a></p>}
      {collectionJob.companyUrl && <p><a href={collectionJob.companyUrl} target="_blank" rel="noreferrer">{t("Open linked company page")} ↗</a></p>}
      <p><button className="secondary-action" disabled={busy} onClick={() => void finishGuided()}>{t(collectionJob.stage === "FINISHING" ? "Retry saved upload" : collectionJob.stage === "WAITING_FACTORY" ? "Finish with captured product & shop" : "Finish with product evidence only")}</button></p>
      <small>{t("One analysis. HTML is downloaded at each capture and uploaded together when you finish. Only visible content is collected.")}</small>
    </div>}
    {error && <div className="error" role="alert"><p>{errorText(error, language)}</p>{language === "vi" && <details><summary>{t("Technical details")}</summary><p>{error}</p></details>}</div>}
    {isSignedIn && collectionJob?.ownerId === userId && !guidedWaiting && !error && <div className="status" aria-live="polite">
      <strong>{t(collectionJob.stage === "ERROR" ? "Collection interrupted" : collecting ?
        ({ STARTING: "Reading product", SHOP: "Reading supplier shop", FACTORY: "Reading factory profile" } as Record<string, string>)[collectionJob.stage]
        : collectionJob.stage === "ASSESSING" ? "Capture finished · assessment continues" : "Collection deadline reached")}</strong>
      <p>{collectionJob.error ? errorText(collectionJob.error, language) : t("You can close this popup. Open the web result to follow assessment and reporting.")}</p>
    </div>}
    {isSignedIn && lastCapture?.ownerId === userId && result && !guidedWaiting && <div className="status" aria-live="polite">
      <strong>{t(verdict.headline)}</strong>
      <p>{t(result.status === "COMPLETED" && reportLoading ? "Loading saved assessment report…" : verdict.detail)}</p>
      {result.supplier_data && <p>{result.supplier_data.supplier_name || t("Supplier name missing")} · {t("Extraction coverage")}: {Math.round(result.supplier_data.completeness * 100)}%</p>}
      {verdict.riskLabel && <p>{t("Risk")}: {t(verdict.riskLabel)}{verdict.confidence !== null ? ` · ${t("Confidence")}: ${Math.round(verdict.confidence * 100)}%` : ""}{verdict.coverage !== null ? ` · ${t("Coverage")}: ${Math.round(verdict.coverage * 100)}%` : ""}</p>}
      {result.status === "COMPLETED" && !reportLoading && verdict.riskLabel === null && <small>{t("No scored report available. Missing evidence is not low risk.")}</small>}
    </div>}
    {isSignedIn && lastCapture?.ownerId === userId && lastCapture && <div className="status">
      <small>{t("Last page")}: {lastCapture.sourceUrl}</small>
      {isSignedIn && <p><button className="secondary-action" disabled={busy} onClick={() => void retryResult()}>{t("Reload last result")}</button></p>}
      <p><button onClick={() => void chrome.tabs.create({ url: `${VCT_WEB_ORIGIN}/?analysis=${encodeURIComponent(lastCapture.analysisId)}` })}>{t("Open web result")}</button></p>
      <small>{t("Use the same VCT Connect account to view this report.")}</small>
    </div>}
  </main>;
}

const root = document.getElementById("root");
function ExtensionRoot() {
  const [language, setLanguage] = useState<UiLanguage>("vi");
  useEffect(() => {
    void chrome.storage.local.get("uiLanguage").then(stored => {
      if (stored.uiLanguage === "vi" || stored.uiLanguage === "en") setLanguage(stored.uiLanguage);
    }).catch(() => {});
  }, []);
  return <ClerkProvider publishableKey={VCT_CLERK_PUBLISHABLE_KEY}
    localization={language === "vi" ? viVN : enUS}
    syncHost={VCT_CLERK_SYNC_HOST}
    afterSignOutUrl={VCT_WEB_ORIGIN}
    signInFallbackRedirectUrl={VCT_WEB_ORIGIN}
    signUpFallbackRedirectUrl={VCT_WEB_ORIGIN}>
    <App initialLanguage={language} onLanguageChange={setLanguage} />
  </ClerkProvider>;
}
if (root) createRoot(root).render(<ExtensionRoot />);
