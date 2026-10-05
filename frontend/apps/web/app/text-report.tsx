import React from "react";
import type { Analysis } from "@vct/contracts";
import { isFixtureResult } from "./extraction-evidence";

const LABELS = {
  QUEUED: "Báo cáo đang chờ xử lý",
  PROCESSING: "Đang diễn giải bằng chứng sang tiếng Việt",
  READY: "Báo cáo tiếng Việt đã sẵn sàng",
  UNAVAILABLE: "Chưa thể tạo báo cáo",
  INSUFFICIENT: "Chưa đủ bằng chứng văn bản để tạo báo cáo",
  FAILED: "Báo cáo không vượt qua kiểm tra",
  UNCERTAIN: "Lần tạo báo cáo cần được đối soát",
};

export function TextReport({ analysis }: { analysis: Analysis }) {
  if (isFixtureResult(analysis.result) || analysis.actor_type === "GUEST") return null;
  const state = analysis.text_report;
  const report = state?.state === "READY" ? state.report : null;
  return <section className="text-report progress-card" aria-label="Báo cáo tiếng Việt" aria-live="polite">
    <h2>{state ? LABELS[state.state] : "Chưa có báo cáo tiếng Việt"}</h2>
    {!report && <>
      <p>Bằng chứng trích xuất vẫn có thể xem bên dưới. Trạng thái báo cáo độc lập với trạng thái trích xuất.</p>
      {state?.failure_code && <p>Mã trạng thái: <code>{state.failure_code}</code></p>}
      {state?.state === "UNCERTAIN" && <p>Hệ thống không tự gửi lại yêu cầu có thể đã phát sinh chi phí.</p>}
    </>}
    {report && <>
      <p>{report.summary}</p>
      <p>Không có điểm rủi ro hoặc độ tin cậy được tính toán. Độ mới của nguồn: chưa xác định.</p>
      <dl><dt>Trích xuất</dt><dd>{report.extracted_at}</dd>
        <dt>Tạo báo cáo</dt><dd>{state?.generated_at}</dd></dl>
      <h3>Nhận định và nguồn</h3>
      {report.findings.map((finding, index) => <article key={index} className="text-finding">
        <strong>{finding.kind === "observation" ? "Quan sát từ nguồn" : "Suy luận cần xác minh"}</strong>
        <p>{finding.text}</p>
        {finding.citations.map(id => <a key={id} className="text-citation" href={`#report-${analysis.id}-${id}`}>{id}</a>)}
      </article>)}
      <h3>Giới hạn</h3><ul>{report.limitations.map((text, index) => <li key={index}>{text}</li>)}</ul>
      <h3>Trước khi đặt hàng</h3><ol>{report.actions.map((text, index) => <li key={index}>{text}</li>)}</ol>
      <h3>Bằng chứng được dẫn</h3>
      <p>Văn bản nguồn đã được giới hạn và ẩn thông tin liên hệ; xem bản trích xuất bên dưới để kiểm tra đầy đủ.</p>
      {report.evidence.map(entry => <details key={entry.id} id={`report-${analysis.id}-${entry.id}`}>
        <summary>{entry.id} · {entry.path}</summary>
        <pre>{typeof entry.value === "string" ? entry.value : JSON.stringify(entry.value, null, 2)}</pre>
      </details>)}
      <details><summary>Thông tin tạo báo cáo</summary>
        <p>Nguồn: {report.source_url} · Ảnh chụp: {report.snapshot_id}</p>
        {report.source_provenance && <pre>{JSON.stringify(report.source_provenance, null, 2)}</pre>}
        <p>Mô hình: {report.metadata.model} · {report.metadata.model_version}</p>
        <p>Phiên bản: {report.metadata.prompt_version} · {report.metadata.schema_version} · {report.metadata.pipeline_version}</p>
        <p>Chi phí thực tế: chưa xác định.</p>
      </details>
    </>}
  </section>;
}
