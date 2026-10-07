import type { ReportEvidence, ReportFinding, ReportV1 } from "@vct/contracts";
import { safeSourceUrl } from "./source-url";

const DIMENSIONS: Record<string, string> = {
  PRODUCT_QUALITY: "Chất lượng sản phẩm",
  DELIVERY: "Giao hàng",
  AFTER_SALES: "Hậu mãi",
  REVIEW_MANIPULATION: "Độ tin cậy đánh giá",
  SUPPLIER_IDENTITY: "Danh tính nhà cung cấp",
  BUSINESS_STABILITY: "Ổn định hoạt động",
  TRANSACTION: "Giao dịch",
};

const SOURCE_KINDS: Record<string, string> = {
  SUPPLIER_DATA: "Dữ liệu nhà cung cấp",
  REVIEW: "Đánh giá người mua",
  REVIEW_MEDIA: "Ảnh / video đánh giá",
  PLATFORM_PROFILE: "Hồ sơ nền tảng",
  DERIVED: "Tín hiệu suy luận xác định",
  MODEL_INTERPRETATION: "Diễn giải có cấu trúc",
};

function percent(value: unknown) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "Chưa xác định";
}

function barWidth(value: unknown) {
  return typeof value === "number" ? `${Math.max(0, Math.min(100, Math.round(value * 100)))}%` : "0%";
}

function scorePercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function freshness(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Thời điểm thu thập chưa xác định";
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function riskLabel(report: ReportV1) {
  switch (report.risk.label) {
    case "LOW": return { text: "RỦI RO THẤP", tone: "good" as const };
    case "MODERATE": return { text: "RỦI RO TRUNG BÌNH", tone: "warning" as const };
    case "HIGH": return { text: "RỦI RO CAO", tone: "danger" as const };
    default: return { text: "CHƯA ĐỦ THÔNG TIN", tone: "neutral" as const };
  }
}

function evidenceAnchor(id: string) {
  return `evidence-${id.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

function payloadText(payload: Record<string, unknown>) {
  for (const key of ["statement_vi", "statement", "title", "kind"]) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return null;
}

function findingTitle(finding: ReportFinding) {
  return payloadText(finding.payload)
    ?? DIMENSIONS[finding.dimension ?? ""]
    ?? finding.finding_type.replaceAll("_", " ");
}

function FindingCard({ finding }: { finding: ReportFinding }) {
  const statement = payloadText(finding.payload);
  return <article className="report-finding">
    <div className="report-finding-head">
      <span>{DIMENSIONS[finding.dimension ?? ""] ?? finding.finding_type.replaceAll("_", " ")}</span>
      {finding.confidence !== null && <small>{scorePercent(finding.confidence)} tin cậy</small>}
    </div>
    <h4>{findingTitle(finding)}</h4>
    {statement && statement !== findingTitle(finding) ? <p>{statement}</p> : null}
    {finding.evidence_ids.length > 0 && <div className="finding-evidence">
      <span>Bằng chứng</span>
      {finding.evidence_ids.map(id =>
        <a key={id} href={`#${evidenceAnchor(id)}`}>{id}</a>
      )}
    </div>}
  </article>;
}

function EvidenceCard({ evidence, extractedAt }: { evidence: ReportEvidence; extractedAt: string }) {
  const text = payloadText(evidence.payload);
  return <article className="report-source" id={evidenceAnchor(evidence.evidence_id)}>
    <div className="report-source-head">
      <code>{evidence.evidence_id}</code>
      <span>{SOURCE_KINDS[evidence.source_kind] ?? evidence.source_kind}</span>
    </div>
    {evidence.source_field && <p><strong>Trường nguồn:</strong> {evidence.source_field}</p>}
    {text && <p>{text}</p>}
    <small>Độ mới: bằng chứng thuộc ảnh chụp ngày {freshness(extractedAt)}</small>
  </article>;
}

function MissingList({ title, values }: { title: string; values: string[] }) {
  if (!values.length) return null;
  return <div className="report-missing-group">
    <strong>{title}</strong>
    <ul>{values.map(value => <li key={value}>{DIMENSIONS[value] ?? value}</li>)}</ul>
  </div>;
}

