"use client";

import { SignInButton, SignUpButton, UserButton, useAuth } from "@clerk/nextjs";
import { useEffect, useState, type ReactNode } from "react";
import { type AccountState, type Analysis, type AnalysisHistoryItem, type ReportV1, type WatchlistEntry } from "@vct/contracts";
import { ApiError, addWatchlist, getAccountState, getAnalysis, getAnalysisHistory, getReport, getWatchlist, removeWatchlist } from "@vct/api-client";
import { analysisPresentation } from "./analysis-status";
import { ExtractionEvidence, isFixtureResult } from "./extraction-evidence";
import { FullReport } from "./full-report";
import { ExtensionGuide } from "./extension-guide";
import { AccountStateView } from "./account-state";
import { AnalysisHistory } from "./analysis-history";
import { WatchlistView } from "./watchlist";

type WorkspaceView = "extension" | "analysis" | "history" | "watchlist" | "account";

function Brand() {
  return <div className="brand"><span className="brand-mark">V</span><span>VCT <strong>Connect</strong></span></div>;
}

function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warning" }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

function Landing() {
  return <div className="landing">
    <nav className="landing-nav">
      <Brand />
      <div className="landing-actions">
        <SignInButton><button type="button" className="button button-ghost">Đăng nhập</button></SignInButton>
        <SignUpButton><button type="button" className="button button-dark">Tạo tài khoản</button></SignUpButton>
      </div>
    </nav>
    <main className="landing-main">
      <section className="hero-copy">
        <div className="kicker"><span className="pulse-dot" /> Trợ lý đánh giá nhà cung cấp</div>
        <h1>Ra quyết định nhập hàng với <em>bằng chứng rõ ràng.</em></h1>
        <p className="hero-text">Thu thập thông tin ngay trên trang nhà cung cấp với tiện ích VCT Connect. Đối chiếu bằng chứng và xem báo cáo rủi ro bằng tiếng Việt trong tài khoản của bạn.</p>
        <div className="hero-actions">
          <SignUpButton><button type="button" className="button button-primary button-large">Bắt đầu sử dụng <span>→</span></button></SignUpButton>
          <span className="hero-note">Không cần thẻ thanh toán</span>
        </div>
        <div className="trust-row">
          <div><strong>3 nguồn</strong><span>Sản phẩm · Cửa hàng · Nhà máy</span></div>
          <div><strong>Rõ nguồn</strong><span>Kiểm tra từng bằng chứng</span></div>
          <div><strong>Đã lưu</strong><span>Xem lại báo cáo trong tài khoản</span></div>
        </div>
      </section>
      <section className="landing-flow" aria-label="Cách sử dụng VCT Connect">
        <span className="card-label">TỪ TRANG SẢN PHẨM ĐẾN QUYẾT ĐỊNH</span>
        <h2>Hiểu nhà cung cấp trước khi đặt hàng</h2>
        <div><span>01</span><article><h3>Thu thập bằng tiện ích</h3><p>Sản phẩm, cửa hàng và hồ sơ công ty trên 1688, Alibaba hoặc Taobao.</p></article></div>
        <div><span>02</span><article><h3>Đọc bằng chứng</h3><p>Kiểm tra đánh giá, thông tin doanh nghiệp, giá và các điều khoản đã thu thập.</p></article></div>
        <div><span>03</span><article><h3>Xem báo cáo & theo dõi</h3><p>Nhận diện rủi ro, mở lại báo cáo và lưu nhà cung cấp trong tài khoản.</p></article></div>
        <p className="guide-muted">Đăng nhập để tải tiện ích và xem hướng dẫn từng bước.</p>
      </section>
    </main>
    <footer className="landing-footer"><span>Thu thập bằng chứng · Đánh giá rủi ro · Lưu báo cáo</span><span>1688 · Alibaba · Taobao</span></footer>
  </div>;
}

