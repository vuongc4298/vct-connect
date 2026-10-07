import React from "react";
import type { GuestPreviewV1 } from "@vct/contracts";

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function GuestPreview({ preview }: { preview: GuestPreviewV1 }) {
  const insufficient = preview.information_state === "INSUFFICIENT_INFORMATION";
  const missing = preview.missing_source_fields.length + preview.missing_risk_dimensions.length;

  return <section className="guest-preview-card" aria-label="Bản xem trước đánh giá dành cho khách">
    <div className="guest-preview-head">
      <div>
        <span className="card-label">BẢN XEM TRƯỚC DÀNH CHO KHÁCH</span>
        <h2>{preview.supplier_name ?? "Nhà cung cấp chưa xác định"}</h2>
        <p>{preview.platform} · Chỉ hiển thị độ phủ, độ tin cậy và giới hạn dữ liệu.</p>
      </div>
      <span className={`guest-preview-state ${insufficient ? "insufficient" : ""}`}>
        {insufficient ? "CHƯA ĐỦ THÔNG TIN" : "BẢN XEM TRƯỚC GIỚI HẠN"}
      </span>
    </div>

    <div className="guest-preview-metrics">
      <article>
        <span>Độ tin cậy</span>
        <strong>{pct(preview.confidence)}</strong>
        <i><b style={{ width: pct(preview.confidence) }} /></i>
      </article>
      <article>
        <span>Độ phủ dữ liệu</span>
        <strong>{pct(preview.coverage)}</strong>
        <i><b style={{ width: pct(preview.coverage) }} /></i>
      </article>
    </div>

    <div className="guest-preview-warning">
      <strong>{insufficient ? "Không có kết luận rủi ro thấp khi dữ liệu chưa đủ." : "Điểm rủi ro và phát hiện chi tiết không được công khai trong bản xem trước."}</strong>
      <p>{missing > 0 ? `Còn ${missing} hạng mục dữ liệu / chiều rủi ro chưa đủ bằng chứng.` : "Bản xem trước vẫn không thay thế báo cáo đầy đủ và xác minh độc lập."}</p>
    </div>

    {(preview.missing_source_fields.length > 0 || preview.missing_risk_dimensions.length > 0) &&
      <div className="guest-preview-missing">
        {preview.missing_source_fields.length > 0 && <div><strong>Trường nguồn còn thiếu</strong><p>{preview.missing_source_fields.join(", ")}</p></div>}
        {preview.missing_risk_dimensions.length > 0 && <div><strong>Chiều rủi ro chưa đủ bằng chứng</strong><p>{preview.missing_risk_dimensions.join(", ")}</p></div>}
      </div>}

    {preview.limitations_vi.length > 0 &&
      <div className="guest-preview-limit"><strong>Giới hạn</strong><p>{preview.limitations_vi[0]}</p></div>}
  </section>;
}
