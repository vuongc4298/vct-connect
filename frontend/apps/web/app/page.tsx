"use client";

import { SignInButton, SignUpButton, UserButton, useAuth } from "@clerk/nextjs";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { FIXTURE_URL, type Analysis, type GuestPreviewV1, type ReportV1 } from "@vct/contracts";
import { ApiError, getAnalysis, getGuestAnalysis, getGuestPreview, getReport, submitGuestAnalysis } from "@vct/api-client";
import { submitSelectedAnalysis } from "./analysis-request";
import { analysisPresentation } from "./analysis-status";
import { ExtractionEvidence, isFixtureResult } from "./extraction-evidence";
import { FullReport } from "./full-report";
import { GuestPreview } from "./guest-preview";

const DEMO_SIGNALS = [
  { tone: "risk", title: "Thông tin pháp nhân chưa đầy đủ", body: "Kịch bản demo chưa có mã đăng ký kinh doanh để đối chiếu chéo." },
  { tone: "risk", title: "Tỷ lệ giao dịch gần đây biến động", body: "Cần xác minh năng lực đáp ứng đơn hàng lớn trước khi đặt cọc." },
  { tone: "positive", title: "Lịch sử hoạt động ổn định", body: "Hồ sơ minh hoạ thể hiện hoạt động liên tục và phản hồi khách hàng đều." },
] as const;

type WorkspaceView = "analysis" | "history";
type EvidenceTone = "risk" | "watch" | "positive";
type EvidenceProfile = "low" | "medium" | "high";

type EvidenceArtifact =
  | { kind: "quotes"; reference: string; title: string; samples: Array<{ text: string; translation: string; meta: string }> }
  | { kind: "trend"; reference: string; title: string; metric: string; points: Array<{ label: string; value: number }>; annotation: string }
  | { kind: "record"; reference: string; title: string; fields: Array<{ label: string; value: string; flag?: boolean }> };

type EvidenceItem = {
  id: string;
  category: string;
  title: string;
  summary: string;
  detail: string;
  source: string;
  freshness: string;
  confidence: number;
  tone: EvidenceTone;
  followUp: string;
  artifacts?: EvidenceArtifact[];
};

type HistoryEntry = {
  id: string;
  supplier: string;
  platform: "1688";
  sourceUrl: string;
  analyzedAt: string;
  riskScore: number;
  confidence: number;
  profile: EvidenceProfile;
  notes: string;
  origin: "seed" | "live";
};

