import React from "react";
import type { AccountState } from "@vct/contracts";

function dateTime(value: string | null) {
  if (!value) return "Chưa có";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Chưa xác định";
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function AccountStateView({ state }: { state: AccountState }) {
  const trial = state.trial.active;
  const usagePercent = state.usage.limit > 0
    ? Math.min(100, Math.round((state.usage.used / state.usage.limit) * 100))
    : 0;
  return <main className="dashboard account-dashboard" id="account">
    <section className="dashboard-intro">
      <div>
        <span className="pill pill-good">TÀI KHOẢN</span>
        <h1>Hồ sơ & quyền sử dụng</h1>
        <p>Trạng thái này được đọc trực tiếp từ tài khoản và quyền sử dụng đã lưu trên VCT Connect.</p>
      </div>
    </section>

    <div className="account-grid">
      <article className="account-card">
        <span className="card-label">HỒ SƠ</span>
        <h2>{state.user.email ?? "Tài khoản Clerk đã xác thực"}</h2>
        <dl>
          <div><dt>Vai trò</dt><dd>{state.user.role}</dd></div>
          <div><dt>Gói hiện tại</dt><dd>{trial ? "MVP Trial" : "Free"}</dd></div>
        </dl>
      </article>

      <article className="account-card">
        <span className="card-label">MVP TRIAL</span>
        <h2>{trial ? "Đang hoạt động" : "Chưa hoạt động"}</h2>
        <dl>
          <div><dt>Bắt đầu</dt><dd>{dateTime(state.trial.starts_at)}</dd></div>
          <div><dt>Hết hạn</dt><dd>{dateTime(state.trial.expires_at)}</dd></div>
          <div><dt>Trạng thái bản ghi</dt><dd>{state.trial.status ?? "Không có entitlement"}</dd></div>
        </dl>
        <p className="account-safety-note">MVP hiện không tự động thu phí và không tự động gia hạn khi trial kết thúc.</p>
      </article>

      <article className="account-card account-usage-card">
        <span className="card-label">LƯỢT PHÂN TÍCH</span>
        <div className="account-usage-value"><strong>{state.usage.used}</strong><span>/ {state.usage.limit}</span></div>
        <div className="report-meter"><i style={{ width: `${usagePercent}%` }} /></div>
        <p>Còn {state.usage.remaining} lượt trong cửa sổ sử dụng hiện tại.</p>
        <small>Làm mới lúc {dateTime(state.usage.resets_at)}</small>
      </article>
    </div>
  </main>;
}