function Sidebar({ view, historyCount, watchlistCount, hasReport, onViewChange }: { hasReport: boolean; view: WorkspaceView; historyCount: number; watchlistCount: number; onViewChange: (view: WorkspaceView) => void }) {
  return <aside className="sidebar">
    <Brand />
    <nav className="side-nav" aria-label="Điều hướng sản phẩm">
      <button type="button" aria-label="Tiện ích & hướng dẫn" className={view === "extension" ? "active" : ""} aria-current={view === "extension" ? "page" : undefined} onClick={() => onViewChange("extension")}><span>↓</span><span className="nav-label">Tiện ích & hướng dẫn</span></button>
      {hasReport && <button type="button" aria-label="Báo cáo đang xem" className={view === "analysis" ? "active" : ""} aria-current={view === "analysis" ? "page" : undefined} onClick={() => onViewChange("analysis")}><span>◇</span><span className="nav-label">Báo cáo đang xem</span></button>}
      <button type="button" aria-label={`Lịch sử, ${historyCount} mục`} className={view === "history" ? "active" : ""} aria-current={view === "history" ? "page" : undefined} onClick={() => onViewChange("history")}><span>◷</span><span className="nav-label">Lịch sử</span><span className="nav-count">{historyCount}</span></button>
      <button type="button" aria-label={`Theo dõi, ${watchlistCount} mục`} className={view === "watchlist" ? "active" : ""} aria-current={view === "watchlist" ? "page" : undefined} onClick={() => onViewChange("watchlist")}><span>☆</span><span className="nav-label">Theo dõi</span><span className="nav-count">{watchlistCount}</span></button>
      <button type="button" aria-label="Tài khoản" className={view === "account" ? "active" : ""} aria-current={view === "account" ? "page" : undefined} onClick={() => onViewChange("account")}><span>◎</span><span className="nav-label">Tài khoản</span></button>
    </nav>
    <button type="button" className="sidebar-footer" onClick={() => onViewChange("extension")}><span>?</span><div><strong>Hướng dẫn sử dụng</strong><small>Cài đặt và thu thập nguồn</small></div></button>
  </aside>;
}

function ProgressCard({ analysis, delayed, requestedMethod, reportAvailable = false }: { analysis: Analysis | null; delayed: boolean; requestedMethod: string | null; reportAvailable?: boolean }) {
  const presentation = analysisPresentation(analysis);
  const method = analysis?.extraction_method ?? requestedMethod;
  const liveExtraction = method === "PUBLIC_HTTP" || method === "PUBLIC_BROWSER" || method === "USER_UPLOAD" || method === "EXTENSION_DOM";
  const stepClass = (step: number) => {
    if (step === 0) return "done";
    if (analysis?.status === "COMPLETED" && liveExtraction && step >= 2) return reportAvailable ? "done" : "";
    if (presentation.final) return "";
    if (presentation.progressStep > step) return "done";
    return presentation.progressStep === step ? "current" : "";
  };
  const stepSymbol = (step: number) => analysis?.status === "COMPLETED" && liveExtraction && step >= 2 && !reportAvailable ? String(step + 1) : presentation.progressStep > step || presentation.complete ? "✓" : String(step + 1);
  return <section className="progress-card" aria-live="polite">
    <div className="progress-top"><div><span className={`status-orb ${presentation.orbClass}`}>{presentation.orbSymbol}</span><div><strong>{presentation.headline}</strong><p>{presentation.detail}</p></div></div><Pill tone={presentation.pillTone}>{presentation.pillLabel}</Pill></div>
    <div className="steps report-steps" aria-label="Tiến độ phân tích">
      <div className={stepClass(0)}><span>✓</span><strong>Đã nhận URL</strong><small>Kiểm tra nguồn</small></div><i />
      <div className={stepClass(1)}><span>{stepSymbol(1)}</span><strong>{liveExtraction ? "Trích xuất" : "Chuẩn bị dữ liệu"}</strong><small>{liveExtraction ? "Đọc bằng chứng" : "Nạp dữ liệu"}</small></div><i />
      {liveExtraction ? <><div className={stepClass(2)}><span>{stepSymbol(2)}</span><strong>Đánh giá</strong><small>Risk · Confidence · Coverage</small></div><i />
      <div className={stepClass(3)}><span>{stepSymbol(3)}</span><strong>Báo cáo</strong><small>Lưu kết quả trước hoàn tất</small></div></> : <div className={presentation.complete ? "done" : ""}><span>{presentation.complete ? "✓" : "3"}</span><strong>Kết quả tracer</strong><small>Kiểm tra tổng hợp · Không chấm điểm</small></div>}
    </div>
    {presentation.nextAction && <p className="progress-next-action"><strong>Bước tiếp theo:</strong> {presentation.nextAction}</p>}
    {presentation.retrying && analysis?.next_retry_at && <p className="delay-note">Lần thử tiếp theo dự kiến lúc {new Date(analysis.next_retry_at).toLocaleTimeString("vi-VN")}.</p>}
    {delayed && !presentation.terminal && !presentation.retrying && <p className="delay-note">Quá trình đang lâu hơn dự kiến. VCT Connect sẽ tiếp tục kiểm tra; không cần gửi lại yêu cầu.</p>}
  </section>;
}