const EVIDENCE_PROFILES: Record<EvidenceProfile, EvidenceItem[]> = {
  medium: [
    { id: "identity-gap", category: "Pháp nhân", title: "Chưa đối chiếu được mã đăng ký", summary: "Hồ sơ demo không chứa mã doanh nghiệp để kiểm tra chéo.", detail: "Tên cửa hàng và tên nhận thanh toán cần được đối chiếu với giấy phép kinh doanh trước khi đặt cọc.", source: "Hồ sơ cửa hàng 1688", freshness: "Hôm nay", confidence: 84, tone: "risk", followUp: "Yêu cầu ảnh giấy phép kinh doanh và kiểm tra tên tài khoản ngân hàng.", artifacts: [
      { kind: "record", reference: "ID-01", title: "Trích xuất hồ sơ cửa hàng · Minh hoạ", fields: [{ label: "Tên cửa hàng", value: "广州未来科技商行" }, { label: "Tên pháp nhân", value: "Chưa cung cấp", flag: true }, { label: "Mã đăng ký", value: "Không tìm thấy", flag: true }, { label: "Khu vực", value: "Guangdong, CN" }] },
    ] },
    { id: "volume-shift", category: "Giao dịch", title: "Nhịp giao dịch biến động", summary: "Khối lượng minh hoạ tăng nhanh trong kỳ gần nhất.", detail: "Tăng trưởng đột biến có thể đến từ mùa vụ hoặc năng lực mới, nhưng cần xác minh để loại trừ dữ liệu bất thường.", source: "Chỉ số giao dịch demo", freshness: "7 ngày", confidence: 71, tone: "watch", followUp: "Đề nghị bảng năng lực tháng và xác nhận lead time bằng văn bản.", artifacts: [
      { kind: "trend", reference: "TX-04", title: "Đơn hàng theo tuần · Minh hoạ", metric: "đơn", points: [{ label: "T1", value: 18 }, { label: "T2", value: 21 }, { label: "T3", value: 19 }, { label: "T4", value: 47 }, { label: "T5", value: 63 }], annotation: "Tăng 3,3× từ tuần 3 đến tuần 5; chưa có dữ liệu công suất tương ứng." },
    ] },
    { id: "operating-history", category: "Hoạt động", title: "Lịch sử cửa hàng ổn định", summary: "Hồ sơ minh hoạ duy trì hoạt động liên tục nhiều năm.", detail: "Dấu hiệu hoạt động đều giúp giảm rủi ro cửa hàng mới, nhưng không thay thế việc xác minh pháp nhân.", source: "Dòng thời gian hồ sơ", freshness: "30 ngày", confidence: 88, tone: "positive", followUp: "Đối chiếu ngày thành lập trên giấy phép kinh doanh." },
    { id: "review-pattern", category: "Đánh giá", title: "Phản hồi tập trung theo cụm", summary: "Đánh giá 5★ tăng đột biến và nhiều bình luận có cấu trúc tương tự.", detail: "Mẫu phản hồi tập trung có thể phản ánh chiến dịch bán hàng hoặc chất lượng đánh giá chưa đồng đều.", source: "Mẫu đánh giá demo", freshness: "14 ngày", confidence: 79, tone: "watch", followUp: "Đọc thủ công đánh giá có ảnh và liên hệ hai khách hàng tham chiếu.", artifacts: [
      { kind: "trend", reference: "RV-12", title: "Đánh giá 5★ theo tuần · Minh hoạ", metric: "đánh giá", points: [{ label: "T1", value: 8 }, { label: "T2", value: 11 }, { label: "T3", value: 9 }, { label: "T4", value: 46 }, { label: "T5", value: 58 }], annotation: "Tăng 6,4× từ tuần 3 đến tuần 5; 41% bình luận mới có cụm từ tương tự." },
      { kind: "quotes", reference: "RV-13", title: "Bình luận tiếng Trung được lấy mẫu · Minh hoạ", samples: [
        { text: "质量很好，物流很快，值得购买。", translation: "Chất lượng rất tốt, giao hàng nhanh, đáng mua.", meta: "5★ · tài khoản demo A · 09:12" },
        { text: "质量不错，发货很快，值得购买。", translation: "Chất lượng tốt, gửi hàng nhanh, đáng mua.", meta: "5★ · tài khoản demo B · 09:18" },
        { text: "东西很好，物流很快，下次再来。", translation: "Sản phẩm tốt, giao hàng nhanh, lần sau sẽ mua tiếp.", meta: "5★ · tài khoản demo C · 09:26" },
      ] },
    ] },
  ],
  low: [
    { id: "verified-identity", category: "Pháp nhân", title: "Thông tin pháp nhân nhất quán", summary: "Tên doanh nghiệp, địa chỉ và tài khoản nhận tiền khớp trong dữ liệu minh hoạ.", detail: "Ba trường nhận diện chính thống nhất, tạo nền tảng tốt cho bước xác minh tài liệu gốc.", source: "Hồ sơ doanh nghiệp demo", freshness: "3 ngày", confidence: 91, tone: "positive", followUp: "Yêu cầu bản sao đóng dấu trước đơn hàng đầu tiên." },
    { id: "stable-volume", category: "Giao dịch", title: "Khối lượng giao dịch ổn định", summary: "Không có biến động lớn trong sáu kỳ minh hoạ gần nhất.", detail: "Nhịp giao dịch đều phù hợp với năng lực khai báo và không xuất hiện đỉnh bất thường.", source: "Chỉ số giao dịch demo", freshness: "7 ngày", confidence: 86, tone: "positive", followUp: "Xác nhận lịch sản xuất cho SKU cụ thể." },
    { id: "capacity-proof", category: "Năng lực", title: "Bằng chứng nhà xưởng còn cũ", summary: "Video nhà xưởng minh hoạ đã quá sáu tháng.", detail: "Nội dung vẫn hữu ích nhưng có thể không phản ánh công suất và thiết bị hiện tại.", source: "Tài liệu nhà cung cấp demo", freshness: "8 tháng", confidence: 58, tone: "watch", followUp: "Yêu cầu video call trực tiếp tại dây chuyền.", artifacts: [
      { kind: "record", reference: "CP-03", title: "Siêu dữ liệu video nhà xưởng · Minh hoạ", fields: [{ label: "Ngày ghi hình", value: "12/01/2026", flag: true }, { label: "Dây chuyền khai báo", value: "8" }, { label: "Dây chuyền nhìn thấy", value: "3", flag: true }, { label: "Vị trí GPS", value: "Không có", flag: true }] },
    ] },
  ],
  high: [
    { id: "payment-mismatch", category: "Thanh toán", title: "Tên người nhận không khớp", summary: "Tài khoản nhận tiền minh hoạ khác tên pháp nhân khai báo.", detail: "Thanh toán cho bên thứ ba làm tăng rủi ro tranh chấp và khó truy vết giao dịch.", source: "Hướng dẫn thanh toán demo", freshness: "Hôm nay", confidence: 94, tone: "risk", followUp: "Không chuyển tiền cho đến khi có giải trình và chứng từ uỷ quyền hợp lệ.", artifacts: [
      { kind: "record", reference: "PY-02", title: "Đối chiếu người nhận · Minh hoạ", fields: [{ label: "Pháp nhân khai báo", value: "义乌市光明贸易有限公司" }, { label: "Người nhận thanh toán", value: "陈伟 / CHEN WEI", flag: true }, { label: "Ngân hàng", value: "Tài khoản cá nhân", flag: true }, { label: "Chứng từ uỷ quyền", value: "Chưa cung cấp", flag: true }] },
    ] },
    { id: "young-store", category: "Hoạt động", title: "Hồ sơ hoạt động còn mới", summary: "Lịch sử cửa hàng minh hoạ ngắn hơn tuyên bố của người bán.", detail: "Chênh lệch thời gian hoạt động cần được làm rõ bằng giấy phép và lịch sử pháp nhân.", source: "Dòng thời gian hồ sơ", freshness: "2 ngày", confidence: 82, tone: "risk", followUp: "Đối chiếu ngày thành lập và lịch sử thay đổi tên doanh nghiệp.", artifacts: [
      { kind: "record", reference: "ID-09", title: "Đối chiếu tuổi hồ sơ · Minh hoạ", fields: [{ label: "Người bán tuyên bố", value: "6 năm hoạt động" }, { label: "Hồ sơ xuất hiện lần đầu", value: "14 tháng trước", flag: true }, { label: "Ngày thành lập pháp nhân", value: "Chưa cung cấp", flag: true }, { label: "Lịch sử đổi tên", value: "Không có dữ liệu", flag: true }] },
    ] },
    { id: "review-anomaly", category: "Đánh giá", title: "Cụm đánh giá có dấu hiệu bất thường", summary: "Tỷ lệ nội dung lặp lại cao trong mẫu minh hoạ.", detail: "Tín hiệu này không kết luận đánh giá giả nhưng làm giảm độ tin cậy của điểm phản hồi tổng hợp.", source: "Mẫu đánh giá demo", freshness: "7 ngày", confidence: 86, tone: "risk", followUp: "Ưu tiên đánh giá có ảnh, video và lịch sử người mua.", artifacts: [
      { kind: "trend", reference: "RV-21", title: "Tỷ trọng đánh giá 5★ · Minh hoạ", metric: "%", points: [{ label: "T1", value: 62 }, { label: "T2", value: 65 }, { label: "T3", value: 64 }, { label: "T4", value: 91 }, { label: "T5", value: 96 }], annotation: "Tỷ trọng 5★ tăng 32 điểm phần trăm trong hai tuần, không đi kèm tăng trưởng đánh giá có ảnh." },
      { kind: "quotes", reference: "RV-22", title: "Cụm nội dung lặp lại · Minh hoạ", samples: [
        { text: "老板服务很好，质量很好，五星好评。", translation: "Chủ shop phục vụ tốt, chất lượng tốt, đánh giá 5 sao.", meta: "5★ · không có ảnh · 14:02" },
        { text: "服务很好，产品质量很好，五星好评。", translation: "Dịch vụ tốt, chất lượng sản phẩm tốt, đánh giá 5 sao.", meta: "5★ · không có ảnh · 14:04" },
      ] },
    ] },
    { id: "sample-pass", category: "Sản phẩm", title: "Mẫu thử đạt yêu cầu cơ bản", summary: "Biên bản kiểm tra demo ghi nhận kích thước và hoàn thiện phù hợp.", detail: "Kết quả mẫu là tín hiệu tích cực nhưng chưa chứng minh độ ổn định của sản xuất hàng loạt.", source: "Biên bản QC demo", freshness: "21 ngày", confidence: 73, tone: "positive", followUp: "Đặt lô thử nhỏ và kiểm tra ngẫu nhiên trước khi tăng MOQ." },
  ],
};

