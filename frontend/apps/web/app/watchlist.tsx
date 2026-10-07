import React from "react";
import type { WatchlistEntry } from "@vct/contracts";

function pct(value: number | null) {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}

export function WatchlistView({
  entries,
  loading,
  error,
  removingId,
  onOpen,
  onRemove,
}: {
  entries: WatchlistEntry[];
  loading: boolean;
  error: string;
  removingId: string | null;
  onOpen: (entry: WatchlistEntry) => void;
  onRemove: (entry: WatchlistEntry) => void;
}) {
  return <main className="dashboard watchlist-dashboard" id="watchlist">
    <section className="dashboard-intro">
      <div>
        <span className="pill pill-good">DANH SÁCH THEO DÕI</span>
        <h1>Watchlist nhà cung cấp</h1>
        <p>Các nhà cung cấp bạn đã lưu từ báo cáo. Mỗi nhà cung cấp chỉ xuất hiện một lần trong tài khoản.</p>
      </div>
    </section>

    {loading && <section className="history-empty"><span>◌</span><strong>Đang tải Watchlist…</strong></section>}
    {!loading && error && <section className="history-empty" role="alert"><span>!</span><strong>Không thể tải Watchlist</strong><p>{error}</p></section>}
    {!loading && !error && entries.length === 0 && <section className="history-empty"><span>☆</span><strong>Watchlist đang trống</strong><p>Mở một báo cáo và chọn “Lưu vào Watchlist”.</p></section>}

    {!loading && !error && entries.length > 0 && <section className="watchlist-grid" aria-label="Watchlist của bạn">
      {entries.map(entry => <article className="watchlist-card" key={entry.id}>
        <div className="watchlist-card-head">
          <span className="platform-chip">{entry.platform}</span>
          <button type="button" className="button button-ghost" disabled={removingId === entry.id} onClick={() => onRemove(entry)}>
            {removingId === entry.id ? "Đang xoá…" : "Xoá"}
          </button>
        </div>
        <h2>{entry.name ?? "Nhà cung cấp chưa xác định"}</h2>
        <code>{entry.platform_supplier_id ?? "Không có mã nhà cung cấp"}</code>
        <p className="watchlist-source">{entry.source_url}</p>
        <div className="watchlist-metrics">
          <span><small>Rủi ro</small><strong>{entry.overall_risk === null ? "—" : Math.round(entry.overall_risk)}</strong></span>
          <span><small>Tin cậy</small><strong>{pct(entry.confidence)}</strong></span>
          <span><small>Độ phủ</small><strong>{pct(entry.coverage)}</strong></span>
        </div>
        <button type="button" className="button button-primary" disabled={!entry.analysis_id} onClick={() => onOpen(entry)}>
          {entry.report_available ? "Mở báo cáo" : "Mở phân tích"} →
        </button>
      </article>)}
    </section>}
  </main>;
}
