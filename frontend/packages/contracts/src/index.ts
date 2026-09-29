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
export type ExtractionStatus = "SUCCESS" | "PARTIAL" | "AUTH_REQUIRED" | "BLOCKED" | "UNSUPPORTED_PAGE" | "TIMEOUT" | "PARSE_FAILED";
export type SupplierData = {
  contract_version: "supplierdata.v1";
  platform: "1688" | "TAOBAO" | "ALIBABA";
  source_url: string;
  offer_id: string | null;
  extracted_at: string;
  extraction_method: string;
  analysis_mode: AnalysisMode;
  extractor_version: string;
  completeness: number;
  completeness_denominator: string[];
  missing_fields: string[];
  platform_supplier_id: string | null;
  supplier_name: string | null;
  company_information: Record<string, string> | null;
  years_active: number | null;
  categories: string[] | null;
  certifications: string[] | null;
  products: Array<{ offer_id: string | null; title: string | null }> | null;
  price_information: { minimum?: string; maximum?: string; minimum_order_quantity?: number } | null;
  transaction_signals: { review_count?: number; positive_review_rate?: number; repeat_purchase_rate?: string } | null;
  rating: number | null;
  reviews: Array<Record<string, unknown>> | null;
  delivery_information: Record<string, unknown> | null;
  activity_history: Array<Record<string, unknown>> | null;
};
export type ExtractionResult = {
  source_url: string;
  extraction_status: ExtractionStatus;
  reason?: string;
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
  result: FixtureResult | ExtractionResult | null;
  supplier_snapshot_id: string | null;
  supplier_data: SupplierData | null;
  raw_evidence: { source_url: string; captured_at: string; html_sha256: string; public_fields: Record<string, unknown> } | null;
  reviews: Array<Record<string, unknown>>;
};
