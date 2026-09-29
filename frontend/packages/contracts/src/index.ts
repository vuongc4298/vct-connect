export const FIXTURE_URL = "https://detail.1688.com/offer/123456789012.html";

export type AnalysisStatus =
  | "QUEUED"
  | "PROCESSING"
  | "FAILED_RETRYABLE"
  | "FAILED_FINAL"
  | "COMPLETED";
export type FinalDisposition = "DLQ_PENDING" | "DEAD_LETTERED" | "PUBLICATION_FAILED";
export type AnalysisStatusEvent = {
  status: AnalysisStatus;
  attempt: number;
  failure_code: string | null;
  next_retry_at: string | null;
  disposition: FinalDisposition | null;
  created_at: string;
};
export type SubmitAnalysisRequest = { source_url: string };
export type SubmitAnalysisResponse = { id: string; status: "QUEUED" };
export type SubmitGuestAnalysisRequest = SubmitAnalysisRequest;
export type SubmitGuestAnalysisResponse = SubmitAnalysisResponse;
export type AnalysisMode = "GUEST_PUBLIC" | "ACCOUNT_PUBLIC" | "EXTENSION_ENHANCED";
export type AnalysisActor = "GUEST" | "CUSTOMER" | "LEGACY";
export type FixtureResult = {
  source_url: string;
  supplier_name: string;
  fixture: true;
};
export type Analysis = {
  id: string;
  source_url: string;
  status: AnalysisStatus;
  created_at: string;
  completed_at: string | null;
  attempt_count: number;
  failure_code: string | null;
  next_retry_at: string | null;
  final_disposition: FinalDisposition | null;
  mode: AnalysisMode;
  actor_type: AnalysisActor;
  extraction_method: string;
  scoring_version: string;
  events: AnalysisStatusEvent[];
  result: FixtureResult | null;
};