const DEMO_HISTORY_SEED: HistoryEntry[] = [
  { id: "demo-history-medium", supplier: "Guangzhou Future Tech", platform: "1688", sourceUrl: FIXTURE_URL, analyzedAt: "2026-09-27T08:30:00.000Z", riskScore: 64, confidence: 72, profile: "medium", notes: "Xác minh giấy phép kinh doanh trước khi trao đổi điều khoản đặt cọc.", origin: "seed" },
  { id: "demo-history-low", supplier: "Shenzhen Nova Home", platform: "1688", sourceUrl: "https://detail.1688.com/offer/demo-low-risk.html", analyzedAt: "2026-09-25T03:15:00.000Z", riskScore: 31, confidence: 86, profile: "low", notes: "Đã nhận catalogue. Cần lên lịch video call tại xưởng.", origin: "seed" },
  { id: "demo-history-high", supplier: "Yiwu Bright Trading", platform: "1688", sourceUrl: "https://detail.1688.com/offer/demo-high-risk.html", analyzedAt: "2026-09-22T10:45:00.000Z", riskScore: 78, confidence: 81, profile: "high", notes: "Tạm dừng thanh toán vì tên tài khoản nhận tiền không khớp.", origin: "seed" },
];

function riskLevel(score: number) {
  if (score >= 70) return { label: "Cao", className: "high" };
  if (score >= 45) return { label: "Trung bình", className: "medium" };
  return { label: "Thấp", className: "low" };
}

function formatDemoDate(value: string) {
  return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(value));
}

function Brand() {
  return <div className="brand"><span className="brand-mark">V</span><span>VCT <strong>Connect</strong></span></div>;
}

function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warning" }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

function Landing() {
  const [guestId, setGuestId] = useState<string | null>(null);
  const [guestAnalysis, setGuestAnalysis] = useState<Analysis | null>(null);
  const [guestPreview, setGuestPreview] = useState<GuestPreviewV1 | null>(null);
  const [guestError, setGuestError] = useState("");
  const [guestBusy, setGuestBusy] = useState(false);

  useEffect(() => {
    if (!guestId) return;
    let active = true;
    let timer: number | undefined;
    async function poll() {
      try {
        const current = await getGuestAnalysis(guestId!);
        if (active) { setGuestAnalysis(current); setGuestError(""); }
        if (current.status === "COMPLETED") {
          try {
            const preview = await getGuestPreview(guestId!);
            if (active) setGuestPreview(preview);
          } catch (cause) {
            if (active) setGuestError(cause instanceof Error ? cause.message : "Không thể tải bản xem trước");
          }
        }
        if (!analysisPresentation(current).shouldPoll) return;
      } catch (cause) {
        if (active) setGuestError(cause instanceof Error ? cause.message : "Không thể tải phân tích");
        if (cause instanceof ApiError && cause.status === 404) return;
      }
      if (active) timer = window.setTimeout(() => { void poll(); }, 1500);
    }
    void poll();
    return () => { active = false; window.clearTimeout(timer); };
  }, [guestId]);

  async function submitGuest(event: FormEvent) {
    event.preventDefault();
    setGuestBusy(true); setGuestError(""); setGuestAnalysis(null); setGuestPreview(null); setGuestId(null);
    try {
      const submitted = await submitGuestAnalysis({ source_url: FIXTURE_URL });
      setGuestId(submitted.id);
    } catch (cause) {
      setGuestError(cause instanceof Error ? cause.message : "Không thể gửi phân tích");
    } finally { setGuestBusy(false); }
  }

  return <div className="landing">
    <nav className="landing-nav">
      <Brand />
      <div className="landing-actions">
        <SignInButton><button type="button" className="button button-ghost">Đăng nhập</button></SignInButton>
        <SignUpButton><button type="button" className="button button-dark">Dùng bản demo</button></SignUpButton>
      </div>
    </nav>
    <main className="landing-main">
      <section className="hero-copy">
        <div className="kicker"><span className="pulse-dot" /> Trợ lý đánh giá nhà cung cấp</div>
        <h1>Ra quyết định nhập hàng với <em>bằng chứng rõ ràng.</em></h1>
        <p className="hero-text">VCT Connect biến dữ liệu nhà cung cấp Trung Quốc thành báo cáo rủi ro dễ hiểu dành cho người bán Việt Nam.</p>
        <div className="hero-actions">
          <SignUpButton><button type="button" className="button button-primary button-large">Phân tích nhà cung cấp <span>→</span></button></SignUpButton>
          <span className="hero-note">Không cần thẻ thanh toán</span>
        </div>
        <form onSubmit={submitGuest} className="guest-demo-form">
          <p>Thử fixture demo mà không cần tài khoản. Giới hạn tạm thời áp dụng cho trình duyệt này.</p>
          <button type="submit" className="button button-ghost" disabled={guestBusy}>
            {guestBusy ? "Đang gửi…" : "Thử demo khách"}
          </button>
        </form>
        {guestError && <p role="alert" className="error-banner">{guestError}</p>}
        {guestId && <ProgressCard analysis={guestAnalysis} delayed={false} requestedMethod={null} />}
        {guestId && guestAnalysis?.status === "COMPLETED" && guestPreview && <>
          <GuestPreview preview={guestPreview} />
          <div className="guest-preview-cta">
            <SignUpButton><button type="button" className="button button-primary">Đăng ký để xem báo cáo đầy đủ</button></SignUpButton>
            <span>Đăng nhập và dùng tiện ích để có thêm bằng chứng khi trang nguồn hạn chế truy cập.</span>
          </div>
        </>}
        <div className="trust-row">
          <div><strong>01</strong><span>luồng demo hoàn chỉnh</span></div>
          <div><strong>&lt; 2 phút</strong><span>mục tiêu phân tích</span></div>
          <div><strong>Demo</strong><span>dữ liệu minh hoạ</span></div>
        </div>
      </section>
      <section className="preview-window" aria-label="Bản xem trước báo cáo demo">
        <div className="window-bar"><span /><span /><span /><small>BÁO CÁO DEMO</small></div>
        <div className="preview-content">
          <div className="preview-heading">
            <div><span className="platform-chip">1688</span><h2>Guangzhou Future Tech</h2><p>Nhà cung cấp · Guangdong, CN</p></div>
            <Pill tone="warning">Rủi ro trung bình</Pill>
          </div>
          <div className="score-grid">
            <div className="risk-ring"><span><strong>64</strong><small>/100</small></span></div>
            <div className="preview-metrics">
              <div><span>Độ tin cậy</span><strong>72%</strong><i style={{ width: "72%" }} /></div>
              <div><span>Độ phủ dữ liệu</span><strong>68%</strong><i style={{ width: "68%" }} /></div>
            </div>
          </div>
          <div className="mini-alert"><span>!</span><div><strong>Cần xác minh trước khi đặt cọc</strong><p>2 tín hiệu cần được kiểm tra thêm.</p></div></div>
          <div className="preview-footer"><span>Danh tính</span><span>Giao dịch</span><span>Đánh giá</span><span>Năng lực</span></div>
        </div>
        <div className="floating-proof"><span>✓</span><div><strong>Phân tích hoàn tất</strong><small>12 trường dữ liệu minh hoạ</small></div></div>
      </section>
    </main>
    <footer className="landing-footer"><span>Dữ liệu demo · Không phải đánh giá nhà cung cấp thực tế</span><span>Nguồn fixture: 1688</span></footer>
  </div>;
}

