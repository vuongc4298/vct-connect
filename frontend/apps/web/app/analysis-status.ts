import type { Analysis } from "@vct/contracts";

type StatusInput = Pick<Analysis, "status" | "attempt_count" | "failure_code"> | null;

export function analysisPresentation(analysis: StatusInput) {
  const status = analysis?.status ?? "QUEUED";
  const complete = status === "COMPLETED";
  const final = status === "FAILED_FINAL";
  const retrying = status === "FAILED_RETRYABLE";
  const processing = status === "PROCESSING";
  return {
    complete,
    final,
    retrying,
    terminal: complete || final,
    shouldPoll: !complete && !final,
    orbClass: complete ? "complete" : final ? "failed" : "working",
    orbSymbol: complete ? "✓" : final ? "!" : "",
    pillTone: complete ? "good" : final || retrying ? "warning" : "neutral",
    pillLabel: complete ? "HOÀN TẤT" : final ? "DỪNG XỬ LÝ" : retrying ? "SẼ THỬ LẠI" : "ĐANG XỬ LÝ",
    headline: complete ? "Báo cáo đã sẵn sàng" : final ? "Phân tích chưa thể hoàn tất" : retrying ? "Hệ thống sẽ thử lại" : processing ? "Đang xử lý dữ liệu demo" : "Đang chờ xử lý",
    detail: complete ? "Dữ liệu minh hoạ đã được tổng hợp." : final ? `Mã lỗi an toàn: ${analysis?.failure_code ?? "PROCESSING_ERROR"}. Bạn có thể tạo một phân tích mới.` : retrying ? `Lần thử ${analysis?.attempt_count ?? 1} chưa thành công. Hệ thống sẽ tự động thử lại.` : "Bạn có thể giữ trang này mở trong khi hệ thống xử lý.",
  } as const;
}
