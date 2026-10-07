export const REPORT_STALE_AFTER_DAYS = 30;
const DAY_MS = 24 * 60 * 60 * 1000;

export type ReportFreshness = {
  label: string;
  stale: boolean;
  ageDays: number | null;
  invalid: boolean;
};

export function reportFreshness(value: string, now = Date.now()): ReportFreshness {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) {
    return {
      label: "Thời điểm thu thập chưa xác định",
      stale: false,
      ageDays: null,
      invalid: true,
    };
  }
  const ageDays = Math.max(0, Math.floor((now - date.valueOf()) / DAY_MS));
  return {
    label: new Intl.DateTimeFormat("vi-VN", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date),
    stale: ageDays >= REPORT_STALE_AFTER_DAYS,
    ageDays,
    invalid: false,
  };
}
