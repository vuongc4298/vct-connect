import { importSavedPage, submitAnalysis, type RequestAuth } from "@vct/api-client";

export function submitSelectedAnalysis(sourceUrl: string, savedPage: File | null, auth: RequestAuth) {
  return savedPage
    ? importSavedPage(sourceUrl, savedPage, auth)
    : submitAnalysis({ source_url: sourceUrl }, auth);
}
