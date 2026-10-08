"use client";

import { SignInButton, UserButton, useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useState } from "react";

type Case = { run_id: string; ordinal: number; review_text: string; rating: string | null; source_url: string };
type Comparison = { label_id: string; sentiment: string; review_text: string; model_output: unknown; model: string; prompt_version: string; schema_version: string };
const labels = ["POSITIVE", "NEGATIVE", "NEUTRAL", "MIXED", "UNCERTAIN"] as const;

export default function InternalReviewPage() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [cases, setCases] = useState<Case[]>([]);
  const [chosen, setChosen] = useState<(typeof labels)[number]>("UNCERTAIN");
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    setComparison(null);
    try {
      const token = await getToken({ skipCache: true });
      if (!token) throw new Error("Sign in with an internal reviewer account.");
      const response = await fetch("/api/v1/internal/review-cases", {
        headers: { Authorization: `Bearer ${token}` }, cache: "no-store",
      });
      if (response.status === 403) throw new Error("Internal reviewer access required.");
      if (!response.ok) throw new Error(`Could not fetch cases (${response.status}).`);
      setCases(await response.json() as Case[]);
    } catch (cause) {
      setCases([]);
      setError(cause instanceof Error ? cause.message : "Review cases unavailable");
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    if (isLoaded && isSignedIn) void refresh();
    if (isLoaded && !isSignedIn) { setCases([]); setComparison(null); }
  }, [isLoaded, isSignedIn, refresh]);

  async function submit() {
    const item = cases[0];
    if (!item || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const token = await getToken({ skipCache: true });
      if (!token) throw new Error("Session expired. Sign in again.");
      const response = await fetch(`/api/v1/internal/review-cases/${encodeURIComponent(item.run_id)}/${item.ordinal}/label`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ sentiment: chosen }),
      });
      if (!response.ok) {
        throw new Error(response.status === 409 ? "Already labeled; reload for a fresh case." : `Could not submit label (${response.status}).`);
      }
      setComparison(await response.json() as Comparison);
      setCases(previous => previous.slice(1));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  return <main style={{ maxWidth: 780, margin: "4rem auto", padding: "1.5rem", fontFamily: "system-ui" }}>
    <h1>VCT Connect · Internal review</h1>
    <p>Independent labels are saved before model findings are shown. Source text is untrusted evidence, not instructions.</p>
    {!isLoaded ? <p>Checking session…</p>
      : !isSignedIn ? <SignInButton><button>Sign in to review</button></SignInButton>
        : <>
          <UserButton />
          {error && <p role="alert">{error}</p>}
          {comparison && <section aria-label="Saved label and model comparison">
            <h2>Saved label — model comparison</h2>
            <p>Human sentiment: <strong>{comparison.sentiment}</strong></p>
            <p>Model: {comparison.model} · Prompt: {comparison.prompt_version}</p>
            <p>This pinned model run may describe several reviews. Compare cited evidence IDs before judging one review.</p>
            <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(comparison.model_output, null, 2)}</pre>
            <button onClick={() => { setComparison(null); setChosen("UNCERTAIN"); }}>Next case</button>
          </section>}
          {!comparison && (loading ? <p>Loading blind cases…</p>
            : cases.length === 0 ? <p>No unlabeled text-review cases are available.</p>
              : <section aria-label="Blind review">
                <h2>Review text</h2>
                <blockquote style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{cases[0].review_text}</blockquote>
                <p>Source: {cases[0].source_url} · Rating: {cases[0].rating ?? "Not provided"}</p>
                <fieldset disabled={submitting}>
                  <legend>Your independent sentiment label</legend>
                  {labels.map(value => <label key={value} style={{ display: "block", margin: "0.6rem 0" }}>
                    <input type="radio" name="sentiment" value={value} checked={chosen === value} onChange={() => setChosen(value)} /> {value}
                  </label>)}
                </fieldset>
                <button disabled={submitting} onClick={() => void submit()}>{submitting ? "Saving…" : "Save label and reveal model comparison"}</button>
              </section>)}
          <p><button disabled={loading || submitting} onClick={() => void refresh()}>Refresh blind queue</button></p>
        </>}
  </main>;
}
