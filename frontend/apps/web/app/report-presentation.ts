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

export const REPORT_FINDING_LABELS: Record<string, string> = {
  SUPPLIER_RISK: "Rủi ro nhà cung cấp", SUPPLIER_POSITIVE: "Tín hiệu tích cực",
  SUPPLIER_UNCERTAINTY: "Điểm chưa chắc chắn", IDENTITY_CONTRADICTION: "Thông tin danh tính mâu thuẫn",
};

export const FACTORY_CLASSIFICATION_LABELS: Record<string, string> = {
  FACTORY: "Nhà máy", TRADER: "Thương mại", MIXED: "Kết hợp", UNCERTAIN: "Chưa xác định",
  FACTORY_LIKELY: "Nghiêng về nhà máy", TRADER_LIKELY: "Nghiêng về thương mại",
};

export const REPORT_SOURCE_KIND_LABELS: Record<string, string> = {
  SUPPLIER_DATA: "Dữ liệu nhà cung cấp",
  REVIEW: "Đánh giá người mua",
  REVIEW_MEDIA: "Ảnh / video đánh giá",
  PLATFORM_PROFILE: "Hồ sơ nền tảng",
  DERIVED: "Tín hiệu suy luận xác định",
  MODEL_INTERPRETATION: "Diễn giải có cấu trúc",
};

export const REPORT_FIELD_LABELS: Record<string, string> = {
  page_context: "Ngữ cảnh trang đã thu thập",
  supplier_name: "Tên nhà cung cấp", company_information: "Hồ sơ công ty",
  years_active: "Thời gian hoạt động", certifications: "Chứng nhận",
  activity_history: "Lịch sử hoạt động", products: "Sản phẩm",
  reviews: "Đánh giá người mua", rating: "Điểm đánh giá",
  transaction_signals: "Giao dịch", delivery_information: "Giao hàng",
  price_information: "Giá và điều khoản", categories: "Ngành hàng",
  html_capture_status: "Trang đã thu thập", collection_status: "Nguồn đã truy cập",
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

export function reportSourceContent(payload: Record<string, unknown>): string | null {
  if (typeof payload.text === "string" && payload.text.trim()) return payload.text;
  const value = payload.value;
  if (value === null || value === undefined || value === "" || (Array.isArray(value) && !value.length)) return null;
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}
