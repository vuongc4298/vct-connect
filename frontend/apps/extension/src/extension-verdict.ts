import type { Analysis, ReportV1 } from "@vct/contracts";

export type ExtensionVerdict = {
  headline: string;
  detail: string;
  terminal: boolean;
  poll: boolean;
  riskLabel: string | null;
  confidence: number | null;
  coverage: number | null;
};

export function extensionVerdict(analysis: Analysis | null, report: ReportV1 | null): ExtensionVerdict {
  if (!analysis) return { headline: "Loading analysis", detail: "Retrieving the latest saved state.", terminal: false, poll: true, riskLabel: null, confidence: null, coverage: null };
  const status = analysis.status;
  const validReport = status === "COMPLETED" && report?.analysis_id === analysis.id ? report : null;
  const extraction = analysis.result && "extraction_status" in analysis.result ? analysis.result.extraction_status : null;
  const reason = analysis.result && "reason" in analysis.result ? analysis.result.reason : null;
  const blocked = status === "COMPLETED" && extraction !== null && extraction !== "SUCCESS" && extraction !== "PARTIAL";
  const terminal = status === "COMPLETED" || status === "FAILED_FINAL";
  const states: Record<string, string> = {
    QUEUED: "Queued for analysis",
    PROCESSING: "Extracting source evidence",
    ASSESSING: "Assessing evidence",
    REPORTING: "Preparing report",
    FAILED_RETRYABLE: "Retry scheduled",
    FAILED_FINAL: "Analysis failed",
    COMPLETED: "Analysis completed",
  };
  const headline = blocked ? "Source evidence unavailable" : states[status];
  const detail = blocked ? `Extraction: ${extraction} ${reason ?? ""}`.trim()
    : status === "FAILED_FINAL" ? `Processing stopped (${analysis.failure_code ?? "PROCESSING_ERROR"}).`
    : status === "FAILED_RETRYABLE" ? "The system will retry; do not submit again."
    : status === "COMPLETED" && !validReport ? "Saved extraction result available. A full assessment report is not available."
    : "The report will update when processing reaches the next stage.";
  const label = validReport?.risk.label ?? null;
  const riskLabel = label === "INSUFFICIENT_INFORMATION" ? "Insufficient information"
    : label === "LOW" ? "Low" : label === "MODERATE" ? "Moderate" : label === "HIGH" ? "High" : null;
  return { headline, detail, terminal, poll: !terminal, riskLabel,
    confidence: validReport?.risk.confidence ?? null, coverage: validReport?.risk.coverage ?? null };
}
