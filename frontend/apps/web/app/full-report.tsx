import React, { useEffect } from "react";
import { MetricRing, ReportPages, RiskBar } from "./report-visuals";
import type { ReportEvidence, ReportFinding, ReportV1 } from "@vct/contracts";
import { safeSourceUrl } from "./source-url";
import { reportFreshness } from "./report-freshness";
import {
  REPORT_DIMENSION_LABELS,
  REPORT_FIELD_LABELS,
  REPORT_SOURCE_KIND_LABELS,
  optionalReportPercent,
  reportBarWidth,
  reportEvidenceAnchor,
  reportFindingTitle,
  reportPayloadText,
  reportPercent,
  reportRiskLabel,
  reportSourceContent,
} from "./report-presentation";

function FindingCard({ finding, availableEvidenceIds }: { finding: ReportFinding; availableEvidenceIds: Set<string> }) {
  const statement = reportPayloadText(finding.payload);
  return <article className="report-finding">
    <div className="report-finding-head">
      <span>{REPORT_DIMENSION_LABELS[finding.dimension ?? ""] ?? finding.finding_type.replaceAll("_", " ")}</span>
      {finding.confidence !== null && <small>{reportPercent(finding.confidence)} tin cậy</small>}
    </div>
    <h4>{reportFindingTitle(finding)}</h4>
    {statement && statement !== reportFindingTitle(finding) ? <p>{statement}</p> : null}
    {finding.evidence_ids.length > 0 && <div className="finding-evidence">
      <span>Bằng chứng</span>
      {finding.evidence_ids.map(id =>
        availableEvidenceIds.has(id)
          ? <a key={id} href={`#${reportEvidenceAnchor(id)}`}>{id}</a>
          : <span className="missing-evidence-ref" key={id}>{id} · thiếu nguồn</span>
      )}
    </div>}
  </article>;
}

function EvidenceCard({ evidence, extractedAt, uploaded }: { evidence: ReportEvidence; extractedAt: string; uploaded: boolean }) {
  const text = reportPayloadText(evidence.payload);
  const content = reportSourceContent(evidence.payload);
  const hasSourceContent = evidence.source_kind === "REVIEW" || evidence.source_kind === "SUPPLIER_DATA";
  const freshness = reportFreshness(extractedAt);
  const reviewSource = safeSourceUrl(typeof evidence.payload.source_url === "string" ? evidence.payload.source_url : undefined);
  return <article className="report-source" id={reportEvidenceAnchor(evidence.evidence_id)}>
    <details>
    <summary className="report-source-head">
      <strong>{REPORT_FIELD_LABELS[evidence.source_field ?? ""] ?? evidence.source_field ?? evidence.evidence_id}</strong>
      <span>{REPORT_SOURCE_KIND_LABELS[evidence.source_kind] ?? evidence.source_kind}</span>
    </summary>
    <code className="source-reference">{evidence.evidence_id}</code>
    {evidence.source_field && <p><strong>Trường nguồn:</strong> {evidence.source_field}</p>}
    {hasSourceContent && <div><strong>Nội dung nguồn:</strong><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{content ?? "Chưa xác định"}</pre></div>}
    {text && <p><strong>Diễn giải / ghi chú:</strong> {text}</p>}
    {reviewSource && <a href={reviewSource} target="_blank" rel="noreferrer">Mở nguồn đánh giá ↗</a>}
    <small>{uploaded ? "Thời điểm xử lý HTML: " : "Độ mới: "}{!uploaded && freshness.stale ? "DỮ LIỆU CŨ · " : ""}{freshness.label}{uploaded ? " · Tuổi ảnh chụp trang: Chưa xác định" : ""}</small>
    </details>
  </article>;
}

function MissingList({ title, values, tags = false }: { title: string; values: string[]; tags?: boolean }) {
  if (!values.length) return null;
  return <div className="report-missing-group">
    <strong>{title}</strong>
    {tags ? <div className="report-missing-tags">{values.map(value => <span key={value}>{REPORT_DIMENSION_LABELS[value] ?? REPORT_FIELD_LABELS[value] ?? value}</span>)}</div>
      : <ReportPages items={values} label={title}>{items => <ul>{items.map(value => <li key={value}>{value}</li>)}</ul>}</ReportPages>}
  </div>;
}

