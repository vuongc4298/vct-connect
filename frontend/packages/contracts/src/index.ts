export const FIXTURE_URL = "https://detail.1688.com/offer/123456789012.html";

export type AnalysisStatus =
  | "QUEUED"
  | "PROCESSING"
  | "ASSESSING"
  | "REPORTING"
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
export type ImportSavedPageResponse = { id: string; status: "COMPLETED" };
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
export type SourceMetric = { label: string; value: string; scope: string; description?: string };
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
  products: Array<{ offer_id: string | null; title: string | null; source_url?: string; attributes?: Array<{ name: string; value: string }>; price_display_text?: string | null; minimum_order_display_text?: string | null }> | null;
  price_information: {
    minimum?: string; maximum?: string; minimum_order_quantity?: number; display_text?: string;
    price?: { priceText: string | null; priceTitle: string | null; priceUnit: string | null; priceDesc: string | null };
    extraPrice?: { priceText: string | null; priceTitle: string | null; priceUnit: string | null; priceDesc: string | null };
    starting_price_text?: string;
    currency?: string; unit?: string;
  } | null;
  transaction_signals: {
    review_count?: number; positive_review_rate?: number; repeat_purchase_rate?: string;
    sales_display_text?: string; review_count_display_text?: string; positive_review_rate_display_text?: string;
    shop_metrics_display_text?: string[];
    shop_evaluations?: Array<{ type: string | null; title: string | null; score: string | null; levelText: string | null }>;
    source_metrics?: SourceMetric[];
  } | null;
  rating: number | null;
  reviews: Array<Record<string, unknown>> | null;
  delivery_information: { source_metrics?: SourceMetric[]; lead_times?: Array<{ minQuantity: number; maxQuantity: number; processPeriod: number }>; [key: string]: unknown } | null;
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
  raw_evidence: (
    { source_url: string; captured_at: string | null; imported_at?: string; html_sha256: string;
      rendered_html_sha256?: string; rendered_at?: string; extraction_method?: string; extractor_version?: string;
      public_fields: Record<string, unknown> }
    | { source_url: string; captured_at: string; provenance: "USER_PROVIDED_BROWSER_EVIDENCE"; selected_fields: Record<string, unknown>;
        merged_from_snapshot_id?: string; merged_from_extracted_at?: string;
        merged_from_extraction_method?: string; field_sources?: Record<string, string[]>;
        source_snapshots?: Record<string, { extracted_at: string; extraction_method: string }>;
        dict_key_sources?: Record<string, Record<string, string[]>>;
        item_sources?: Record<string, Record<string, string[]>>;
        omitted_review_count?: number; omitted_product_count?: number }
  ) | null;
  reviews: Array<Record<string, unknown>>;
};


export type ReportRiskLabel = "LOW" | "MODERATE" | "HIGH" | "INSUFFICIENT_INFORMATION";

export type ReportEvidence = {
  evidence_id: string;
  source_kind: string;
  source_field: string | null;
  payload: Record<string, unknown>;
};

export type ReportFinding = {
  finding_key: string;
  finding_type: string;
  dimension: string | null;
  severity: number | null;
  confidence: number | null;
  evidence_ids: string[];
  payload: Record<string, unknown>;
};

export type ReportRisk = {
  overall_risk: number | null;
  label: ReportRiskLabel;
  confidence: number;
  coverage: number;
  scoring_version: string;
  dimensions: Array<Record<string, unknown>>;
};

export type ReportV1 = {
  schema_version: "report.v1";
  language: "vi";
  analysis_id: string;
  source_url: string;
  platform: string;
  extracted_at: string;
  supplier_name: string | null;
  platform_supplier_id: string | null;
  supplier_summary_vi: string;
  risk: ReportRisk;
  factory_trader: Record<string, unknown>;
  review_summary: Record<string, unknown>;
  key_risks: ReportFinding[];
  positive_signals: ReportFinding[];
  other_findings: ReportFinding[];
  evidence: ReportEvidence[];
  missing_data: {
    source_fields: string[];
    risk_dimensions: string[];
    uncertainties_vi: string[];
    [key: string]: string[];
  };
  limitations_vi: string[];
  recommended_actions_vi: string[];
};
