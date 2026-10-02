import React from "react";
import type { Analysis, FixtureResult } from "@vct/contracts";
import { extractionRecovery } from "./analysis-status";
import { safeSourceUrl, sourceLabel } from "./source-url";

const companyLabels: Record<string, string> = {
  company_name: "Tên công ty", business_type: "Loại hình doanh nghiệp",
  register_country: "Quốc gia đăng ký", markets_display_text: "Thị trường được nguồn công bố",
};

export function isFixtureResult(result: Analysis["result"]): result is FixtureResult {
  return result !== null && "fixture" in result && result.fixture === true;
}

export function ExtractionEvidence({ analysis }: { analysis: Analysis }) {
  const data = analysis.supplier_data;
  const result = analysis.result;
  if (!result || isFixtureResult(result)) return null;
  const uploaded = (data?.extraction_method ?? analysis.extraction_method) === "USER_UPLOAD";
  const browser = (data?.extraction_method ?? analysis.extraction_method) === "EXTENSION_DOM";
  const publicBrowser = (data?.extraction_method ?? analysis.extraction_method) === "PUBLIC_BROWSER";
  const merged = analysis.raw_evidence && "merged_from_snapshot_id" in analysis.raw_evidence;
  const previousCapturedAt = analysis.raw_evidence && "merged_from_extracted_at" in analysis.raw_evidence
    ? analysis.raw_evidence.merged_from_extracted_at : null;
  const omittedReviews = analysis.raw_evidence && "omitted_review_count" in analysis.raw_evidence
    ? analysis.raw_evidence.omitted_review_count : 0;
  const omittedProducts = analysis.raw_evidence && "omitted_product_count" in analysis.raw_evidence
    ? analysis.raw_evidence.omitted_product_count : 0;
  const recovery = extractionRecovery(result.extraction_status, result.reason, result.source_url);
  const sourceUrl = safeSourceUrl(data?.source_url ?? result.source_url);
  const source = sourceLabel(result.source_url);
  return <section className="progress-card" aria-label={`Bằng chứng trích xuất ${source}`}>
    <h2>Bằng chứng {source}</h2>
    <p>Trạng thái trích xuất: <strong>{result.extraction_status}</strong>{result.reason ? ` · ${result.reason}` : ""}</p>
    {data ? <>
      <p><strong>{data.supplier_name ?? "Chưa có tên nhà cung cấp"}</strong> · {data.products?.[0]?.title ?? "Chưa có tên sản phẩm"}</p>
      {data.price_information?.display_text && <p>Giá hiển thị trên trang: {data.price_information.display_text}</p>}
      {source === "Alibaba" && <>
        <p>Các thông tin dưới đây là tuyên bố trên trang nguồn; chưa được xác minh độc lập.</p>
        {data.company_information && <ul>{Object.entries(data.company_information).map(([label, value]) => <li key={label}>{companyLabels[label] ?? label}: {value}</li>)}</ul>}
        {data.years_active !== null && <p>Thời gian tham gia Alibaba: {data.years_active} năm; chưa xác minh tuổi pháp nhân.</p>}
        {data.categories && <p>Danh mục: {data.categories.join(" · ")}</p>}
        {data.certifications && <p>Chứng nhận / báo cáo kiểm tra được nguồn công bố: {data.certifications.join(" · ")}</p>}
        {data.rating !== null && <p>Điểm đánh giá nhà cung cấp trên nguồn: {data.rating}/5</p>}
        {data.price_information?.currency && <p>Giá chào sản phẩm: {data.price_information.minimum ?? "chưa có"}–{data.price_information.maximum ?? "chưa có"} {data.price_information.currency} / {data.price_information.unit ?? "chưa có đơn vị"} · MOQ: {data.price_information.minimum_order_quantity ?? "chưa có"}</p>}
        {[...(data.transaction_signals?.source_metrics ?? []), ...(data.delivery_information?.source_metrics ?? [])].map((metric, index) => <p key={index}>{metric.label}: {metric.value} · Phạm vi: {metric.scope}{metric.description ? ` · ${metric.description}` : ""}</p>)}
        {data.delivery_information?.lead_times?.map((lead, index) => <p key={index}>Thời gian chuẩn bị sản phẩm: {lead.minQuantity}–{lead.maxQuantity} đơn vị → {lead.processPeriod} ngày</p>)}
        {data.products && <ul>{data.products.map((product, index) => {
          const productUrl = safeSourceUrl(product.source_url);
          const bound = productUrl?.match(/_([1-9][0-9]{0,19})\.html$/)?.[1] === product.offer_id && productUrl?.startsWith("https://www.alibaba.com/product-detail/");
          return <li key={index}>{bound ? <a href={productUrl!} target="_blank" rel="noreferrer">{product.title ?? product.offer_id}</a> : product.title ?? product.offer_id}
            {product.price_display_text && <span> · Giá: {product.price_display_text}</span>}{product.minimum_order_display_text && <span> · {product.minimum_order_display_text}</span>}
            {product.attributes && <ul>{product.attributes.map((attribute, i) => <li key={i}>{attribute.name}: {attribute.value}</li>)}</ul>}
          </li>;
        })}</ul>}
      </>}
      {source === "Taobao" && <>
        {[data.price_information?.price, data.price_information?.extraPrice].filter(Boolean).map((price, index) => <p key={index}>{price?.priceTitle ?? "Giá hiển thị"}: {price?.priceUnit}{price?.priceText} {price?.priceDesc}</p>)}
        {data.price_information?.starting_price_text && <p>Giá khởi điểm hiển thị: {data.price_information.starting_price_text}</p>}
        {data.transaction_signals?.sales_display_text && <p>Lượt bán hiển thị: {data.transaction_signals.sales_display_text}</p>}
        {data.transaction_signals?.positive_review_rate_display_text && <p>{data.transaction_signals.positive_review_rate_display_text}</p>}
        {data.transaction_signals?.shop_metrics_display_text && <p>Chỉ số cửa hàng: {data.transaction_signals.shop_metrics_display_text.join(" · ")}</p>}
        {data.transaction_signals?.shop_evaluations?.map((metric, index) => <p key={index}>Chỉ số cửa hàng — {metric.title}: {metric.score} ({metric.levelText})</p>)}
        {data.years_active !== null && <p>Tuổi cửa hàng hiển thị: {data.years_active} năm; chưa xác minh tuổi pháp nhân.</p>}
        {data.offer_id === null && data.products && <>
          <p>Sản phẩm hiển thị trong cửa hàng ({data.products.length}):</p>
          <ul>{data.products.map((product, index) => {
            const productUrl = safeSourceUrl(product.source_url);
            const safeProductUrl = productUrl?.startsWith("https://item.taobao.com/item.htm?id=")
              && productUrl === `https://item.taobao.com/item.htm?id=${product.offer_id}` ? productUrl : null;
            const title = product.title ?? `Sản phẩm ${product.offer_id ?? "chưa có mã"}`;
            return <li key={index}>{safeProductUrl ? <a href={safeProductUrl} target="_blank" rel="noreferrer">{title}</a> : title}</li>;
          })}</ul>
        </>}
      </>}
      <p>Độ phủ: {Math.round(data.completeness * 100)}% ({data.completeness_denominator.length - data.missing_fields.length}/{data.completeness_denominator.length} trường) · Thiếu: {data.missing_fields.length ? data.missing_fields.join(", ") : "không"}</p>
      <p>Nguồn: {data.platform} · {publicBrowser ? "Trang công khai được hệ thống kết xuất bằng trình duyệt" : browser ? merged ? "Bằng chứng trình duyệt do bạn cung cấp, kết hợp với ảnh chụp trước đó của bạn" : "Bằng chứng trình duyệt do bạn cung cấp" : uploaded ? "Trang HTML do bạn tải lên" : "Trang công khai"} · {data.extraction_method} · {data.analysis_mode} · {data.extractor_version} · {uploaded ? "Nhập lúc" : "Trích xuất lúc"} {new Date(data.extracted_at).toLocaleString("vi-VN")}</p>
      {previousCapturedAt && <p>Một phần dữ liệu được lấy từ ảnh chụp trước đó lúc {new Date(previousCapturedAt).toLocaleString("vi-VN")}.</p>}
      {(omittedReviews || omittedProducts) ? <p>Giới hạn dữ liệu kết hợp: bỏ qua {omittedReviews} đánh giá và {omittedProducts} sản phẩm cũ; ảnh chụp gốc vẫn được lưu.</p> : null}
      {uploaded && <p>Thời điểm lưu trang gốc: chưa xác định.</p>}
      <p>Đánh giá hiển thị: {data.transaction_signals?.review_count_display_text ?? data.transaction_signals?.review_count ?? "chưa có"} · Nội dung đánh giá truy cập được: {analysis.reviews.length}</p>
      {analysis.reviews.length > 0 && <ul>{analysis.reviews.map((review, index) => <li key={index}>{String(review.text ?? "")}</li>)}</ul>}
      <p>Thiếu dữ liệu là chưa xác định, không phải tín hiệu an toàn. Chưa có điểm rủi ro cho dữ liệu này.</p>
      {sourceUrl && <a href={sourceUrl} target="_blank" rel="noreferrer">Mở trang nguồn {source}</a>}
    </> : <>
      <p>{browser ? "Trang đang mở không có tên nhà cung cấp hoặc tên sản phẩm trong các trường được chọn." : uploaded ? "Trang đã tải lên không cung cấp bằng chứng có thể xác minh." : "Không có bằng chứng có thể xác minh từ trang nguồn."} Chưa có điểm rủi ro.</p>
      {recovery && <p>{recovery}</p>}
      {sourceUrl && <a href={sourceUrl} target="_blank" rel="noreferrer">Mở trang nguồn {source}</a>}
    </>}
  </section>;
}