function Sidebar({ view, historyCount, onViewChange }: { view: WorkspaceView; historyCount: number; onViewChange: (view: WorkspaceView) => void }) {
  return <aside className="sidebar">
    <Brand />
    <nav className="side-nav" aria-label="Điều hướng sản phẩm">
      <button type="button" aria-label="Phân tích mới" className={view === "analysis" ? "active" : ""} aria-current={view === "analysis" ? "page" : undefined} onClick={() => onViewChange("analysis")}><span>◇</span><span className="nav-label">Phân tích mới</span></button>
      <button type="button" aria-label={`Lịch sử, ${historyCount} mục`} className={view === "history" ? "active" : ""} aria-current={view === "history" ? "page" : undefined} onClick={() => onViewChange("history")}><span>◷</span><span className="nav-label">Lịch sử</span><span className="nav-count">{historyCount}</span></button>
    </nav>
    <div className="sidebar-footer"><span>?</span><div><strong>Trung tâm trợ giúp</strong><small>Hướng dẫn sử dụng</small></div></div>
  </aside>;
}

function ProgressCard({ analysis, delayed, requestedMethod }: { analysis: Analysis | null; delayed: boolean; requestedMethod: string | null }) {
  const presentation = analysisPresentation(analysis);
  const method = analysis?.extraction_method ?? requestedMethod;
  const liveExtraction = method === "PUBLIC_HTTP" || method === "PUBLIC_BROWSER" || method === "USER_UPLOAD" || method === "EXTENSION_DOM";
  return <section className="progress-card" aria-live="polite">
    <div className="progress-top"><div><span className={`status-orb ${presentation.orbClass}`}>{presentation.orbSymbol}</span><div><strong>{presentation.headline}</strong><p>{presentation.detail}</p></div></div><Pill tone={presentation.pillTone}>{presentation.pillLabel}</Pill></div>
    <div className="steps">
      <div className="done"><span>✓</span><strong>Đã nhận URL</strong><small>Kiểm tra nguồn</small></div><i />
      <div className={presentation.complete ? "done" : presentation.final ? "" : "current"}><span>{presentation.complete ? "✓" : "2"}</span><strong>{liveExtraction ? "Trích xuất" : "Phân tích"}</strong><small>{liveExtraction ? "Đọc bằng chứng" : "Tổng hợp tín hiệu"}</small></div><i />
      <div className={presentation.complete ? "done" : ""}><span>{presentation.complete ? "✓" : "3"}</span><strong>{liveExtraction ? "Bằng chứng" : "Báo cáo"}</strong><small>{liveExtraction ? "Độ phủ và nguồn" : "Đưa ra khuyến nghị"}</small></div>
    </div>
    {presentation.retrying && analysis?.next_retry_at && <p className="delay-note">Lần thử tiếp theo dự kiến lúc {new Date(analysis.next_retry_at).toLocaleTimeString("vi-VN")}.</p>}
    {delayed && !presentation.terminal && !presentation.retrying && <p className="delay-note">Quá trình đang lâu hơn dự kiến. VCT Connect sẽ tiếp tục kiểm tra.</p>}
  </section>;
}

