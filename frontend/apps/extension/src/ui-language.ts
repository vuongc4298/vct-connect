export type UiLanguage = "vi" | "en";

const vi: Record<string, string> = {
  "Source evidence": "Thu thập bằng chứng",
  "Analyze this page": "Phân tích trang này",
  "Save shop HTML": "Lưu HTML cửa hàng",
  "Save factory HTML & analyze": "Lưu HTML nhà máy và phân tích",
  "Retry saved upload": "Gửi lại dữ liệu đã lưu",
  "Working…": "Đang xử lý…",
  "Supported page": "Trang được hỗ trợ",
  "Product": "Sản phẩm", "Shop": "Cửa hàng", "Factory": "Nhà máy",
  "Capture product, shop and factory evidence for one supplier report.": "Thu thập thông tin sản phẩm, cửa hàng và nhà máy để tạo báo cáo nhà cung cấp.",
  "Open a supported product, shop or linked factory page.": "Mở trang sản phẩm, cửa hàng hoặc hồ sơ nhà máy được liên kết.",
  "Checking the active page…": "Đang kiểm tra trang hiện tại…",
  "Checking your VCT Connect session…": "Đang kiểm tra phiên đăng nhập…",
  "Sign-in is taking longer than expected. Sign in on the web, then reopen this popup.": "Đăng nhập đang chậm. Hãy đăng nhập trên trang VCT Connect rồi mở lại tiện ích.",
  "Open VCT Connect": "Mở VCT Connect",
  "Sign in on VCT Connect": "Đăng nhập VCT Connect",
  "Sign in on the web, then reopen this extension in the same browser profile.": "Đăng nhập trên trang VCT Connect, rồi mở lại tiện ích trong cùng hồ sơ trình duyệt.",
  "This page cannot be captured. Open a supported source.": "Chưa hỗ trợ thu thập trang này. Hãy mở trang nguồn được hỗ trợ.",
  "Capture the product first. Then follow the supplier cue to save shop and factory HTML. Finish within 30 minutes.": "Thu thập sản phẩm trước, rồi làm theo hướng dẫn để lưu HTML cửa hàng và nhà máy. Hoàn tất trong 30 phút.",
  "Start from a product and follow its linked supplier page.": "Bắt đầu từ sản phẩm, rồi mở trang nhà cung cấp được liên kết.",
  "Capture saved · retry upload": "Đã lưu dữ liệu · cần gửi lại",
  "Shop saved · factory next": "Đã lưu cửa hàng · tiếp theo là nhà máy",
  "Product captured · shop next": "Đã thu thập sản phẩm · tiếp theo là cửa hàng",
  "Retry the stored upload. Your evidence and analysis ID are retained.": "Gửi lại dữ liệu đã lưu. Bằng chứng và mã phân tích được giữ nguyên.",
  "Open the supplier shop using the link below or the highlighted name. If an overlay covers visible company content, close it with X, then save shop HTML.": "Mở cửa hàng qua liên kết bên dưới hoặc tên nhà cung cấp được đánh dấu. Nếu cửa sổ CAPTCHA che thông tin công ty đã hiển thị, đóng bằng nút X rồi lưu HTML cửa hàng.",
  "Open Factory profile / 工厂档案 from the shop. When factory details are visible, save factory HTML to complete the report.": "Mở Hồ sơ nhà máy / Factory profile / 工厂档案 từ cửa hàng. Khi thông tin nhà máy hiển thị, lưu HTML nhà máy để hoàn tất báo cáo.",
  "Open linked factory profile": "Mở hồ sơ nhà máy",
  "Open linked company page": "Mở cửa hàng nhà cung cấp",
  "Finish with captured product & shop": "Phân tích với sản phẩm và cửa hàng đã lưu",
  "Finish with product evidence only": "Chỉ phân tích dữ liệu sản phẩm",
  "One analysis. HTML is downloaded at each capture and uploaded together when you finish. Only visible content is collected.": "Một lượt phân tích. HTML được tải xuống ở mỗi bước và gửi cùng nhau khi hoàn tất. Chỉ thu thập nội dung đang hiển thị.",
  "Collection interrupted": "Thu thập bị gián đoạn",
  "Reading product": "Đang đọc sản phẩm", "Reading supplier shop": "Đang đọc cửa hàng",
  "Reading factory profile": "Đang đọc hồ sơ nhà máy",
  "Capture finished · assessment continues": "Đã thu thập xong · đang đánh giá",
  "Collection deadline reached": "Đã hết thời gian thu thập",
  "You can close this popup. Open the web result to follow assessment and reporting.": "Bạn có thể đóng tiện ích. Mở báo cáo trên VCT Connect để theo dõi tiến độ.",
  "Loading saved assessment report…": "Đang tải báo cáo đã lưu…",
  "Supplier name missing": "Chưa có tên nhà cung cấp",
  "Extraction coverage": "Độ phủ trích xuất", "Risk": "Rủi ro", "Confidence": "Độ tin cậy", "Coverage": "Độ phủ",
  "No scored report available. Missing evidence is not low risk.": "Chưa có báo cáo chấm điểm. Thiếu bằng chứng không có nghĩa là rủi ro thấp.",
  "Last page": "Trang đã thu thập", "Reload last result": "Tải lại kết quả", "Open web result": "Mở báo cáo",
  "Use the same VCT Connect account to view this report.": "Dùng cùng tài khoản VCT Connect để xem báo cáo.",
  "Loading analysis": "Đang tải phân tích", "Retrieving the latest saved state.": "Đang lấy trạng thái đã lưu mới nhất.",
  "Queued for analysis": "Đang chờ phân tích", "Extracting source evidence": "Đang trích xuất bằng chứng",
  "Assessing evidence": "Đang đánh giá bằng chứng", "Preparing report": "Đang tạo báo cáo", "Retry scheduled": "Đã lên lịch thử lại",
  "Analysis failed": "Phân tích chưa hoàn tất", "Analysis completed": "Đã hoàn tất phân tích",
  "Source evidence unavailable": "Chưa có bằng chứng nguồn",
  "The system will retry; do not submit again.": "Hệ thống sẽ tự thử lại; không cần gửi lại yêu cầu.",
  "Saved extraction result available. A full assessment report is not available.": "Đã lưu kết quả trích xuất. Chưa có báo cáo đánh giá đầy đủ.",
  "The report will update when processing reaches the next stage.": "Báo cáo sẽ cập nhật khi chuyển sang bước tiếp theo.",
  "Insufficient information": "Chưa đủ thông tin", "Low": "Thấp", "Moderate": "Trung bình", "High": "Cao",
  "Technical details": "Chi tiết kỹ thuật",
};

