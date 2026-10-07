import type { ReportFinding, ReportRiskLabel } from "@vct/contracts";

export const REPORT_DIMENSION_LABELS: Record<string, string> = {
  PRODUCT_QUALITY: "Chất lượng sản phẩm",
  DELIVERY: "Giao hàng",
  AFTER_SALES: "Hậu mãi",
  REVIEW_MANIPULATION: "Độ tin cậy đánh giá",
  SUPPLIER_IDENTITY: "Danh tính nhà cung cấp",
  PRICING: "Giá và điều khoản",
  COMMUNICATION: "Giao tiếp",
};

export const REPORT_SOURCE_KIND_LABELS: Record<string, string> = {
  SUPPLIER_DATA: "Dữ liệu nhà cung cấp",
  REVIEW: "Đánh giá người mua",
  REVIEW_MEDIA: "Ảnh / video đánh giá",
  PLATFORM_PROFILE: "Hồ sơ nền tảng",
  DERIVED: "Tín hiệu suy luận xác định",
  MODEL_INTERPRETATION: "Diễn giải có cấu trúc",
};

export function reportPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function optionalReportPercent(value: unknown): string {
  return typeof value === "number" ? reportPercent(value) : "Chưa xác định";
}

export function reportBarWidth(value: unknown): string {
  if (typeof value !== "number") return "0%";
  return `${Math.max(0, Math.min(100, Math.round(value * 100)))}%`;
}

export function reportRiskLabel(label: ReportRiskLabel) {
  switch (label) {
    case "LOW": return { text: "RỦI RO THẤP", tone: "good" as const };
    case "MODERATE": return { text: "RỦI RO TRUNG BÌNH", tone: "warning" as const };
    case "HIGH": return { text: "RỦI RO CAO", tone: "danger" as const };
    default: return { text: "CHƯA ĐỦ THÔNG TIN", tone: "neutral" as const };
  }
}

export function reportEvidenceAnchor(id: string): string {
  return `evidence-${id.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

export function reportPayloadText(payload: Record<string, unknown>): string | null {
  for (const key of ["statement_vi", "statement", "title", "kind"]) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return null;
}

export function reportFindingTitle(finding: ReportFinding): string {
  return reportPayloadText(finding.payload)
    ?? REPORT_DIMENSION_LABELS[finding.dimension ?? ""]
    ?? finding.finding_type.replaceAll("_", " ");
}
