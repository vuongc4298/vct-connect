import { supportedOffer } from "./capture";

export type LastCapture = { analysisId: string; sourceUrl: string; ownerId: string };

export function restoreLastCapture(value: unknown, ownerId: string | null | undefined): LastCapture | null {
  if (!ownerId || !value || typeof value !== "object") return null;
  const record = value as Partial<LastCapture>;
  if (typeof record.analysisId !== "string" || typeof record.sourceUrl !== "string" || record.ownerId !== ownerId
      || !supportedOffer(record.sourceUrl)) return null;
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