export function FullReport({ report }: { report: ReportV1 }) {
  const label = riskLabel(report);
  const source = safeSourceUrl(report.source_url);
  const factory = report.factory_trader;
  const review = report.review_summary;
  const overall = report.risk.overall_risk;
  const reviewReliability = typeof review.review_reliability === "number"
    ? review.review_reliability
    : typeof review.reliability === "number" ? review.reliability : null;
  const reviewCount = typeof review.review_count === "number"
    ? review.review_count
    : Array.isArray(review.findings) ? review.findings.length : null;

  return <section className="full-report" aria-label="Báo cáo đánh giá nhà cung cấp">
    <header className="full-report-header">
      <div>
        <div className="report-title-row">
          <span className="platform-chip">{report.platform}</span>
          <span className={`report-risk-pill ${label.tone}`}>{label.text}</span>
        </div>
        <h2>{report.supplier_name ?? "Nhà cung cấp chưa xác định"}</h2>
        <p>{report.supplier_summary_vi}</p>
      </div>
      <div className="report-ref">
        <small>MÃ PHÂN TÍCH</small>
        <code>{report.analysis_id.slice(0, 8).toUpperCase()}</code>
        <small>Thu thập {freshness(report.extracted_at)}</small>
      </div>
    </header>

    <div className={`report-decision ${report.risk.label === "INSUFFICIENT_INFORMATION" ? "insufficient" : ""}`}>
      <article>
        <span className="card-label">RỦI RO TỔNG THỂ</span>
        <div className="real-risk-score">
          {overall === null ? <strong>—</strong> : <strong>{Math.round(overall)}</strong>}
          <small>{overall === null ? "chưa đủ dữ liệu" : "/100"}</small>
        </div>
        <span className={`report-risk-pill ${label.tone}`}>{label.text}</span>
        {report.risk.label === "INSUFFICIENT_INFORMATION" &&
          <p>Không có điểm rủi ro thấp mặc định khi bằng chứng chưa đủ.</p>}
      </article>
      <article>
        <span className="card-label">ĐỘ TIN CẬY</span>
        <strong className="metric-value">{scorePercent(report.risk.confidence)}</strong>
        <div className="report-meter"><i style={{ width: scorePercent(report.risk.confidence) }} /></div>
        <p>Mức tin cậy của kết quả dựa trên chất lượng và độ đầy đủ của bằng chứng.</p>
      </article>
      <article>
        <span className="card-label">ĐỘ PHỦ DỮ LIỆU</span>
        <strong className="metric-value">{scorePercent(report.risk.coverage)}</strong>
        <div className="report-meter"><i style={{ width: scorePercent(report.risk.coverage) }} /></div>
        <p>Phiên bản chấm điểm: <code>{report.risk.scoring_version}</code></p>
      </article>
    </div>

    <div className="report-grid">
      <article className="identity-card">
        <div className="section-heading">
          <div><span className="card-label">NHÀ MÁY / THƯƠNG MẠI</span><h3>Nhận định loại hình</h3></div>
          <span>{typeof factory.classification === "string" ? factory.classification : "UNCERTAIN"}</span>
        </div>
        <div className="identity-bars">
          <div><span><b>Khả năng nhà máy</b><small>{percent(factory.factory_likelihood)}</small></span><i><b style={{ width: barWidth(factory.factory_likelihood) }} /></i></div>
          <div><span><b>Khả năng thương mại</b><small>{percent(factory.trader_likelihood)}</small></span><i className="dark"><b style={{ width: barWidth(factory.trader_likelihood) }} /></i></div>
        </div>
        <p className="identity-note">Độ tin cậy nhận định: {percent(factory.confidence)}. Đây là tổng hợp bằng chứng, không phải xác minh pháp lý độc lập.</p>
      </article>

      <article className="report-summary-card">
        <div className="section-heading">
          <div><span className="card-label">ĐÁNH GIÁ NGƯỜI MUA</span><h3>Tóm tắt đánh giá</h3></div>
          <span>{review.mode === "semantic" ? "Ngữ nghĩa" : "Xác định"}</span>
        </div>
        <dl className="report-summary-stats">
          <div><dt>Độ tin cậy đánh giá</dt><dd>{reviewReliability === null ? "Chưa xác định" : scorePercent(reviewReliability)}</dd></div>
          <div><dt>Mẫu / phát hiện</dt><dd>{reviewCount ?? "Chưa xác định"}</dd></div>
        </dl>
        {Array.isArray(review.missing_inputs) && review.missing_inputs.length > 0 &&
          <p className="identity-note">Thiếu đầu vào đánh giá: {review.missing_inputs.join(", ")}</p>}
      </article>
    </div>

    <div className="report-grid lower">
      <article className="signals-card">
        <div className="section-heading">
          <div><span className="card-label">RỦI RO CẦN XÁC MINH</span><h3>Phát hiện chính</h3></div>
          <span>{report.key_risks.length} phát hiện</span>
        </div>
        <div className="report-finding-list">
          {report.key_risks.length
            ? report.key_risks.map(finding => <FindingCard finding={finding} key={finding.finding_key} />)
            : <p className="report-empty-copy">Không có phát hiện rủi ro có căn cứ trong dữ liệu hiện tại. Điều này không đồng nghĩa với rủi ro bằng 0.</p>}
        </div>
      </article>
      <article className="signals-card positive-card">
        <div className="section-heading">
          <div><span className="card-label">TÍN HIỆU TÍCH CỰC</span><h3>Bằng chứng hỗ trợ</h3></div>
          <span>{report.positive_signals.length} tín hiệu</span>
        </div>
        <div className="report-finding-list">
          {report.positive_signals.length
            ? report.positive_signals.map(finding => <FindingCard finding={finding} key={finding.finding_key} />)
            : <p className="report-empty-copy">Chưa có tín hiệu tích cực đủ căn cứ để hiển thị.</p>}
        </div>
      </article>
    </div>

    <article className="actions-card report-actions">
      <div className="card-label">HÀNH ĐỘNG ĐỀ XUẤT</div>
      <h3>Trước khi đặt hàng</h3>
      <ol>{report.recommended_actions_vi.map((action, index) =>
        <li key={action}><span>{index + 1}</span><p><strong>{action}</strong></p></li>
      )}</ol>
    </article>

    <section className="report-unknowns" aria-label="Thông tin còn thiếu và giới hạn">
      <div>
        <span className="card-label">THÔNG TIN CÒN THIẾU</span>
        <MissingList title="Trường nguồn chưa có" values={report.missing_data.source_fields} />
        <MissingList title="Chiều rủi ro chưa đủ bằng chứng" values={report.missing_data.risk_dimensions} />
        <MissingList title="Điểm chưa chắc chắn" values={report.missing_data.uncertainties_vi} />
        {!report.missing_data.source_fields.length && !report.missing_data.risk_dimensions.length && !report.missing_data.uncertainties_vi.length &&
          <p>Không có mục thiếu được ghi nhận trong payload báo cáo.</p>}
      </div>
      <div>
        <span className="card-label">GIỚI HẠN</span>
        <ul>{report.limitations_vi.map(item => <li key={item}>{item}</li>)}</ul>
      </div>
    </section>

    <section className="report-sources" aria-label="Nguồn và bằng chứng">
      <div className="section-heading">
        <div><span className="card-label">NGUỒN VÀ BẰNG CHỨNG</span><h3>Truy vết phát hiện</h3></div>
        <span>{report.evidence.length} mục</span>
      </div>
      <p className="report-source-freshness">Ảnh chụp dữ liệu dùng cho báo cáo: {freshness(report.extracted_at)}.</p>
      <div className="report-source-list">
        {report.evidence.map(item => <EvidenceCard evidence={item} extractedAt={report.extracted_at} key={item.evidence_id} />)}
      </div>
      {source && <a className="report-origin-link" href={source} target="_blank" rel="noreferrer">Mở trang nguồn {report.platform} ↗</a>}
    </section>
  </section>;
}