function EvidenceArtifactCard({ artifact }: { artifact: EvidenceArtifact }) {
  if (artifact.kind === "quotes") {
    return <article className="artifact-card quote-artifact">
      <div className="artifact-title"><span>{artifact.reference}</span><strong>{artifact.title}</strong></div>
      <div className="quote-samples">{artifact.samples.map((sample, index) => <blockquote key={`${artifact.reference}-${index}`}>
        <p lang="zh-CN">“{sample.text}”</p><footer><span>{sample.translation}</span><small>{sample.meta}</small></footer>
      </blockquote>)}</div>
    </article>;
  }

  if (artifact.kind === "trend") {
    const maxValue = Math.max(...artifact.points.map(point => point.value), 1);
    return <article className="artifact-card trend-artifact">
      <div className="artifact-title"><span>{artifact.reference}</span><strong>{artifact.title}</strong></div>
      <div className="artifact-chart" role="img" aria-label={`${artifact.title}. ${artifact.annotation}`}>
        {artifact.points.map(point => <div className="chart-column" key={point.label}><div><i style={{ height: `${Math.max(8, (point.value / maxValue) * 100)}%` }}><b>{point.value}{artifact.metric === "%" ? "%" : ""}</b></i></div><small>{point.label}</small></div>)}
      </div>
      <p className="artifact-annotation"><span>↗</span>{artifact.annotation}</p>
    </article>;
  }

  return <article className="artifact-card record-artifact">
    <div className="artifact-title"><span>{artifact.reference}</span><strong>{artifact.title}</strong></div>
    <dl>{artifact.fields.map(field => <div className={field.flag ? "flag" : ""} key={field.label}><dt>{field.label}</dt><dd>{field.value}{field.flag && <span>!</span>}</dd></div>)}</dl>
  </article>;
}

