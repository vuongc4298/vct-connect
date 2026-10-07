import React, { useMemo, useState } from "react";
import type { AnalysisHistoryItem, AnalysisStatus, ReportRiskLabel } from "@vct/contracts";

function date(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return "Chưa xác định";
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function statusLabel(status: AnalysisStatus) {
  switch (status) {
    case "QUEUED": return "Đang xếp hàng";
    case "PROCESSING": return "Đang trích xuất";
    case "ASSESSING": return "Đang đánh giá";
    case "REPORTING": return "Đang tạo báo cáo";
    case "FAILED_RETRYABLE": return "Đang thử lại";
    case "FAILED_FINAL": return "Không hoàn tất";
    case "COMPLETED": return "Hoàn tất";
  }
}

function riskLabel(label: ReportRiskLabel | null) {
  switch (label) {
    case "LOW": return "Rủi ro thấp";
    case "MODERATE": return "Rủi ro trung bình";
    case "HIGH": return "Rủi ro cao";
    case "INSUFFICIENT_INFORMATION": return "Chưa đủ thông tin";
    default: return null;
  }
}

export function AnalysisHistory({
  items,
  loading,
  error,
  onOpen,
  onNewAnalysis,
}: {
  items: AnalysisHistoryItem[];
  loading: boolean;
  error: string;
  onOpen: (item: AnalysisHistoryItem) => void;
  onNewAnalysis: () => void;
}) {
  const [query, setQuery] = useState("");
  const normalized = query.trim().toLocaleLowerCase("vi");
  const visible = useMemo(
    () => items.filter(item => {
      if (!normalized) return true;
      return [
        item.supplier_name,
        item.platform,
        item.source_url,
        statusLabel(item.status),
      ].some(value => value?.toLocaleLowerCase("vi").includes(normalized));
    }),
    [items, normalized],
  );

  return <main className="dashboard history-dashboard" id="history">
    <section className="dashboard-intro">
      <div>
        <span className="pill pill-good">TÀI KHOẢN CỦA BẠN</span>
        <h1>Lịch sử phân tích</h1>
        <p>Các phân tích được lưu trên VCT Connect và chỉ hiển thị cho tài khoản đã tạo chúng.</p>
      </div>
      <button type="button" className="button button-primary" onClick={onNewAnalysis}>+ Phân tích mới</button>
    </section>

    <section className="history-panel server-history-panel" aria-label="Lịch sử phân tích của bạn">
      <div className="history-search">
        <span>⌕</span>
        <input value={query} onChange={event => setQuery(event.target.value)}
          placeholder="Tìm nhà cung cấp, nền tảng hoặc URL" aria-label="Tìm trong lịch sử" />
      </div>
      <div className="history-panel-title">
        <strong>{visible.length} kết quả</strong>
        <span>Mới nhất trước</span>
      </div>

      {loading && <div className="history-empty" aria-live="polite"><span>◌</span><strong>Đang tải lịch sử…</strong></div>}
      {!loading && error && <div className="history-empty" role="alert"><span>!</span><strong>Không thể tải lịch sử</strong><p>{error}</p></div>}
      {!loading && !error && !visible.length && <div className="history-empty"><span>◎</span><strong>Chưa có phân tích</strong><p>Phân tích đầu tiên của bạn sẽ xuất hiện tại đây.</p></div>}

      {!loading && !error && visible.length > 0 && <div className="history-list server-history-list">
        {visible.map(item => {
          const risk = riskLabel(item.risk_label);
          const action = item.report_available ? "Mở báo cáo" : item.status === "COMPLETED" ? "Xem kết quả" : "Xem tiến độ";
          return <article className="history-entry server-history-entry" key={item.id}>
            <div className="history-entry-top">
              <span><b>{item.platform ?? "Nguồn chưa xác định"}</b><small>{statusLabel(item.status)}</small></span>
              <time>{date(item.created_at)}</time>
            </div>
            <strong>{item.supplier_name ?? "Nhà cung cấp chưa xác định"}</strong>
            <code className="history-source-url">{item.source_url}</code>
            <div className="history-entry-meta">
              <span>{risk ?? "Chưa có đánh giá rủi ro"}</span>
              {item.confidence !== null && <span>{Math.round(item.confidence * 100)}% tin cậy</span>}
              {item.coverage !== null && <span>{Math.round(item.coverage * 100)}% độ phủ</span>}
            </div>
            <button type="button" className="button button-ghost history-open-button" onClick={() => onOpen(item)}>
              {action} →
            </button>
          </article>;
        })}
      </div>}
    </section>
  </main>;
}
