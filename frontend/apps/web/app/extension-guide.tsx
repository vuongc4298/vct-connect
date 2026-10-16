"use client";

import type { useAuth } from "@clerk/nextjs";
import React, { useEffect, useRef, useState } from "react";

const captureSteps = {
  "1688": [
    ["Mở sản phẩm", "Trên trang sản phẩm, mở tiện ích và chọn Phân tích trang này. Cho phép tiện ích truy cập 1688 khi trình duyệt hỏi. Hiển thị các đánh giá cần thu thập trước khi phân tích."],
    ["Lưu cửa hàng", "Theo tên nhà cung cấp được đánh dấu hoặc liên kết trong tiện ích. Khi thông tin cửa hàng hiển thị, chọn Lưu HTML cửa hàng."],
    ["Lưu hồ sơ nhà máy", "Mở Factory profile / 工厂档案 và chọn Lưu HTML nhà máy và phân tích. Nếu không có hồ sơ, chọn Phân tích với sản phẩm và cửa hàng đã lưu; nếu thiếu cả cửa hàng, chọn Chỉ phân tích dữ liệu sản phẩm."],
    ["Xem kết quả", "Mở báo cáo từ tiện ích. HTML của từng nguồn được tải về máy và gửi cho VCT Connect khi bạn hoàn tất."],
  ],
  "Alibaba": [
    ["Mở sản phẩm", "Mở tiện ích trên trang sản phẩm Alibaba và chọn Phân tích trang này. Cho phép tiện ích truy cập Alibaba khi trình duyệt hỏi."],
    ["Lưu trang nhà cung cấp", "Theo tên hoặc liên kết nhà cung cấp được đánh dấu. Chọn lưu HTML cửa hàng khi thông tin đã hiển thị."],
    ["Lưu Company overview", "Mở Company overview, chọn Lưu HTML hồ sơ công ty và phân tích. Nếu không có hồ sơ, chọn Phân tích với sản phẩm và cửa hàng đã lưu; nếu thiếu cả cửa hàng, chọn Chỉ phân tích dữ liệu sản phẩm."],
    ["Đọc báo cáo", "Mở kết quả từ tiện ích để kiểm tra thông tin doanh nghiệp, năng lực sản xuất và các bằng chứng nguồn."],
  ],
} as const;
type Platform = keyof typeof captureSteps;

