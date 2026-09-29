import type { Analysis } from "@vct/contracts";

type StatusInput = Pick<Analysis, "status" | "attempt_count" | "failure_code"> &
  Partial<Pick<Analysis, "result" | "extraction_method">> | null;

export function analysisPresentation(analysis: StatusInput) {
  const status = analysis?.status ?? "QUEUED";
  const completedProcessing = status === "COMPLETED";
  const extractionStatus = analysis?.result && "extraction_status" in analysis.result
    ? analysis.result.extraction_status : null;
  const live = analysis?.extraction_method === "PUBLIC_HTTP" || extractionStatus !== null;
  const blocked = completedProcessing && live && extractionStatus !== "SUCCESS" && extractionStatus !== "PARTIAL";
  const complete = completedProcessing && !blocked;
  const final = status === "FAILED_FINAL" || blocked;
  const retrying = status === "FAILED_RETRYABLE";
  const processing = status === "PROCESSING";
  return {
    complete,
    final,
    retrying,
    terminal: completedProcessing || final,
    shouldPoll: !completedProcessing && !final,
    orbClass: complete ? "complete" : final ? "failed" : "working",
    orbSymbol: complete ? "✓" : final ? "!" : "",
    pillTone: blocked || extractionStatus === "PARTIAL" || final || retrying ? "warning" : complete ? "good" : "neutral",
    pillLabel: blocked ? "KHÔNG CÓ DỮ LIỆU" : complete && live ? extractionStatus === "PARTIAL" ? "TRÍCH XUẤT MỘT PHẦN" : "ĐÃ TRÍCH XUẤT" : complete ? "HOÀN TẤT" : final ? "DỪNG XỬ LÝ" : retrying ? "SẼ THỬ LẠI" : "ĐANG XỬ LÝ",
    headline: blocked ? "Chưa thể trích xuất trang 1688" : complete && live ? "Bằng chứng đã được lưu" : complete ? "Báo cáo đã sẵn sàng" : final ? "Phân tích chưa thể hoàn tất" : retrying ? "Hệ thống sẽ thử lại" : processing ? live ? "Đang trích xuất bằng chứng" : "Đang xử lý dữ liệu demo" : "Đang chờ xử lý",
    detail: blocked ? `Trạng thái nguồn: ${extractionStatus ?? "UNKNOWN"}. Không có ảnh chụp bằng chứng cho URL này.` : complete && live ? "Nguồn và độ phủ đã được ghi nhận; chưa có điểm rủi ro." : complete ? "Dữ liệu minh hoạ đã được tổng hợp." : final ? `Mã lỗi an toàn: ${analysis?.failure_code ?? "PROCESSING_ERROR"}. Bạn có thể tạo một phân tích mới.` : retrying ? `Lần thử ${analysis?.attempt_count ?? 1} chưa thành công. Hệ thống sẽ tự động thử lại.` : "Bạn có thể giữ trang này mở trong khi hệ thống xử lý.",
  } as const;
}
