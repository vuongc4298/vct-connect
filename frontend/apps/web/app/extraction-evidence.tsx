import React from "react";
import type { Analysis, FixtureResult } from "@vct/contracts";

export function isFixtureResult(result: Analysis["result"]): result is FixtureResult {
  return result !== null && "fixture" in result && result.fixture === true;
}

export function ExtractionEvidence({ analysis }: { analysis: Analysis }) {
  const data = analysis.supplier_data;
  const result = analysis.result;
  if (!result || isFixtureResult(result)) return null;
  return <section className="progress-card" aria-label="Bằng chứng trích xuất 1688">
    <h2>Bằng chứng 1688</h2>
    <p>Trạng thái trích xuất: <strong>{result.extraction_status}</strong>{result.reason ? ` · ${result.reason}` : ""}</p>
    {data ? <>
      <p><strong>{data.supplier_name ?? "Chưa có tên nhà cung cấp"}</strong> · {data.products?.[0]?.title ?? "Chưa có tên sản phẩm"}</p>
      <p>Độ phủ: {Math.round(data.completeness * 100)}% ({data.completeness_denominator.length - data.missing_fields.length}/{data.completeness_denominator.length} trường) · Thiếu: {data.missing_fields.length ? data.missing_fields.join(", ") : "không"}</p>
      <p>Nguồn: {data.platform} · {data.extraction_method} · {data.analysis_mode} · {data.extractor_version} · {new Date(data.extracted_at).toLocaleString("vi-VN")}</p>
      <p>Đánh giá hiển thị: {data.transaction_signals?.review_count ?? "chưa có"} · Nội dung đánh giá truy cập được: {analysis.reviews.length}</p>
      {analysis.reviews.length > 0 && <ul>{analysis.reviews.map((review, index) => <li key={index}>{String(review.text ?? "")}</li>)}</ul>}
      <p>Thiếu dữ liệu là chưa xác định, không phải tín hiệu an toàn. Chưa có điểm rủi ro cho dữ liệu này.</p>
      <a href={data.source_url} target="_blank" rel="noreferrer">Mở trang nguồn 1688</a>
    </> : <p>Không có ảnh chụp bằng chứng công khai. Chưa có điểm rủi ro.</p>}
  </section>;
}
