from typing import Annotated, Literal
import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field

PROMPT_VERSION = "vi-text.v1"
SCHEMA_VERSION = "text-report.v1"
PIPELINE_VERSION = "saved-evidence.v1"
Text = Annotated[str, Field(min_length=1, max_length=1600)]
Reference = Annotated[str, Field(pattern=r"^E[0-9]{1,3}$")]


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["observation", "inference"]
    text: Text
    citations: Annotated[list[Reference], Field(min_length=1, max_length=10)]


class VietnameseReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: Text
    findings: Annotated[list[Finding], Field(min_length=1, max_length=12)]
    limitations: Annotated[list[Text], Field(min_length=1, max_length=12)]
    actions: Annotated[list[Text], Field(min_length=1, max_length=12)]


def screen_vietnamese(text: str) -> bool:
    """Conservative local prose screen, not language identification or factual QA.

    Require Vietnamese cues in each sentence; quoted source names/text and code
    identifiers may remain in their original language. Ambiguous prose fails closed.
    """
    text = unicodedata.normalize("NFC", text).casefold()
    text = re.sub(r'"[^"\n]*"|“[^”\n]*”|`[^`\n]*`', "", text)
    words_vi = set("nguồn có thông tin cần kiểm tra xác minh trước đặt hàng trang hiển thị sản phẩm "
                   "chưa độc lập yêu cầu mẫu cọc dữ liệu thiếu không đủ bằng chứng nhà cung cấp "
                   "giới hạn nhận định quan sát suy luận về và của từ được đã này cho thấy là một "
                   "với theo nhưng chỉ khi nên để số lượng giá đơn tối thiểu giao vận chuyển "
                   "đánh tích cực tỷ lệ điểm cửa chất mức rủi ro độ cậy hệ thống tính khoảng "
                   "thời gian ngày tháng năm hoạt động doanh nghiệp chứng nhận mua bán người "
                   "vẫn còn phải đối chiếu bao gồm kết quả bảo đảm cam chất lượng uy tín".split())
    # Common product descriptions and purchasing terms must not be mistaken for
    # foreign prose merely because they are outside the initial small lexicon.
    words_vi.update("liệt kê váy dài tay cổ liệu dệt kim phong cách thanh lịch nữ mùa thu đông "
                    "trích xuất ở trạng thái nhiều trường bị rõ thập chính sách đổi trả bảo hành "
                    "hoặc xử lý khiếu nại báo thức phí thuế nền tảng điều kiện thanh toán thống nhất "
                    "khoản hoàn tiền tranh chấp văn bản kích thước màu sắc thử nghiệm phù hợp "
                    "chi thực tế năng lực sản xuất kiểm soát khả đáp ứng bất kỳ tổng hợp".split())
    foreign_words = {"the", "this", "that", "is", "are", "and", "with", "should", "supplier", "reliable", "before", "order"}
    sentences = re.split(r"[!?;\n]+|(?<!\d)\.|\.(?!\d)", text)
    checked = False
    for sentence in sentences:
        words = re.findall(r"[^\W\d_]+", sentence, re.UNICODE)
        if not words:
            continue
        checked = True
        if (re.search(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", sentence)
                or sum(word in foreign_words for word in words) >= 2
                or sum(word in words_vi for word in words) < max(2, len(words) / 2)
                or not re.search(r"[ăâđêôơưà-ỹ]", sentence)):
            return False
    return checked


def validate_report(content: str, evidence: list[dict]) -> dict:
    report = VietnameseReport.model_validate_json(content)
    references = {entry["id"] for entry in evidence}
    if any(ref not in references for finding in report.findings for ref in finding.citations):
        raise ValueError("UNKNOWN_CITATION")
    prose = [report.summary, *(finding.text for finding in report.findings), *report.limitations, *report.actions]
    for text in prose:
        normalized = unicodedata.normalize("NFC", text)
        if re.search(r"(?:(?:điểm|chỉ số|mức)\s+(?:rủi ro|tin cậy)|độ tin cậy|risk score|confidence score)"
                     r"[^.!?;\n]{0,120}?(?:\d|\b(?:một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|trăm)\b)",
                     normalized, re.IGNORECASE):
            raise ValueError("UNSUPPORTED_SCORE")
        if not screen_vietnamese(normalized):
            raise ValueError("NON_VIETNAMESE_PROSE")
    return report.model_dump()