export function ExtensionGuide({ onHistory, getToken }: { onHistory: () => void; getToken: ReturnType<typeof useAuth>["getToken"] }) {
  const [platform, setPlatform] = useState<Platform>("1688");
  const [downloading, setDownloading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);
  const deadline = useRef<ReturnType<typeof setTimeout> | null>(null);
  const downloads = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  useEffect(() => () => {
    request.current?.abort(); request.current = null;
    if (deadline.current) clearTimeout(deadline.current);
    for (const [url, timer] of downloads.current) { clearTimeout(timer); URL.revokeObjectURL(url); }
    downloads.current.clear();
  }, []);

  async function download() {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setDownloading(true); setMessage(""); setError("");
    const timer = setTimeout(() => {
      if (request.current !== controller) return;
      controller.abort(); request.current = null;
      setDownloading(false);
      setError("Tải tiện ích mất quá lâu. Vui lòng kiểm tra kết nối và thử lại.");
    }, 45_000);
    deadline.current = timer;
    try {
      const token = await getToken({ skipCache: true });
      if (controller.signal.aborted) return;
      if (!token) throw new Error("SESSION");
      const response = await fetch("/api/v1/extension-download", {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store", signal: controller.signal,
      });
      if (response.status === 401 || response.status === 403) throw new Error("SESSION");
      if (!response.ok || !response.headers.get("content-type")?.startsWith("application/zip")) throw new Error("DOWNLOAD");
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      try {
        link.href = url; link.download = "vct-connect-extension.zip";
        document.body.appendChild(link); link.click();
      } finally {
        link.remove();
        // Chromium must resolve the Blob after the click before it can be revoked.
        downloads.current.set(url, setTimeout(() => {
          URL.revokeObjectURL(url); downloads.current.delete(url);
        }, 30_000));
      }
      setMessage("Đã bắt đầu tải. Giải nén tệp ZIP, rồi làm theo hướng dẫn cài đặt bên dưới.");
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error && cause.message === "SESSION"
        ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại rồi tải tiện ích."
        : "Chưa thể tải tiện ích. Vui lòng kiểm tra kết nối và thử lại.");
    } finally {
      clearTimeout(timer);
      if (request.current === controller) { request.current = null; setDownloading(false); }
    }
  }

  return <main className="dashboard extension-guide" id="extension-guide">
    <section className="guide-hero">
      <div><span className="pill pill-good">TIỆN ÍCH VCT CONNECT</span><h1>Thu thập ngay trên trang nhà cung cấp</h1><p>Từ sản phẩm đến hồ sơ công ty, lưu bằng chứng bạn đang xem để tạo báo cáo thẩm định bằng tiếng Việt.</p><div className="guide-download-actions"><button type="button" className="button button-primary button-large" disabled={downloading} onClick={() => { void download(); }}>{downloading ? "Đang tải…" : "↓ Tải tiện ích"}</button><span>Chrome & Brave trên máy tính · Tệp ZIP</span></div><div aria-live="polite">{message && <p className="guide-success" role="status">{message}</p>}{error && <p className="guide-download-error" role="alert">{error}</p>}</div></div>
      <div className="guide-flow" aria-label="Luồng sử dụng"><span>01 <strong>Cài tiện ích</strong></span><i>↓</i><span>02 <strong>Thu thập nguồn</strong></span><i>↓</i><span>03 <strong>Đọc báo cáo</strong></span></div>
    </section>
    <section className="guide-card" aria-labelledby="guide-install">
      <div className="guide-section-heading"><span className="guide-section-number">01</span><div><span className="card-label">CÀI ĐẶT MỘT LẦN</span><h2 id="guide-install">Thêm tiện ích vào trình duyệt</h2></div></div>
      <ol className="guide-step-list">
        <li><strong>Giải nén tệp vừa tải</strong><p>Giữ thư mục cài đặt ở một vị trí cố định. Khi cập nhật, thay nội dung thư mục bằng bản mới rồi nhấn Reload / Tải lại trên trang quản lý tiện ích.</p></li>
        <li><strong>Mở trang quản lý tiện ích</strong><p>Nhập <code>chrome://extensions</code> trên Chrome hoặc <code>brave://extensions</code> trên Brave vào thanh địa chỉ.</p></li>
        <li><strong>Bật Chế độ dành cho nhà phát triển</strong><p>Bật Developer mode, chọn Load unpacked / Tải tiện ích đã giải nén, rồi chọn thư mục chứa <code>manifest.json</code>.</p></li>
        <li><strong>Ghim VCT Connect</strong><p>Mở biểu tượng tiện ích hình mảnh ghép trên thanh công cụ và ghim VCT Connect để dễ mở khi xem sản phẩm.</p></li>
        <li><strong>Đăng nhập cùng tài khoản</strong><p>Mở VCT Connect và tiện ích trong cùng trình duyệt, cùng hồ sơ người dùng. Dùng cùng tài khoản để báo cáo xuất hiện trong Lịch sử.</p></li>
      </ol>
    </section>
    <section className="guide-card" aria-labelledby="guide-capture">
      <div className="guide-section-heading"><span className="guide-section-number">02</span><div><span className="card-label">BẮT ĐẦU PHÂN TÍCH</span><h2 id="guide-capture">Thu thập theo từng nền tảng</h2></div></div>
      <div className="guide-platforms" role="group" aria-label="Chọn nền tảng">{(Object.keys(captureSteps) as Platform[]).map(item => <button key={item} type="button" aria-pressed={platform === item} className={platform === item ? "active" : ""} onClick={() => setPlatform(item)}>{item}</button>)}</div>
      <ol className="guide-step-list" aria-label={`Các bước thu thập ${platform}`}>{captureSteps[platform].map(([title, body]) => <li key={title}><strong>{title}</strong><p>{body}</p></li>)}</ol>
      <aside className="guide-note"><strong>Khi trang có CAPTCHA</strong><p>Nếu thông tin đã hiển thị, bạn có thể đóng lớp CAPTCHA bằng X rồi lưu HTML. Nếu nội dung vẫn bị che hoặc chưa tải, hoàn tất với bằng chứng hiện có hoặc thử lại sau. Hoàn tất một lượt thu thập trong 30 phút.</p></aside>
      <p className="guide-muted">Nếu gửi dữ liệu bị gián đoạn, mở lại tiện ích và chọn Gửi lại dữ liệu đã lưu để giữ nguyên bằng chứng và mã phân tích. Nếu đã từ chối quyền truy cập trang, nhấn Phân tích trang này để cấp quyền và thử lại.</p>
    </section>
    <section className="guide-report-card"><span className="guide-section-number">03</span><div><h2>Đọc kết quả và kiểm tra nguồn</h2><p>Mở báo cáo từ tiện ích hoặc xem lại trong Lịch sử. Điểm rủi ro dựa trên bằng chứng đã thu thập; hạng mục thiếu dữ liệu sẽ được ghi rõ. Bạn có thể lưu nhà cung cấp vào Theo dõi từ báo cáo.</p></div><button type="button" className="button button-ghost" onClick={onHistory}>Mở lịch sử →</button></section>
  </main>;
}
