import type { ReportEvidence } from "@vct/contracts";

export const REMOVED_RISK_DIMENSIONS = new Set(["DELIVERY", "COMMUNICATION"]);
export function capturedReviewSummary(evidence: ReportEvidence[]) {
  const reviews = evidence.find(item => item.source_field === "reviews" && item.source_kind === "SUPPLIER_DATA")?.payload.value;
  const signals = evidence.find(item => item.source_field === "transaction_signals" && item.source_kind === "SUPPLIER_DATA")?.payload.value;
  const display = signals && typeof signals === "object" && !Array.isArray(signals)
    ? (signals as Record<string, unknown>).review_count_display_text : null;
  return { count: Array.isArray(reviews) ? reviews.length : null, totalDisplay: typeof display === "string" ? display : null };
}
const fields: Record<string, string[]> = {
  PRODUCT_QUALITY: ["reviews", "transaction_signals", "certifications"],
  SUPPLIER_IDENTITY: ["company_information", "certifications", "activity_history"],
  REVIEW_MANIPULATION: ["reviews", "rating", "transaction_signals"],
  AFTER_SALES: ["reviews", "transaction_signals", "company_information"],
  PRICING: ["price_information"],
};

export function dimensionEvidence(dimension: string, evidence: ReportEvidence[]) {
  const captured = evidence.filter(item => item.source_kind === "SUPPLIER_DATA" &&
    fields[dimension]?.includes(item.source_field ?? "") &&
    item.payload.value !== null && item.payload.value !== undefined && item.payload.value !== "" &&
    JSON.stringify(item.payload.value) !== "[]" && JSON.stringify(item.payload.value) !== "{}");
  let explanation = captured.length ? "Đã thu thập dữ liệu liên quan, nhưng chưa đủ cơ sở chấm điểm hạng mục này." : "Chưa có dữ liệu nguồn phù hợp để đánh giá.";
  if (dimension === "PRICING" && captured.length)
    explanation = "Đã thu thập giá và điều kiện hiển thị. Cần đối chiếu mức giá, số lượng tối thiểu, ưu đãi và điều khoản thanh toán trước khi kết luận.";
  if (dimension === "REVIEW_MANIPULATION" && captured.length) {
    const { count, totalDisplay } = capturedReviewSummary(evidence);
    explanation = `${count === null ? "Đã thu thập dữ liệu đánh giá." : `Đã thu thập ${count} đánh giá trong mẫu.`}${totalDisplay ? ` Tổng đánh giá hiển thị trên nguồn: ${totalDisplay}.` : ""} Số lượng và điểm đánh giá không tự xác minh tính xác thực; mẫu đánh giá liên quan có thể có thiên lệch lựa chọn.`;
  }
  return { captured, explanation };
}
