import { ClerkProvider, UserButton, useAuth } from "@clerk/chrome-extension";
import { ApiError, getAnalysis, submitBrowserEvidence } from "@vct/api-client";
import type { Analysis } from "@vct/contracts";
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { assertPermittedEvidence, captureSelectedDom, supportedOffer } from "./capture";
import { restoreLastCapture, saveOpenAndLoadResult, type LastCapture } from "./capture-result";
import { canSubmitEnhancedEvidence, classifyExtensionPage, extensionGate, type ExtensionPageState } from "./extension-shell";

const LAST_CAPTURE_KEY = "lastCapture";

function openWebSignIn() {
  return chrome.tabs.create({ url: `${VCT_WEB_ORIGIN}/` });
}

function App() {
  const { getToken, isLoaded, isSignedIn, userId } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Analysis | null>(null);
  const [lastCapture, setLastCapture] = useState<LastCapture | null>(null);
  const [page, setPage] = useState<ExtensionPageState>({ status: "checking" });
  const [signInDelayed, setSignInDelayed] = useState(false);

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
    setLastCapture(null);
    setResult(null);
    setError("");
    if (!isLoaded || !userId) { setLastCapture(null); return; }
    let active = true;
    void chrome.storage.local.get(LAST_CAPTURE_KEY).then(stored => {
      const last = restoreLastCapture(stored[LAST_CAPTURE_KEY], userId);
      if (active && last) setLastCapture(last);
    }).catch(() => { if (active) setError("Could not restore the last result link"); });
    return () => { active = false; };
  }, [isLoaded, userId]);

  async function loadResult(analysisId: string) {
    try {
      const analysis = await getAnalysis(
        analysisId,
        { getToken: () => getToken({ skipCache: true }) },
        { origin: VCT_WEB_ORIGIN, timeoutMs: 45_000 },
      );
      setResult(analysis);
    } catch (cause) {
      if (cause instanceof ApiError) {
        if (cause.status === 401 || cause.status === 403 || cause.status === 404) {
          throw new Error("Could not load result. Sign into the same VCT Connect account.");
        }
        if (cause.status === 408) throw new Error("Result lookup timed out. Retry loading the last result.");
      }
      throw cause;
    }
  }

  async function retryResult() {
    if (!lastCapture) return;
    setBusy(true); setError("");
    try { await loadResult(lastCapture.analysisId); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load result"); }
    finally { setBusy(false); }
  }

  const gate = extensionGate({ authLoaded: isLoaded, signedIn: Boolean(isSignedIn), page });

  async function capture() {
    setBusy(true); setError(""); setResult(null);
    try {
      if (!canSubmitEnhancedEvidence(gate)) throw new Error("Sign in on a supported source page before analyzing");
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      const offer = tab?.url ? supportedOffer(tab.url) : null;
      if (!tab?.id || !offer) throw new Error("Open a supported 1688 offer or Taobao item/shop first");
      const token = await getToken({ skipCache: true });
      if (!token) throw new Error("Sign in before capturing evidence");
      if (!userId) throw new Error("Sign in before capturing evidence");
      const [injected] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: captureSelectedDom });
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
      const last = { analysisId: created.id, sourceUrl: evidence.source_url, ownerId: userId };
      setLastCapture(last);
      await saveOpenAndLoadResult(last, {
        save: record => chrome.storage.local.set({ [LAST_CAPTURE_KEY]: record }),
        storageFailed: () => setError("Evidence was saved, but the last result link could not be kept. Keep the web result tab open."),
        open: id => chrome.tabs.create({ url: `${VCT_WEB_ORIGIN}/?analysis=${encodeURIComponent(id)}` }),
        load: loadResult,
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Capture failed");
    } finally { setBusy(false); }
  }

  const extractionStatus = result?.result && "extraction_status" in result.result
    ? result.result.extraction_status
    : result?.status;
  const extractionReason = result?.result && "reason" in result.result && typeof result.result.reason === "string"
    ? result.result.reason
    : undefined;

  return <main>
    <h1>VCT Connect</h1>
    <p>Analyze selected visible evidence from a supported 1688 offer or Taobao item/shop.</p>
    {page.status === "supported"
      ? <p className="page-state">Supported page detected · {page.kind}</p>
      : page.status === "unsupported"
        ? <p className="page-state">This page is not supported. Open a 1688 offer or Taobao item/shop.</p>
        : <p className="page-state">Checking the active page…</p>}
    {gate === "loading-auth" ? <>
      <p>{signInDelayed ? "Sign-in is taking longer than expected. Sign in on the web, then close and reopen this popup." : "Checking your VCT Connect session…"}</p>
      {signInDelayed && <button onClick={() => void openWebSignIn()}>Open VCT Connect</button>}
    </> : gate === "signed-out" ? <>
      <button onClick={() => void openWebSignIn()}>Sign in on VCT Connect</button>
      <p>Finish sign-in in the web tab, then return to the source page and reopen this popup. Use the same Chrome profile.</p>
    </> : <>
      <UserButton />
      {gate === "checking-page" && <p>Checking whether this page can be analyzed…</p>}
      {gate === "unsupported-page" && <p>Enhanced analysis is disabled on unsupported pages.</p>}
      {gate === "ready" && <p><button disabled={busy} onClick={() => void capture()}>{busy ? "Working…" : "Analyze this page"}</button></p>}
    </>}
    {error && <p className="error" role="alert">{error}</p>}
    {isSignedIn && result && <div className="status">
      <strong>{extractionStatus}</strong>
      {result.supplier_data ? <p>{result.supplier_data.supplier_name || "Supplier name missing"}<br />Coverage: {Math.round(result.supplier_data.completeness * 100)}%<br />Missing: {result.supplier_data.missing_fields.join(", ") || "none"}</p>
        : <p>No selected supplier or product evidence was visible. {extractionReason}</p>}
      <small>User-provided browser evidence. No risk score is available.</small>
    </div>}
    {isSignedIn && lastCapture && <div className="status">
      <small>Last page: {lastCapture.sourceUrl}</small>
      {isSignedIn && <p><button disabled={busy} onClick={() => void retryResult()}>Reload last result</button></p>}
      <p><button onClick={() => void chrome.tabs.create({ url: `${VCT_WEB_ORIGIN}/?analysis=${encodeURIComponent(lastCapture.analysisId)}` })}>Open web result</button></p>
      <small>Sign into the same VCT Connect account on the web to view this result.</small>
    </div>}
  </main>;
}

createRoot(document.getElementById("root")!).render(
  <ClerkProvider publishableKey={VCT_CLERK_PUBLISHABLE_KEY}
    syncHost={VCT_CLERK_SYNC_HOST}
    afterSignOutUrl={VCT_WEB_ORIGIN}
    signInFallbackRedirectUrl={VCT_WEB_ORIGIN}
    signUpFallbackRedirectUrl={VCT_WEB_ORIGIN}>
    <App />
  </ClerkProvider>,
);