export function FullReport({ report, extractionMethod }: { report: ReportV1; extractionMethod?: string }) {
  const uploaded = extractionMethod === "USER_UPLOAD";
  const label = reportRiskLabel(report.risk.label);
  const source = safeSourceUrl(report.source_url);
  const factory = report.factory_trader;
  const review = report.review_summary;
  const overall = report.risk.label === "INSUFFICIENT_INFORMATION" ? null : report.risk.overall_risk;
  const sourceFreshness = reportFreshness(report.extracted_at);
  const availableEvidenceIds = new Set(report.evidence.map(item => item.evidence_id));
  const reviewReliability = typeof review.review_reliability === "number"
    ? review.review_reliability
    : typeof review.reliability === "number" ? review.reliability : null;
  const reviewCount = typeof review.review_count === "number"
    ? review.review_count
    : Array.isArray(review.findings) ? review.findings.length : null;

  useEffect(() => {
    const revealSource = () => {
      const id = window.location.hash.slice(1);
      if (!id.startsWith("evidence-")) return;
      const target = document.getElementById(id);
      const details = target?.querySelector("details");
      if (details) details.open = true;
    };
    revealSource();
    window.addEventListener("hashchange", revealSource);
    return () => window.removeEventListener("hashchange", revealSource);
  }, [report.analysis_id]);

  return <section className="full-report" aria-label="Báo cáo đánh giá nhà cung cấp" onClick={event => {
    const anchor = (event.target as HTMLElement).closest("a");
    const href = anchor?.getAttribute("href");
    if (!href?.startsWith("#evidence-")) return;
    const details = document.getElementById(href.slice(1))?.querySelector("details");
    if (details) details.open = true;
  }}>
    <header className="full-report-header" id="report-overview">
      <div>
        <div className="report-title-row">
          <span className="platform-chip">{report.platform}</span>
          <span className={`report-risk-pill ${label.tone}`}>{label.text}</span>
        </div>
        <h2>{report.supplier_name ?? "Nhà cung cấp chưa xác định"}</h2>
        <p className="report-intro">{report.supplier_summary_vi}</p>
      </div>
      <div className="report-ref">
        <small>MÃ PHÂN TÍCH</small>
        <code>{report.analysis_id.slice(0, 8).toUpperCase()}</code>
        <small>{uploaded ? "Xử lý HTML" : "Thu thập"} {sourceFreshness.label}</small>
      </div>
    </header>

    <nav className="report-section-nav" aria-label="Điều hướng báo cáo"><a href="#report-overview">Tổng quan</a><a href="#report-risk-dimensions">Biểu đồ rủi ro</a><a href="#report-next-actions">Việc cần làm</a><a href="#report-source-evidence">Bằng chứng</a></nav>

    {uploaded && <div className="report-stale-warning" role="status"><strong>Tuổi ảnh chụp trang đã lưu chưa xác định</strong><p>Thời điểm xử lý HTML là lúc nhập trang, không xác nhận thời điểm trang được lưu. Hãy xác minh lại dữ liệu nguồn trước khi đặt hàng.</p></div>}
    {!uploaded && sourceFreshness.stale && <div className="report-stale-warning" role="status">
      <strong>Dữ liệu nguồn đã cũ</strong>
      <p>Ảnh chụp bằng chứng đã hơn 30 ngày{sourceFreshness.ageDays !== null ? ` (${sourceFreshness.ageDays} ngày)` : ""}. Hãy xác minh lại các thông tin có thể thay đổi trước khi đặt hàng.</p>
    </div>}

    <div className={`report-decision ${report.risk.label === "INSUFFICIENT_INFORMATION" ? "insufficient" : ""}`}>
      <article>
        <span className="card-label">RỦI RO TỔNG THỂ</span>
        <MetricRing value={overall} label="Rủi ro tổng thể" suffix="/100" tone={label.tone} />
        <span className={`report-risk-pill ${label.tone}`}>{label.text}</span>
        {report.risk.label === "INSUFFICIENT_INFORMATION" &&
          <p>Không có điểm rủi ro thấp mặc định khi bằng chứng chưa đủ.</p>}
      </article>
      <article>
        <span className="card-label">ĐỘ TIN CẬY</span>
        <MetricRing value={report.risk.confidence * 100} label="Độ tin cậy" tone="blue" />
        <p>Mức tin cậy của kết quả dựa trên chất lượng và độ đầy đủ của bằng chứng.</p>
      </article>
      <article>
        <span className="card-label">ĐỘ PHỦ DỮ LIỆU</span>
        <MetricRing value={report.risk.coverage * 100} label="Độ phủ dữ liệu" />
        <p>Tỷ trọng hạng mục có bằng chứng hỗ trợ.</p>
      </article>
    </div>

    <section id="report-risk-dimensions" className="report-dimensions" aria-label="Các chiều rủi ro">
      <div className="section-heading">
        <div><span className="card-label">CÁC CHIỀU RỦI RO</span><h3>Rủi ro tập trung ở đâu?</h3></div>
        <span>{report.risk.dimensions.length} hạng mục</span>
      </div>
      <p className="chart-caption">Điểm càng cao, rủi ro càng lớn. Vùng kẻ sọc là hạng mục chưa đủ bằng chứng.</p>
      <div className="risk-chart-scale" aria-hidden="true"><span>0</span><span>50</span><span>100</span></div>
      <div className="report-dimension-list">
        {report.risk.dimensions.map((item, index) => {
          const dimension = typeof item.dimension === "string" ? item.dimension : `dimension-${index}`;
          const dimensionRisk = typeof item.risk === "number" ? item.risk : null;
          const confidence = typeof item.effective_confidence === "number" ? item.effective_confidence : null;
          const ids = Array.isArray(item.evidence_ids)
            ? item.evidence_ids.filter((value): value is string => typeof value === "string")
            : [];
          return <article className={`report-dimension ${dimensionRisk === null ? "unknown" : ""}`} key={dimension}>
            <div><strong>{REPORT_DIMENSION_LABELS[dimension] ?? dimension}</strong><span>{dimensionRisk === null ? "Chưa đủ bằng chứng" : `${Math.round(dimensionRisk)}/100`}</span></div>
            <RiskBar value={dimensionRisk} label={REPORT_DIMENSION_LABELS[dimension] ?? dimension} />
            <details className="dimension-detail"><summary>Độ tin cậy & nguồn</summary><div className="dimension-meta">
              <small>Độ tin cậy hiệu dụng: {confidence === null ? "chưa xác định" : reportPercent(confidence)}</small>
              {ids.length > 0 && <span>{ids.map(id =>
                availableEvidenceIds.has(id)
                  ? <a href={`#${reportEvidenceAnchor(id)}`} key={id}>{id}</a>
                  : <span className="scoring-reference" key={id}>{id} · tham chiếu chấm điểm</span>
              )}</span>}
            </div></details>
          </article>;
        })}
      </div>
    </section>

    <div className="report-grid">
      <article className="identity-card">
        <div className="section-heading">
          <div><span className="card-label">NHÀ MÁY / THƯƠNG MẠI</span><h3>Nhận định loại hình</h3></div>
          <span>{typeof factory.classification === "string" ? factory.classification : "UNCERTAIN"}</span>
        </div>
        <div className="identity-bars">
          <div><span><b>Khả năng nhà máy</b><small>{optionalReportPercent(factory.factory_likelihood)}</small></span><i><b style={{ width: reportBarWidth(factory.factory_likelihood) }} /></i></div>
          <div><span><b>Khả năng thương mại</b><small>{optionalReportPercent(factory.trader_likelihood)}</small></span><i className="dark"><b style={{ width: reportBarWidth(factory.trader_likelihood) }} /></i></div>
        </div>
        <p className="identity-note">Độ tin cậy nhận định: {optionalReportPercent(factory.confidence)}. Đây là tổng hợp bằng chứng, không phải xác minh pháp lý độc lập.</p>
      </article>

      <article className="report-summary-card">
        <div className="section-heading">
          <div><span className="card-label">ĐÁNH GIÁ NGƯỜI MUA</span><h3>Tóm tắt đánh giá</h3></div>
          <span>{review.mode === "semantic" ? "Ngữ nghĩa" : "Xác định"}</span>
        </div>
        <dl className="report-summary-stats">
          <div><dt>Độ tin cậy đánh giá</dt><dd>{reviewReliability === null ? "Chưa xác định" : reportPercent(reviewReliability)}</dd></div>
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
            ? <ReportPages items={report.key_risks} label="Phát hiện rủi ro">{items => items.map(finding => <FindingCard finding={finding} availableEvidenceIds={availableEvidenceIds} key={finding.finding_key} />)}</ReportPages>
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
            ? <ReportPages items={report.positive_signals} label="Tín hiệu tích cực">{items => items.map(finding => <FindingCard finding={finding} availableEvidenceIds={availableEvidenceIds} key={finding.finding_key} />)}</ReportPages>
            : <p className="report-empty-copy">Chưa có tín hiệu tích cực đủ căn cứ để hiển thị.</p>}
        </div>
      </article>
    </div>

    <article id="report-next-actions" className="actions-card report-actions">
      <div className="card-label">HÀNH ĐỘNG ĐỀ XUẤT</div>
      <h3>Trước khi đặt hàng</h3>
      <ReportPages items={report.recommended_actions_vi} label="Hành động đề xuất">{(items, offset) => <ol>{items.map((action, index) =>
        <li key={action}><span>{offset + index + 1}</span><p><strong>{action}</strong></p></li>
      )}</ol>}</ReportPages>
    </article>

    <div className="report-unknowns">
      <section aria-label="Thông tin còn thiếu">
        <span className="card-label">THÔNG TIN CÒN THIẾU</span>
        <MissingList tags title="Trường nguồn chưa có" values={report.missing_data.source_fields} />
        <MissingList tags title="Chiều rủi ro chưa đủ bằng chứng" values={report.missing_data.risk_dimensions} />
        <MissingList title="Điểm chưa chắc chắn" values={report.missing_data.uncertainties_vi} />
        {!report.missing_data.source_fields.length && !report.missing_data.risk_dimensions.length && !report.missing_data.uncertainties_vi.length &&
          <p>Không có mục thiếu được ghi nhận trong payload báo cáo.</p>}
      </section>
      <section aria-label="Giới hạn báo cáo">
        <span className="card-label">GIỚI HẠN</span>
        <ReportPages items={report.limitations_vi} label="Giới hạn">{items => <ul>{items.map(item => <li key={item}>{item}</li>)}</ul>}</ReportPages>
      </section>
    </div>

    <section id="report-source-evidence" className="report-sources" aria-label="Nguồn và bằng chứng">
      <div className="section-heading">
        <div><span className="card-label">NGUỒN VÀ BẰNG CHỨNG</span><h3>Kiểm tra bằng chứng gốc</h3></div>
        <span>{report.evidence.length} mục</span>
      </div>
      <p className="chart-caption">Mở từng mục để xem dữ liệu gốc. Liên kết từ phát hiện sẽ mở đúng bằng chứng.</p>
      <p className="report-source-freshness">{uploaded ? "Thời điểm xử lý HTML dùng cho báo cáo" : "Ảnh chụp dữ liệu dùng cho báo cáo"}: {sourceFreshness.label}{!uploaded && sourceFreshness.stale ? " · DỮ LIỆU CŨ" : ""}.</p>
      <div className="report-source-list">
        {report.evidence.map(item => <EvidenceCard evidence={item} extractedAt={report.extracted_at} uploaded={uploaded} key={item.evidence_id} />)}
      </div>
      {source && <a className="report-origin-link" href={source} target="_blank" rel="noreferrer">Mở trang nguồn {report.platform} ↗</a>}
    </section>
    <footer className="report-method-note">Phiên bản chấm điểm: <code>{report.risk.scoring_version}</code> · Báo cáo hỗ trợ thẩm định dựa trên bằng chứng đã thu thập.</footer>
  </section>;
}