export default function Page() {
  const { getToken, isLoaded, isSignedIn, userId } = useAuth();
  const [requestedMethod, setRequestedMethod] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [report, setReport] = useState<ReportV1 | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const [id, setId] = useState<string | null>(null);
  const [reopenVersion, setReopenVersion] = useState(0);
  const [error, setError] = useState("");
  const [delayed, setDelayed] = useState(false);
  const [view, setView] = useState<WorkspaceView>("extension");
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [watchlistLoading, setWatchlistLoading] = useState(false);
  const [watchlistError, setWatchlistError] = useState("");
  const [watchlistRemovingId, setWatchlistRemovingId] = useState<string | null>(null);
  const [watchlistBusy, setWatchlistBusy] = useState(false);
  const [accountState, setAccountState] = useState<AccountState | null>(null);
  const [accountError, setAccountError] = useState("");
  const [accountLoading, setAccountLoading] = useState(false);

  useEffect(() => {
    setId(null); setAnalysis(null); setReport(null); setReportError(""); setReportLoading(false); setError(""); setDelayed(false); setView("extension");
    setAnalysisHistory([]); setHistoryLoading(false); setHistoryError("");
    setWatchlist([]); setWatchlistLoading(false); setWatchlistError(""); setWatchlistRemovingId(null); setWatchlistBusy(false);
    setAccountState(null); setAccountError(""); setAccountLoading(false);
    setRequestedMethod(null);
  }, [userId]);

  useEffect(() => {
    if (!isSignedIn || !userId || view !== "history") return;
    let active = true;
    setHistoryLoading(true);
    setHistoryError("");
    void getAnalysisHistory({ getToken }).then(
      value => { if (active) setAnalysisHistory(value); },
      cause => {
        if (!active) return;
        setAnalysisHistory([]);
        setHistoryError(cause instanceof Error ? cause.message : "Không thể tải lịch sử phân tích");
      },
    ).finally(() => { if (active) setHistoryLoading(false); });
    return () => { active = false; };
  }, [getToken, isSignedIn, userId, view]);

  useEffect(() => {
    if (!isSignedIn || !userId || view !== "watchlist") return;
    let active = true;
    setWatchlistLoading(true);
    setWatchlistError("");
    void getWatchlist({ getToken }).then(
      value => { if (active) setWatchlist(value); },
      cause => {
        if (!active) return;
        setWatchlist([]);
        setWatchlistError(cause instanceof Error ? cause.message : "Không thể tải danh sách theo dõi");
      },
    ).finally(() => { if (active) setWatchlistLoading(false); });
    return () => { active = false; };
  }, [getToken, isSignedIn, userId, view]);

  useEffect(() => {
    if (!isSignedIn || !userId || view !== "account") return;
    let active = true;
    setAccountLoading(true);
    setAccountError("");
    void getAccountState({ getToken }).then(
      value => { if (active) setAccountState(value); },
      cause => {
        if (!active) return;
        setAccountState(null);
        setAccountError(cause instanceof Error ? cause.message : "Không thể tải trạng thái tài khoản");
      },
    ).finally(() => { if (active) setAccountLoading(false); });
    return () => { active = false; };
  }, [getToken, isSignedIn, userId, view]);

  useEffect(() => {
    if (!userId) return;
    const analysisId = new URLSearchParams(window.location.search).get("analysis");
    if (!analysisId) return;
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(analysisId)) {
      setView("analysis");
      setError("Mã phân tích không hợp lệ");
      return;
    }
    setRequestedMethod(null);
    setId(analysisId);
    setView("analysis");
  }, [userId]);

  function clearAnalysisQuery() {
    const next = new URL(window.location.href);
    if (!next.searchParams.has("analysis")) return;
    next.searchParams.delete("analysis");
    next.hash = "";
    window.history.replaceState(null, "", `${next.pathname}${next.search}${next.hash}`);
  }

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
          setRequestedMethod(current.extraction_method);
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
  }, [getToken, id, isSignedIn, userId, reopenVersion]);

  useEffect(() => {
    if (!id || !isSignedIn || analysis?.status !== "COMPLETED" || analysis.id !== id) return;
    if (isFixtureResult(analysis.result)) {
      setReport(null);
      setReportLoading(false);
      setReportError("Tracer tổng hợp chỉ kiểm tra luồng xử lý; chưa có báo cáo đánh giá nhà cung cấp hoặc điểm rủi ro.");
      return;
    }
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
  }, [analysis, getToken, id, isSignedIn, userId]);

  async function saveCurrentSupplier() {
    if (!id || watchlistBusy) return;
    setWatchlistBusy(true);
    setWatchlistError("");
    try {
      await addWatchlist(id, { getToken });
      setWatchlist(await getWatchlist({ getToken }));
    } catch (cause) {
      setWatchlistError(cause instanceof Error ? cause.message : "Không thể lưu nhà cung cấp");
    } finally {
      setWatchlistBusy(false);
    }
  }

  async function deleteWatchlistEntry(entry: WatchlistEntry) {
    setWatchlistRemovingId(entry.id);
    setWatchlistError("");
    try {
      await removeWatchlist(entry.id, { getToken });
      setWatchlist(current => current.filter(item => item.id !== entry.id));
    } catch (cause) {
      setWatchlistError(cause instanceof Error ? cause.message : "Không thể xoá khỏi danh sách theo dõi");
    } finally {
      setWatchlistRemovingId(null);
    }
  }

  function openWatchlistAnalysis(entry: WatchlistEntry) {
    if (!entry.analysis_id) return;
    openHistoryAnalysis({
      id: entry.analysis_id,
      source_url: entry.source_url,
      status: entry.analysis_status ?? "COMPLETED",
      created_at: entry.created_at,
      completed_at: null,
      mode: "ACCOUNT_PUBLIC",
      extraction_method: "PUBLIC_HTTP",
      scoring_version: "v0.1.0",
      supplier_name: entry.name,
      platform: entry.platform,
      report_available: Boolean(entry.report_available),
      risk_label: entry.risk_label,
      overall_risk: entry.overall_risk,
      confidence: entry.confidence,
      coverage: entry.coverage,
    });
  }

  function openHistoryAnalysis(item: AnalysisHistoryItem) {
    const next = new URL(window.location.href);
    next.searchParams.set("analysis", item.id);
    window.history.replaceState(null, "", `${next.pathname}${next.search}${next.hash}`);
    setView("analysis");
    setId(item.id);
    setReopenVersion(version => version + 1);
    setAnalysis(null);
    setReport(null);
    setReportError("");
    setReportLoading(false);
    setError("");
    setDelayed(false);
    setRequestedMethod(item.extraction_method);
  }

  function showNewAnalysis() {
    clearAnalysisQuery();
    setView("extension");
    setId(null);
    setAnalysis(null);
    setReport(null);
    setReportError("");
    setReportLoading(false);
    setError("");
    setRequestedMethod(null);
  }

  function changeView(next: WorkspaceView) {
    if (next === "extension") showNewAnalysis();
    else setView(next);
  }

  if (!isLoaded) return <div className="loading-screen"><Brand /><span>Đang mở VCT Connect…</span></div>;
  if (!isSignedIn) return <Landing />;

  return <div className="product-shell">
    <Sidebar view={view} historyCount={analysisHistory.length} watchlistCount={watchlist.length} hasReport={Boolean(id) || view === "analysis"} onViewChange={changeView} />
    <div className="workspace">
      <header className="workspace-header"><div><span>Không gian làm việc</span><i>/</i><strong>{view === "extension" ? "Tiện ích & hướng dẫn" : view === "analysis" ? "Báo cáo" : view === "history" ? "Lịch sử" : view === "watchlist" ? "Theo dõi" : "Tài khoản"}</strong></div><nav className="mobile-nav" aria-label="Điều hướng di động">{(["extension", ...(id ? ["analysis"] : []), "history", "watchlist", "account"] as WorkspaceView[]).map(item => <button key={item} type="button" className={view === item ? "active" : ""} aria-current={view === item ? "page" : undefined} onClick={() => changeView(item)}>{{ extension: "Hướng dẫn", analysis: "Báo cáo", history: "Lịch sử", watchlist: "Theo dõi", account: "Tài khoản" }[item]}</button>)}</nav><div className="header-tools"><span className="language">VI</span><UserButton /></div></header>
      {view === "extension" ? <ExtensionGuide key={userId} getToken={getToken} onHistory={() => setView("history")} /> : view === "history" ? <AnalysisHistory items={analysisHistory} loading={historyLoading} error={historyError} onOpen={openHistoryAnalysis} onNewAnalysis={showNewAnalysis} /> : view === "watchlist" ? <WatchlistView entries={watchlist} loading={watchlistLoading} error={watchlistError} removingId={watchlistRemovingId} onOpen={openWatchlistAnalysis} onRemove={deleteWatchlistEntry} /> : view === "account" ? (accountState ? <AccountStateView state={accountState} /> : <main className="dashboard account-dashboard"><section className="account-card" aria-live="polite">{accountLoading ? <p>Đang tải trạng thái tài khoản…</p> : <p role={accountError ? "alert" : undefined}>{accountError || "Chưa có trạng thái tài khoản."}</p>}</section></main>) : <main className="dashboard" id="analysis">
        <section className="dashboard-intro"><div><Pill tone="good">THẨM ĐỊNH NHÀ CUNG CẤP</Pill><h1>Báo cáo nhà cung cấp</h1><p>Đối chiếu từng nhận định với bằng chứng đã thu thập.</p></div><button type="button" className="button button-ghost" onClick={showNewAnalysis}>+ Phân tích mới</button></section>
        {analysis?.source_url && <p className="analysis-source">Nguồn sản phẩm: <a href={analysis.source_url} target="_blank" rel="noopener noreferrer">{analysis.source_url} ↗</a></p>}
        {error && <div role="alert" className="error-banner"><span>!</span><div><strong>Không thể tiếp tục</strong><p>{error === "Analysis not found" ? "Không tìm thấy phân tích. Vui lòng tạo phân tích mới." : error}</p></div></div>}
        {id && <ProgressCard analysis={analysis} delayed={delayed} requestedMethod={requestedMethod} reportAvailable={Boolean(report)} />}
        {id && analysis?.status === "COMPLETED" && reportLoading &&
          <section className="report-loading" aria-live="polite"><i className="spinner" /><span>Đang tải báo cáo đánh giá đã lưu…</span></section>}
        {id && analysis?.status === "COMPLETED" && report && <><div className="report-watchlist-action"><button type="button" className="button button-ghost" disabled={watchlistBusy} onClick={() => { void saveCurrentSupplier(); }}>{watchlistBusy ? "Đang lưu…" : "☆ Theo dõi nhà cung cấp"}</button>{watchlistError && <span role="alert">{watchlistError}</span>}</div><FullReport key={report.analysis_id} report={report} extractionMethod={analysis.extraction_method} /></>}
        {id && analysis?.status === "COMPLETED" && !reportLoading && !report && reportError &&
          <div className="report-unavailable" role="status"><span>i</span><div><strong>Chưa có báo cáo đánh giá đầy đủ</strong><p>{reportError}</p></div></div>}
        {id && analysis?.status === "COMPLETED" && !report && !isFixtureResult(analysis.result) && <ExtractionEvidence analysis={analysis} />}
        {!id && <section className="empty-guide"><div className="guide-icon">◎</div><h2>Thu thập đủ bằng chứng trước khi đặt hàng</h2><p>VCT Connect tổng hợp thông tin nguồn và chỉ chấm điểm những hạng mục có bằng chứng. Bạn có thể mở lại báo cáo và kiểm tra từng trích dẫn.</p><div><span>1</span>Thu thập nguồn<i /><span>2</span>Đánh giá bằng chứng<i /><span>3</span>Xem báo cáo</div></section>}
      </main>}
    </div>
  </div>;
}