export function uiText(text: string, language: UiLanguage): string {
  if (language === "en") return text;
  if (vi[text]) return vi[text];
  if (text.startsWith("Processing stopped (")) return text.replace("Processing stopped", "Đã dừng xử lý");
  if (text.startsWith("Extraction:")) return text.replace("Extraction:", "Trạng thái trích xuất:");
  return text;
}

export function errorText(text: string, language: UiLanguage): string {
  if (language === "en") return text;
  if (/supplier shop link is not ready/.test(text)) return "Chưa xác định được liên kết cửa hàng. Chờ phần thông tin nhà cung cấp tải xong rồi thử lại. Chưa gửi lượt phân tích.";
  if (/Factory company evidence|No usable factory HTML/.test(text)) return "Chưa đọc được thông tin nhà máy hoặc hồ sơ không khớp nhà cung cấp. Đóng cửa sổ che nội dung nếu có, rồi thử lưu lại.";
  if (/supplier header|No usable shop HTML/.test(text)) return "Chưa đọc được thông tin cửa hàng. Cuộn đến tên nhà cung cấp hoặc phần giới thiệu công ty rồi thử lưu lại.";
  if (/Account changed|Sign in|same VCT Connect account/.test(text)) return "Hãy đăng nhập lại bằng cùng tài khoản VCT Connect.";
  if (/Reservation response lost|reservation may have been saved/.test(text)) return "Phản hồi bị gián đoạn. Thử lại cùng sản phẩm để dùng lại lượt phân tích đã lưu.";
  if (/timed out|Timeout|Failed to fetch|NetworkError/.test(text)) return "Kết nối bị gián đoạn hoặc hết thời gian chờ. Kiểm tra mạng rồi thử lại.";
  if (/waiting for company evidence/.test(text)) return "Sản phẩm đang chờ thông tin công ty. Tiếp tục lưu cửa hàng, nhà máy hoặc hoàn tất với bằng chứng đã có.";
  if (/422|captured evidence was rejected/.test(text)) return "Dữ liệu chưa được chấp nhận. Tải lại tiện ích rồi thu thập lại sản phẩm.";
  if (/download did not start|browser download/.test(text)) return "Đã giữ HTML để gửi lên hệ thống, nhưng trình duyệt chưa tải được tệp xuống. Bạn có thể thử lưu lại.";
  return "Không thể hoàn tất thao tác. Xem chi tiết bên dưới hoặc thử lại.";
}