function EvidenceExplorer({ profile }: { profile: EvidenceProfile }) {
  const [filter, setFilter] = useState<"all" | EvidenceTone>("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const evidence = EVIDENCE_PROFILES[profile];
  const visible = filter === "all" ? evidence : evidence.filter(item => item.tone === filter);
  const filterLabels: Array<["all" | EvidenceTone, string]> = [["all", "Tất cả"], ["risk", "Rủi ro"], ["watch", "Cần xem"], ["positive", "Tích cực"]];

  return <section className="evidence-explorer" aria-label="Bằng chứng rủi ro minh hoạ">
    <div className="evidence-heading">
      <div><div className="card-label">BẰNG CHỨNG RỦI RO</div><h3>Vì sao có điểm số này?</h3><p>Chọn một tín hiệu để xem nguồn, độ mới và bước xác minh đề xuất.</p></div>
      <Pill>{evidence.length} bằng chứng demo</Pill>
    </div>
    <div className="evidence-filters" aria-label="Lọc bằng chứng">
      {filterLabels.map(([value, label]) => <button type="button" key={value} className={filter === value ? "active" : ""} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}
    </div>
    <div className="evidence-list">
      {visible.map(item => {
        const isExpanded = expanded === item.id;
        return <article className={`evidence-item ${item.tone}`} key={item.id}>
          <button type="button" className="evidence-summary" aria-expanded={isExpanded} onClick={() => setExpanded(isExpanded ? null : item.id)}>
            <span className="evidence-icon">{item.tone === "positive" ? "✓" : item.tone === "risk" ? "!" : "•"}</span>
            <span className="evidence-copy"><small>{item.category}{item.artifacts?.length ? ` · ${item.artifacts.map(artifact => artifact.reference).join(", ")}` : ""}</small><strong>{item.title}</strong><span>{item.summary}</span></span>
            <span className="evidence-confidence"><small>Tin cậy</small><strong>{item.confidence}%</strong><i><b style={{ width: `${item.confidence}%` }} /></i></span>
            <span className="evidence-chevron">{isExpanded ? "−" : "+"}</span>
          </button>
          {isExpanded && <div className="evidence-detail">
            <p>{item.detail}</p>
            <dl><div><dt>Nguồn minh hoạ</dt><dd>{item.source}</dd></div><div><dt>Độ mới</dt><dd>{item.freshness}</dd></div><div><dt>Độ tin cậy</dt><dd>{item.confidence}%</dd></div></dl>
            {item.artifacts?.length && <div className="artifact-section"><div className="artifact-section-label"><span>DẪN CHỨNG THAM CHIẾU</span><small>Dữ liệu mockup</small></div>{item.artifacts.map(artifact => <EvidenceArtifactCard artifact={artifact} key={artifact.reference} />)}</div>}
            <div className="evidence-follow-up"><span>→</span><p><strong>Bước xác minh</strong>{item.followUp}</p></div>
          </div>}
        </article>;
      })}
    </div>
  </section>;
}

function HistoryWorkspace({ history, selectedId, storageError, onSelect, onNoteChange, onNewAnalysis }: {
  history: HistoryEntry[];
  selectedId: string | null;
  storageError: boolean;
  onSelect: (id: string) => void;
  onNoteChange: (id: string, notes: string) => void;
  onNewAnalysis: () => void;
}) {
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLocaleLowerCase("vi");
  const visible = history.filter(entry => !normalizedQuery || entry.supplier.toLocaleLowerCase("vi").includes(normalizedQuery) || entry.sourceUrl.toLocaleLowerCase("vi").includes(normalizedQuery));
  const selected = visible.find(entry => entry.id === selectedId) ?? visible[0] ?? null;

  return <main className="dashboard history-dashboard" id="history">
    <section className="dashboard-intro">
      <div><Pill tone="good">LƯU TRONG TRÌNH DUYỆT</Pill><h1>Lịch sử phân tích</h1><p>Xem lại báo cáo demo, bằng chứng và ghi chú riêng cho từng nhà cung cấp.</p></div>
      <button type="button" className="button button-primary" onClick={onNewAnalysis}>+ Phân tích mới</button>
    </section>
    <div className={`history-notice ${storageError ? "storage-error" : ""}`} role={storageError ? "alert" : undefined}><span>{storageError ? "!" : "i"}</span><p>{storageError ? "Trình duyệt đang chặn bộ nhớ cục bộ. Ghi chú vẫn hiển thị trong phiên này nhưng sẽ không còn sau khi tải lại trang." : "Lịch sử và ghi chú trong bản demo chỉ được lưu cục bộ trên trình duyệt này. Tất cả bằng chứng đều là dữ liệu minh hoạ, không phải dữ liệu nhà cung cấp thực tế."}</p></div>
    <div className="history-layout">
      <section className="history-panel" aria-label="Danh sách phân tích">
        <div className="history-search"><span>⌕</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Tìm nhà cung cấp hoặc URL" aria-label="Tìm trong lịch sử" /></div>
        <div className="history-panel-title"><strong>{visible.length} kết quả</strong><span>Mới nhất trước</span></div>
        <div className="history-list">
          {visible.map(entry => {
            const level = riskLevel(entry.riskScore);
            return <button type="button" className={`history-entry ${selected?.id === entry.id ? "selected" : ""}`} key={entry.id} onClick={() => onSelect(entry.id)}>
              <span className="history-entry-top"><span><b>{entry.platform}</b><small>Minh hoạ</small></span><time>{formatDemoDate(entry.analyzedAt)}</time></span>
              <strong>{entry.supplier}</strong>
              <span className="history-entry-meta"><span className={`risk-badge ${level.className}`}>Rủi ro {level.label} · {entry.riskScore}</span><span>{entry.confidence}% tin cậy</span></span>
              <span className="history-note-preview">{entry.notes || "Chưa có ghi chú"}</span>
            </button>;
          })}
          {!visible.length && <div className="history-empty"><span>⌕</span><strong>Không tìm thấy kết quả</strong><p>Thử tên nhà cung cấp hoặc URL khác.</p></div>}
        </div>
      </section>
      <section className="history-detail" aria-live="polite">
        {selected ? <>
          <div className="history-detail-header">
            <div><div className="report-title-row"><span className="platform-chip">{selected.platform}</span><Pill>MINH HOẠ</Pill></div><h2>{selected.supplier}</h2><p>Phân tích ngày {formatDemoDate(selected.analyzedAt)} · Mã {selected.id.slice(0, 8).toUpperCase()}</p></div>
            <div className={`history-score ${riskLevel(selected.riskScore).className}`}><strong>{selected.riskScore}</strong><small>/100 rủi ro</small></div>
          </div>
          <div className="history-note-editor">
            <div><label htmlFor={`notes-${selected.id}`}>GHI CHÚ NHÀ CUNG CẤP</label><span>{storageError ? "Chưa thể lưu cục bộ" : "Tự động lưu cục bộ"}</span></div>
            <textarea id={`notes-${selected.id}`} value={selected.notes} maxLength={600} onChange={event => onNoteChange(selected.id, event.target.value)} placeholder="Ghi lại câu hỏi, điều khoản hoặc bước xác minh tiếp theo…" />
            <small>{selected.notes.length}/600 ký tự</small>
          </div>
          <EvidenceExplorer key={selected.id} profile={selected.profile} />
          <div className="history-source"><span>↗</span><div><strong>URL nguồn demo</strong><code>{selected.sourceUrl}</code></div></div>
        </> : <div className="history-empty detail"><span>◎</span><strong>Chọn một phân tích</strong><p>Chi tiết, ghi chú và bằng chứng sẽ xuất hiện tại đây.</p></div>}
      </section>
    </div>
  </main>;
}

function DemoReport({ analysisId, sourceUrl }: { analysisId: string; sourceUrl: string }) {
  return <section className="report" aria-label="Báo cáo rủi ro minh hoạ">
    <div className="demo-disclaimer"><span>i</span><p><strong>Nội dung minh hoạ giao diện</strong> · Các điểm số và tín hiệu dưới đây là dữ liệu demo, không phải bằng chứng nhà cung cấp thực tế.</p></div>
    <div className="report-header">
      <div><div className="report-title-row"><span className="platform-chip">1688</span><Pill tone="good">Đã phân tích</Pill></div><h2>Developer Fixture Supplier</h2><p>Nhà cung cấp demo · Nguồn 1688</p></div>
      <div className="report-ref"><small>MÃ PHÂN TÍCH</small><code>{analysisId.slice(0, 8).toUpperCase()}</code></div>
    </div>
    <div className="report-grid">
      <article className="overall-card">
        <div className="card-label">RỦI RO TỔNG THỂ <span title="Điểm minh hoạ">?</span></div>
        <div className="overall-score"><div className="risk-ring large"><span><strong>64</strong><small>/100</small></span></div><div><Pill tone="warning">TRUNG BÌNH</Pill><p>Có thể tiếp tục xem xét, nhưng cần xác minh hai tín hiệu chính trước khi đặt cọc.</p></div></div>
        <div className="coverage-row"><div><span>Độ tin cậy</span><strong>72%</strong><i><b style={{ width: "72%" }} /></i></div><div><span>Độ phủ dữ liệu</span><strong>68%</strong><i><b style={{ width: "68%" }} /></i></div></div>
      </article>
      <article className="identity-card">
        <div className="card-label">LOẠI HÌNH NHÀ CUNG CẤP</div>
        <div className="identity-bars"><div><span><b>Nhà máy</b><small>35%</small></span><i><b style={{ width: "35%" }} /></i></div><div><span><b>Đơn vị thương mại</b><small>65%</small></span><i className="dark"><b style={{ width: "65%" }} /></i></div></div>
        <p className="identity-note">Kịch bản demo nghiêng về đơn vị thương mại. Nên yêu cầu video nhà xưởng và hồ sơ sản xuất.</p>
      </article>
    </div>
    <div className="report-grid lower">
      <article className="signals-card">
        <div className="section-heading"><div><div className="card-label">TÍN HIỆU CHÍNH</div><h3>Điều cần chú ý</h3></div><span>3 tín hiệu</span></div>
        <div className="signal-list">{DEMO_SIGNALS.map((signal, index) => <div className={`signal ${signal.tone}`} key={signal.title}><span>{signal.tone === "positive" ? "✓" : index + 1}</span><div><strong>{signal.title}</strong><p>{signal.body}</p></div></div>)}</div>
      </article>
      <article className="actions-card">
        <div className="card-label">HÀNH ĐỘNG ĐỀ XUẤT</div><h3>Trước khi đặt hàng</h3>
        <ol><li><span>1</span><p><strong>Đối chiếu pháp nhân</strong><small>Yêu cầu giấy phép kinh doanh và tài khoản nhận tiền trùng tên.</small></p></li><li><span>2</span><p><strong>Xác minh năng lực</strong><small>Thực hiện video call tại xưởng và kiểm tra dây chuyền sản xuất.</small></p></li><li><span>3</span><p><strong>Đặt đơn thử nghiệm</strong><small>Bắt đầu với MOQ thấp và sử dụng phương thức thanh toán có bảo vệ.</small></p></li></ol>
      </article>
    </div>
    <EvidenceExplorer profile="medium" />
    <div className="evidence-row"><div><span>↗</span><div><strong>Nguồn phân tích demo</strong><code>{sourceUrl}</code></div></div><small>Fixture · Không phải dữ liệu trực tiếp</small></div>
  </section>;
}

export default function Page() {
  const { getToken, isLoaded, isSignedIn, userId } = useAuth();
  const [url, setUrl] = useState(FIXTURE_URL);
  const savedPageInput = useRef<HTMLInputElement>(null);
  const [savedPage, setSavedPage] = useState<File | null>(null);
  const [requestedMethod, setRequestedMethod] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [report, setReport] = useState<ReportV1 | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const [id, setId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [delayed, setDelayed] = useState(false);
  const [view, setView] = useState<WorkspaceView>("analysis");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [historyReady, setHistoryReady] = useState(false);
  const [historyOwnerId, setHistoryOwnerId] = useState<string | null>(null);
  const [historyStorageError, setHistoryStorageError] = useState(false);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);

  function clearSavedPage() {
    setSavedPage(null);
    if (savedPageInput.current) savedPageInput.current.value = "";
  }

  useEffect(() => {
    setId(null); setAnalysis(null); setReport(null); setReportError(""); setReportLoading(false); setError(""); setDelayed(false); setView("analysis"); setHistoryReady(false); setHistoryOwnerId(null); setHistoryStorageError(false);
    clearSavedPage(); setRequestedMethod(null);
    if (!userId) { setHistory([]); setSelectedHistoryId(null); return; }
    const storageKey = `vct-connect-demo-history:${userId}`;
    try {
      const stored = window.localStorage.getItem(storageKey);
      const parsed = stored ? JSON.parse(stored) : null;
      const initial = Array.isArray(parsed) && parsed.length ? parsed as HistoryEntry[] : DEMO_HISTORY_SEED;
      setHistory(initial);
      setSelectedHistoryId(initial[0]?.id ?? null);
    } catch {
      setHistory(DEMO_HISTORY_SEED);
      setSelectedHistoryId(DEMO_HISTORY_SEED[0].id);
      setHistoryStorageError(true);
    }
    setHistoryOwnerId(userId);
    setHistoryReady(true);
  }, [userId]);

  useEffect(() => {
    if (!userId) return;
    const analysisId = new URLSearchParams(window.location.search).get("analysis");
    if (!analysisId) return;
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(analysisId)) {
      setError("Mã phân tích không hợp lệ");
      return;
    }
    setRequestedMethod("EXTENSION_DOM");
    setId(analysisId);
    setView("analysis");
  }, [userId]);

  function clearAnalysisQuery() {
    const next = new URL(window.location.href);
    if (!next.searchParams.has("analysis")) return;
    next.searchParams.delete("analysis");
    window.history.replaceState(null, "", `${next.pathname}${next.search}${next.hash}`);
  }

  useEffect(() => {
    if (!userId || !historyReady || historyOwnerId !== userId) return;
    try {
      window.localStorage.setItem(`vct-connect-demo-history:${userId}`, JSON.stringify(history));
      setHistoryStorageError(false);
    } catch {
      setHistoryStorageError(true);
    }
  }, [history, historyOwnerId, historyReady, userId]);

  useEffect(() => {
    if (!id || !isSignedIn) return;
    let active = true;
    let timer: number | undefined;
    const delayTimer = window.setTimeout(() => { if (active) setDelayed(true); }, 15000);
    async function poll() {
      try {
        const current = await getAnalysis(id!, { getToken });
        if (active) {
          setAnalysis(current); setError("");
          if (current.extraction_method === "EXTENSION_DOM") setUrl(current.source_url);
        }
        if (!analysisPresentation(current).shouldPoll) return;
      } catch (cause) {
        if (active) setError(cause instanceof ApiError && cause.status === 404
          ? "Không tìm thấy phân tích cho tài khoản này. Đăng nhập cùng tài khoản VCT Connect đã dùng trong tiện ích."
          : cause instanceof Error ? cause.message : "Không thể tải phân tích");
        if (cause instanceof ApiError && [401, 403, 404].includes(cause.status)) {
          if (active) setId(null);
          return;
        }
      }
      if (active) timer = window.setTimeout(() => { void poll(); }, 1500);
    }
    void poll();
    return () => { active = false; window.clearTimeout(timer); window.clearTimeout(delayTimer); };
  }, [getToken, id, isSignedIn]);

  useEffect(() => {
    if (!id || !isSignedIn || analysis?.status !== "COMPLETED") return;
    let active = true;
    setReportLoading(true);
    setReportError("");
    void getReport(id, { getToken }).then(
      value => {
        if (!active) return;
        setReport(value);
        setReportError("");
      },
      cause => {
        if (!active) return;
        setReport(null);
        setReportError(
          cause instanceof ApiError && cause.status === 404
            ? "Phân tích này chưa có báo cáo đánh giá đã lưu. Chỉ hiển thị bằng chứng trích xuất hiện có."
            : cause instanceof Error
              ? cause.message
              : "Không thể tải báo cáo đánh giá",
        );
      },
    ).finally(() => {
      if (active) setReportLoading(false);
    });
    return () => { active = false; };
  }, [analysis?.status, getToken, id, isSignedIn]);

  useEffect(() => {
    if (!id || analysis?.status !== "COMPLETED" || !historyReady || !isFixtureResult(analysis.result)) return;
    const fixture = analysis.result;
    setHistory(current => {
      if (current.some(entry => entry.id === id)) return current;
      const completedEntry: HistoryEntry = {
        id,
        supplier: "Developer Fixture Supplier",
        platform: "1688",
        sourceUrl: fixture.source_url,
        analyzedAt: new Date().toISOString(),
        riskScore: 64,
        confidence: 72,
        profile: "medium",
        notes: "",
        origin: "live",
      };
      return [completedEntry, ...current];
    });
  }, [analysis, historyReady, id, url]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    clearAnalysisQuery();
    setBusy(true); setError(""); setAnalysis(null); setReport(null); setReportError(""); setReportLoading(false); setId(null); setDelayed(false);
    setRequestedMethod(savedPage ? "USER_UPLOAD" : url === FIXTURE_URL ? "FIXTURE" : "PUBLIC_HTTP");
    try {
      const submitted = await submitSelectedAnalysis(url, savedPage, { getToken });
      setId(submitted.id);
      if (savedPage) clearSavedPage();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể gửi phân tích");
    } finally { setBusy(false); }
  }

  function updateHistoryNote(entryId: string, notes: string) {
    setHistory(current => current.map(entry => entry.id === entryId ? { ...entry, notes } : entry));
  }

  function showNewAnalysis() {
    clearAnalysisQuery();
    setView("analysis");
    setId(null);
    setAnalysis(null);
    setReport(null);
    setReportError("");
    setReportLoading(false);
    setError("");
    setRequestedMethod(null);
    clearSavedPage();
  }

  if (!isLoaded) return <div className="loading-screen"><Brand /><span>Đang khởi tạo bản demo…</span></div>;
  if (!isSignedIn) return <Landing />;

  return <div className="product-shell">
    <Sidebar view={view} historyCount={history.length} onViewChange={setView} />
    <div className="workspace">
      <header className="workspace-header"><div><span>Không gian Pilot</span><i>/</i><strong>{view === "analysis" ? "Phân tích mới" : "Lịch sử"}</strong></div><nav className="mobile-nav" aria-label="Điều hướng di động"><button type="button" className={view === "analysis" ? "active" : ""} aria-current={view === "analysis" ? "page" : undefined} onClick={() => setView("analysis")}>Phân tích</button><button type="button" className={view === "history" ? "active" : ""} aria-current={view === "history" ? "page" : undefined} onClick={() => setView("history")}>Lịch sử</button></nav><div className="header-tools"><button type="button" className="icon-button" aria-label="Thông báo">♢<i /></button><span className="language">VI</span><UserButton /></div></header>
      {view === "history" ? <HistoryWorkspace history={history} selectedId={selectedHistoryId} storageError={historyStorageError} onSelect={setSelectedHistoryId} onNoteChange={updateHistoryNote} onNewAnalysis={showNewAnalysis} /> : <main className="dashboard" id="analysis">
        <section className="dashboard-intro"><div><Pill tone="good">BẢN DEMO TƯƠNG TÁC</Pill><h1>Phân tích nhà cung cấp</h1><p>Dán liên kết sản phẩm 1688, sản phẩm / cửa hàng Taobao hoặc sản phẩm / hồ sơ công ty Alibaba để xem bằng chứng công khai và độ phủ. URL mẫu hiển thị báo cáo rủi ro minh họa.</p></div>{(analysis?.status === "COMPLETED" || analysis?.status === "FAILED_FINAL") && <button type="button" className="button button-ghost" onClick={showNewAnalysis}>+ Phân tích mới</button>}</section>
        <section className="analyze-card">
          <form onSubmit={submit}>
            <label htmlFor="source-url">LIÊN KẾT 1688 / TAOBAO / ALIBABA</label>
            <div className="url-field"><span className="link-icon">↗</span><input id="source-url" type="url" required value={url} onChange={event => setUrl(event.target.value)} aria-describedby="url-help" /><button className="button button-primary" disabled={busy}>{busy ? <><i className="spinner" /> Đang gửi</> : <>{savedPage ? "Nhập trang đã lưu" : "Trích xuất"} <span>→</span></>}</button></div>
            <label htmlFor="saved-page">Trang 1688 / Taobao đã lưu (HTML, tùy chọn)</label>
            <input id="saved-page" ref={savedPageInput} type="file" accept=".html,.htm,text/html" onChange={event => setSavedPage(event.target.files?.[0] ?? null)} />
            <div className="form-meta" id="url-help"><span><b>1688 / Taobao / Alibaba</b> URL HTTPS: detail.1688.com/offer/…html, item.taobao.com/item.htm?id=…, shop&lt;ID&gt;.taobao.com / shop&lt;ID&gt;.world.taobao.com, www.alibaba.com/product-detail/…_&lt;ID&gt;.html hoặc &lt;store&gt;.en.alibaba.com/company_profile.html. HTML đã lưu và tiện ích chụp trang hỗ trợ 1688 / Taobao. Alibaba chỉ hỗ trợ trích xuất URL công khai. URL mẫu hiện tại chạy fixture demo.</span><Pill>{savedPage ? "USER_UPLOAD" : url === FIXTURE_URL ? "Dữ liệu fixture" : "Trích xuất công khai"}</Pill></div>
          </form>
        </section>
        {error && <div role="alert" className="error-banner"><span>!</span><div><strong>Không thể tiếp tục</strong><p>{error === "Analysis not found" ? "Không tìm thấy phân tích. Vui lòng gửi lại dữ liệu demo." : error}</p></div></div>}
        {id && <ProgressCard analysis={analysis} delayed={delayed} requestedMethod={requestedMethod} />}
        {id && analysis?.status === "COMPLETED" && reportLoading &&
          <section className="report-loading" aria-live="polite"><i className="spinner" /><span>Đang tải báo cáo đánh giá đã lưu…</span></section>}
        {id && analysis?.status === "COMPLETED" && report && <FullReport report={report} />}
        {id && analysis?.status === "COMPLETED" && !reportLoading && !report && reportError &&
          <div className="report-unavailable" role="status"><span>i</span><div><strong>Chưa có báo cáo đánh giá đầy đủ</strong><p>{reportError}</p></div></div>}
        {id && analysis?.status === "COMPLETED" && !report && !isFixtureResult(analysis.result) && <ExtractionEvidence analysis={analysis} />}
        {!id && <section className="empty-guide"><div className="guide-icon">◎</div><h2>Một URL, bằng chứng rõ nguồn</h2><p>URL 1688, Taobao và Alibaba công khai được trích xuất khi truy cập được; URL mẫu chạy báo cáo fixture minh họa. Trang bị chặn sẽ hiển thị trạng thái rõ ràng.</p><div><span>1</span>Gửi URL<i /><span>2</span>Chờ xử lý<i /><span>3</span>Xem kết quả</div></section>}
      </main>}
    </div>
  </div>;
}
