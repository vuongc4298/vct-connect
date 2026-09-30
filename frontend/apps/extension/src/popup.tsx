import { ClerkProvider, UserButton, useAuth } from "@clerk/chrome-extension";
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { captureSelectedDom, supportedOffer } from "./capture";

type Result = {
  id: string;
  status: string;
  supplier_data: { completeness: number; missing_fields: string[]; supplier_name: string | null } | null;
  result: { extraction_status: string; reason?: string } | null;
};

type LastCapture = { analysisId: string; sourceUrl: string; ownerId: string };
const LAST_CAPTURE_KEY = "lastCapture";

function openWebSignIn() {
  return chrome.tabs.create({ url: `${VCT_WEB_ORIGIN}/` });
}

async function fetchWithTimeout(url: string, init: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 45_000);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (cause) {
    if (controller.signal.aborted) throw new Error(init.method === "POST"
      ? "Capture timed out. It may have been saved; submitting again may use another quota slot."
      : "Result lookup timed out. Retry loading the last result.");
    throw cause;
  } finally {
    clearTimeout(timer);
  }
}

function App() {
  const { getToken, isLoaded, isSignedIn, userId } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [lastCapture, setLastCapture] = useState<LastCapture | null>(null);
  const [signInDelayed, setSignInDelayed] = useState(false);

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
      const last = stored[LAST_CAPTURE_KEY] as LastCapture | undefined;
      if (active && last && typeof last.analysisId === "string" && typeof last.sourceUrl === "string"
          && last.ownerId === userId && supportedOffer(last.sourceUrl)) setLastCapture(last);
    }).catch(() => { if (active) setError("Could not restore the last result link"); });
    return () => { active = false; };
  }, [isLoaded, userId]);

  async function loadResult(analysisId: string) {
    const token = await getToken({ skipCache: true });
    if (!token) throw new Error("Sign in before loading the result");
    const status = await fetchWithTimeout(`${VCT_WEB_ORIGIN}/api/v1/analyses/${encodeURIComponent(analysisId)}`, {
      headers: { Authorization: `Bearer ${token}` }, cache: "no-store",
    });
    if (!status.ok) throw new Error(`Could not load result (${status.status}). Sign into the same VCT Connect account.`);
    setResult(await status.json());
  }

  async function retryResult() {
    if (!lastCapture) return;
    setBusy(true); setError("");
    try { await loadResult(lastCapture.analysisId); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load result"); }
    finally { setBusy(false); }
  }

  async function capture() {
    setBusy(true); setError(""); setResult(null);
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      const offer = tab?.url ? supportedOffer(tab.url) : null;
      if (!tab?.id || !offer) throw new Error("Open a supported 1688 offer first");
      const token = await getToken({ skipCache: true });
      if (!token) throw new Error("Sign in before capturing evidence");
      if (!userId) throw new Error("Sign in before capturing evidence");
      const [injected] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: captureSelectedDom });
      const evidence = injected?.result;
      if (!evidence || offer.offerId !== evidence.offer_id || offer.sourceUrl !== evidence.source_url) {
        throw new Error("The active offer changed; try again");
      }
      const response = await fetchWithTimeout(`${VCT_WEB_ORIGIN}/api/v1/analyses/capture`, {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(evidence),
      });
      const created = await response.json();
      if (!response.ok) throw new Error(typeof created.detail === "string" ? created.detail : `Capture failed (${response.status})`);
      if (typeof created.id !== "string") throw new Error("Capture returned no result ID");
      const last = { analysisId: created.id, sourceUrl: evidence.source_url, ownerId: userId };
      setLastCapture(last);
      await chrome.storage.local.set({ [LAST_CAPTURE_KEY]: last });
      await loadResult(created.id);
      await chrome.tabs.create({ url: `${VCT_WEB_ORIGIN}/?analysis=${encodeURIComponent(created.id)}` });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Capture failed");
    } finally { setBusy(false); }
  }

  return <main>
    <h1>VCT Connect</h1>
    <p>Capture selected visible evidence from the active 1688 offer.</p>
    {!isLoaded ? <>
      <p>{signInDelayed ? "Sign-in is taking longer than expected. Sign in on the web, then close and reopen this popup." : "Checking your VCT Connect session…"}</p>
      {signInDelayed && <button onClick={() => void openWebSignIn()}>Open VCT Connect</button>}
    </> : !isSignedIn ? <>
      <button onClick={() => void openWebSignIn()}>Sign in on VCT Connect</button>
      <p>Finish sign-in in the web tab, then return to the 1688 offer and reopen this popup. Use the same Chrome profile.</p>
    </> : <>
      <UserButton />
      <p><button disabled={busy} onClick={() => void capture()}>{busy ? "Working…" : "Capture this offer"}</button></p>
    </>}
    {error && <p className="error" role="alert">{error}</p>}
    {isSignedIn && result && <div className="status">
      <strong>{result.result?.extraction_status ?? result.status}</strong>
      {result.supplier_data ? <p>{result.supplier_data.supplier_name || "Supplier name missing"}<br />Coverage: {Math.round(result.supplier_data.completeness * 100)}%<br />Missing: {result.supplier_data.missing_fields.join(", ") || "none"}</p>
        : <p>No selected supplier or product evidence was visible. {result.result?.reason}</p>}
      <small>User-provided browser evidence. No risk score is available.</small>
    </div>}
    {isSignedIn && lastCapture && <div className="status">
      <small>Last offer: {lastCapture.sourceUrl}</small>
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
