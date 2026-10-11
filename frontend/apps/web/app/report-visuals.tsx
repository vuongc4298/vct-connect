import React, { useState } from "react";

export const REPORT_PAGE_SIZE = 5;

export function ReportPages<T>({ items, label, children }: {
  items: T[]; label: string; children: (items: T[], offset: number) => React.ReactNode;
}) {
  const [page, setPage] = useState(0);
  const pages = Math.ceil(items.length / REPORT_PAGE_SIZE);
  const current = Math.min(page, Math.max(0, pages - 1));
  const offset = current * REPORT_PAGE_SIZE;
  return <div className="report-pages">
    {children(items.slice(offset, offset + REPORT_PAGE_SIZE), offset)}
    {pages > 1 && <nav className="report-pagination" aria-label={label}>
      <span>{offset + 1}–{Math.min(offset + REPORT_PAGE_SIZE, items.length)} / {items.length}</span>
      <div><button type="button" disabled={current === 0} aria-label={`${label}: trước`} onClick={() => setPage(current - 1)}>←</button>
        <button type="button" disabled={current === pages - 1} aria-label={`${label}: tiếp`} onClick={() => setPage(current + 1)}>→</button></div>
    </nav>}
  </div>;
}

export function MetricRing({ value, label, suffix = "%", tone = "green" }: {
  value: number | null; label: string; suffix?: string; tone?: string;
}) {
  const known = value !== null && Number.isFinite(value);
  const bounded = known ? Math.max(0, Math.min(100, value!)) : null;
  const text = bounded === null ? "—" : `${Math.round(bounded)}${suffix}`;
  const circumference = 2 * Math.PI * 46;
  return <figure className={`metric-ring ${tone} ${known ? "" : "unknown"}`} aria-label={`${label}: ${known ? text : "chưa đủ dữ liệu"}`}>
    <svg viewBox="0 0 112 112" aria-hidden="true">
      <circle className="ring-track" cx="56" cy="56" r="46" />
      {bounded !== null && <circle className="ring-value" cx="56" cy="56" r="46" strokeDasharray={circumference}
        strokeDashoffset={circumference * (1 - bounded / 100)} transform="rotate(-90 56 56)" />}
    </svg>
    <figcaption><strong>{text}</strong>{!known && <small>chưa đủ dữ liệu</small>}</figcaption>
  </figure>;
}

export function RiskBar({ value, label }: { value: number | null; label: string }) {
  const known = value !== null && Number.isFinite(value);
  return <div className={`risk-chart-track ${known ? "" : "unknown"}`} role="img"
    aria-label={`${label}: ${known ? `${Math.round(value!)} trên 100` : "chưa đủ bằng chứng"}`}>
    {known && <span style={{ width: `${Math.max(0, Math.min(100, value!))}%` }} />}
  </div>;
}
