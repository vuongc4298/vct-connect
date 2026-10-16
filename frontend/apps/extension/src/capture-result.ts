import { supportedOffer } from "./capture";
import type { Analysis, ReportV1 } from "@vct/contracts";
import { ApiError } from "@vct/api-client";

export async function loadScopedResult(analysisId: string, actions: {
  current: () => boolean;
  analysis: (id: string) => Promise<Analysis>;
  report: (id: string) => Promise<ReportV1>;
  publish: (analysis: Analysis, report: ReportV1 | null) => void;
}): Promise<void> {
  const analysis = await actions.analysis(analysisId);
  if (!actions.current()) return;
  actions.publish(analysis, null);
  if (analysis.status !== "COMPLETED") return;
  try {
    const report = await actions.report(analysisId);
    if (actions.current()) actions.publish(analysis, report);
  } catch (cause) {
    if (!actions.current() || cause instanceof ApiError && cause.status === 404) return;
    throw cause;
  }
}

export type LastCapture = { analysisId: string; sourceUrl: string; ownerId: string };

// Result recovery remains available while Taobao is paused for new captures.
function retainedTaobaoSource(value: string): boolean {
  return value === value.trim() && (/^https:\/\/item\.taobao\.com\/item\.htm\?id=[1-9][0-9]{0,19}$/.test(value)
    || /^https:\/\/shop[1-9][0-9]{0,19}\.(?:world\.)?taobao\.com\/(?:index\.htm|category\.htm)?$/.test(value));
}

export function restoreLastCapture(value: unknown, ownerId: string | null | undefined): LastCapture | null {
  if (!ownerId || !value || typeof value !== "object") return null;
  const record = value as Partial<LastCapture>;
  if (typeof record.analysisId !== "string" || typeof record.sourceUrl !== "string" || record.ownerId !== ownerId
      || !(supportedOffer(record.sourceUrl) || retainedTaobaoSource(record.sourceUrl))) return null;
  return { analysisId: record.analysisId, sourceUrl: record.sourceUrl, ownerId };
}

export async function saveOpenAndLoadResult(record: LastCapture, actions: {
  save: (record: LastCapture) => Promise<unknown>;
  open: (analysisId: string) => Promise<unknown>;
  load: (analysisId: string) => Promise<unknown>;
  storageFailed: () => void;
}): Promise<void> {
  try { await actions.save(record); }
  catch { actions.storageFailed(); }
  await actions.open(record.analysisId);
  await actions.load(record.analysisId);
}
