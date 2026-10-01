import type { Analysis, ExtractionStatus } from "@vct/contracts";
import { sourceLabel } from "./source-url";

export function extractionRecovery(status: ExtractionStatus | null, reason?: string, sourceUrl?: string) {
  if (sourceLabel(sourceUrl) === "Alibaba") {
    if (status === "SUCCESS" || status === "PARTIAL" || status === null) return null;
    if (status === "AUTH_REQUIRED" || status === "BLOCKED") {
      return "Alibaba yêu cầu đăng nhập, xác minh truy cập hoặc địa chỉ nguồn không thể xác minh an toàn. Lần trích xuất này đã kết thúc. Hãy mở đúng trang nguồn để kiểm tra và tạo phân tích mới sau. Nhập HTML và tiện ích chụp trang Alibaba hiện chưa được hỗ trợ.";
    }
    return "Chưa thể lấy bằng chứng có thể xác minh từ Alibaba. Hãy kiểm tra URL HTTPS sản phẩm trên www.alibaba.com/product-detail/ hoặc hồ sơ công ty trên <store>.en.alibaba.com/company_profile.html và tạo phân tích mới sau. Nhập HTML và tiện ích chụp trang Alibaba hiện chưa được hỗ trợ.";
  }
  if (sourceLabel(sourceUrl) === "Taobao") {
    if (status === "SUCCESS" || status === "PARTIAL" || status === null) return null;
    if (reason && ["INVALID_URL", "UNSAFE_DESTINATION", "UNSAFE_REDIRECT", "SOURCE_MISMATCH", "REDIRECT_LOOP", "REDIRECT_LIMIT"].includes(reason)) {
      return "Địa chỉ nguồn hoặc chuyển hướng không thể xác minh an toàn cho sản phẩm / cửa hàng Taobao này. Hãy kiểm tra URL HTTPS và đúng mã sản phẩm / cửa hàng để tạo phân tích mới. Bạn có thể dùng tiện ích VCT Connect trên trang Taobao đang mở hoặc nhập trang HTML đã lưu với đúng URL nguồn.";
    }
    if (status === "AUTH_REQUIRED" || status === "BLOCKED") {
      return "Taobao yêu cầu đăng nhập hoặc xác minh truy cập. Lần trích xuất này đã kết thúc. Bạn có thể mở trang nguồn để kiểm tra và thử tạo phân tích mới sau. Bạn có thể dùng tiện ích VCT Connect trên trang Taobao đang mở hoặc nhập trang HTML đã lưu với đúng URL nguồn.";
    }
    return "Chưa thể lấy bằng chứng có thể xác minh từ Taobao. Hãy kiểm tra URL HTTPS của sản phẩm trên item.taobao.com hoặc cửa hàng shop<ID>.taobao.com / shop<ID>.world.taobao.com và thử tạo phân tích mới sau. Bạn có thể dùng tiện ích VCT Connect trên trang Taobao đang mở hoặc nhập trang HTML đã lưu với đúng URL nguồn.";
  }
  if (reason && ["INVALID_URL", "UNSAFE_DESTINATION", "UNSAFE_REDIRECT", "OFFER_MISMATCH", "REDIRECT_LOOP", "REDIRECT_LIMIT"].includes(reason)) {
    return "Địa chỉ nguồn hoặc chuyển hướng không thể xác minh an toàn cho sản phẩm này. Hãy kiểm tra URL HTTPS của trang sản phẩm trên detail.1688.com và tạo phân tích mới.";
  }
  if (status === "AUTH_REQUIRED" || status === "BLOCKED") {
    return "Mở trang nguồn 1688 trong trình duyệt, đăng nhập hoặc hoàn thành bước xác minh trên 1688. Sau đó dùng tiện ích VCT Connect để chụp dữ liệu đang hiển thị và gửi bằng chứng. Lần trích xuất này đã kết thúc.";
  }
  if (status === "TIMEOUT") {
    return "Trang nguồn phản hồi quá lâu; lần trích xuất này đã kết thúc. Bạn có thể tạo phân tích mới sau hoặc mở trang 1688 và dùng tiện ích VCT Connect để gửi bằng chứng.";
  }
  if (status === "UNSUPPORTED_PAGE") {
    return "Trang nguồn không còn khả dụng hoặc không phải trang sản phẩm được hỗ trợ. Hãy mở 1688, kiểm tra sản phẩm còn tồn tại và dùng URL trang sản phẩm để tạo phân tích mới.";
  }
  if (status === "PARSE_FAILED") {
    return reason && ["HTTP_ERROR", "UPSTREAM_UNAVAILABLE", "DNS_ERROR"].includes(reason)
      ? "Không thể tải bằng chứng từ trang nguồn; lần trích xuất này đã kết thúc. Bạn có thể tạo phân tích mới sau hoặc dùng tiện ích VCT Connect trên trang 1688 đang mở."
      : "Nội dung trang không cung cấp bằng chứng có thể xác minh. Hãy mở đúng trang sản phẩm 1688 và dùng tiện ích VCT Connect để gửi dữ liệu đang hiển thị.";
  }
  return null;
}

type StatusInput = Pick<Analysis, "status" | "attempt_count" | "failure_code"> &
  Partial<Pick<Analysis, "result" | "extraction_method" | "source_url">> | null;

export function analysisPresentation(analysis: StatusInput) {
  const status = analysis?.status ?? "QUEUED";
  const completedProcessing = status === "COMPLETED";
  const extractionStatus = analysis?.result && "extraction_status" in analysis.result
    ? analysis.result.extraction_status : null;
  const reason = analysis?.result && "reason" in analysis.result ? analysis.result.reason : undefined;
  const sourceUrl = analysis?.result?.source_url ?? analysis?.source_url;
  const source = sourceLabel(sourceUrl);
  const recovery = extractionRecovery(extractionStatus, reason, sourceUrl);
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
    headline: blocked ? `Chưa thể trích xuất trang ${source}` : complete && live ? "Bằng chứng đã được lưu" : complete ? "Báo cáo đã sẵn sàng" : final ? "Phân tích chưa thể hoàn tất" : retrying ? "Hệ thống sẽ thử lại" : processing ? live ? "Đang trích xuất bằng chứng" : "Đang xử lý dữ liệu demo" : "Đang chờ xử lý",
    detail: blocked ? `Trạng thái nguồn: ${extractionStatus ?? "UNKNOWN"}${reason ? ` · ${reason}` : ""}. Không có ảnh chụp bằng chứng cho URL này. ${recovery ?? "Bạn có thể tạo phân tích mới."}` : complete && live ? "Nguồn và độ phủ đã được ghi nhận; chưa có điểm rủi ro." : complete ? "Dữ liệu minh hoạ đã được tổng hợp." : final ? `Mã lỗi an toàn: ${analysis?.failure_code ?? "PROCESSING_ERROR"}. Bạn có thể tạo một phân tích mới.` : retrying ? `Lần thử ${analysis?.attempt_count ?? 1} chưa thành công. Hệ thống sẽ tự động thử lại.` : "Bạn có thể giữ trang này mở trong khi hệ thống xử lý.",
  } as const;
}
