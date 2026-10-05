from typing import Annotated, Literal
import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, ValidationError

PROMPT_VERSION = "vi-text.v6"
SCHEMA_VERSION = "text-report.v2"
PIPELINE_VERSION = "saved-evidence.v1"
VALIDATION_VERSION = "vi-prose.v3"
Text = Annotated[str, Field(min_length=1, max_length=1600)]
Reference = Annotated[str, Field(pattern=r"^E[0-9]{1,3}$")]


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["observation", "inference"]
    text: Text
    citations: Annotated[list[Reference], Field(min_length=1, max_length=10)]


class SelfReportedConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    score: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    basis: Text


class ReportValidationError(ValueError):
    """Only fixed categories/locations may cross the settlement boundary."""
    REASONS = frozenset({"SCHEMA_INVALID", "UNKNOWN_CITATION", "UNSUPPORTED_SCORE",
                         "NON_VIETNAMESE_PROSE", "CREDENTIAL_ECHO"})
    LOCATIONS = frozenset({"report", "summary", "findings", "findings.kind", "findings.text",
                           "findings.citations", "limitations", "actions", "self_reported_confidence",
                           "self_reported_confidence.score", "self_reported_confidence.basis"})

    def __init__(self, reason, location="report"):
        self.reason = reason if reason in self.REASONS else "SCHEMA_INVALID"
        self.location = location if location in self.LOCATIONS else "report"
        super().__init__(self.reason)


def schema_location(loc):
    # Never join arbitrary provider keys into metadata. Indices are omitted.
    if not loc:
        return "report"
    if loc[0] in {"summary", "limitations", "actions"}:
        return loc[0]
    if loc[0] == "findings":
        if len(loc) > 2 and loc[2] in {"kind", "text", "citations"}:
            return "findings." + loc[2]
        return "findings"
    if loc[0] == "self_reported_confidence":
        if len(loc) > 1 and loc[1] in {"score", "basis"}:
            return "self_reported_confidence." + loc[1]
        return "self_reported_confidence"
    return "report"


class VietnameseReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: Text
    findings: Annotated[list[Finding], Field(min_length=1, max_length=12)]
    limitations: Annotated[list[Text], Field(min_length=1, max_length=12)]
    actions: Annotated[list[Text], Field(min_length=1, max_length=12)]
    self_reported_confidence: SelfReportedConfidence


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
    words_vi.update("tôi khá chắc chắn cách diễn giải vì nội dung nhất quán tự báo cáo hiệu chuẩn".split())
    # Evidence-supported product vocabulary; sentence thresholds and script guards stay intact.
    words_vi.update("tiêu đề khăn giấy ăn dạng rút lớp tờ đặc mềm mại da nhạy cảm trẻ em tham khảo nhân dân tệ miễn".split())
    # Retained diagnostic confirmed these ordinary shipping/service words were missing.
    words_vi.update("gửi trung bình giờ phản hồi khách giây do bố".split())
    # Broader offline corpus exposed packaging descriptions outside the initial vocabulary.
    words_vi.update("bề mặt bì trơn nhẵn sờ".split())
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


def _source_strings(value):
    if isinstance(value, str) and value:
        yield unicodedata.normalize("NFC", value).casefold()
    elif isinstance(value, dict):
        for item in value.values():
            yield from _source_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _source_strings(item)


def validate_report(content: str, evidence: list[dict]) -> dict:
    try:
        report = VietnameseReport.model_validate_json(content)
    except ValidationError as error:
        location = schema_location(error.errors(include_input=False, include_context=False, include_url=False)[0]["loc"])
        raise ReportValidationError("SCHEMA_INVALID", location) from None
    references = {entry["id"] for entry in evidence}
    if any(ref not in references for finding in report.findings for ref in finding.citations):
        raise ReportValidationError("UNKNOWN_CITATION", "findings.citations")
    prose = [("summary", report.summary), *(("findings.text", finding.text) for finding in report.findings),
             *(("limitations", text) for text in report.limitations), *(("actions", text) for text in report.actions),
             ("self_reported_confidence.basis", report.self_reported_confidence.basis)]
    source_texts = set(_source_strings(evidence))
    quoted_sources = {quoted for source in source_texts
                      for variant in {source, source.replace("'", "’"), source.replace("’", "'")}
                      for quoted in (f"'{variant}'", f"‘{variant}’")}
    source_pattern = "|".join(re.escape(quoted) for quoted in sorted(quoted_sources, key=lambda value: (-len(value), value)))
    for location, text in prose:
        normalized = unicodedata.normalize("NFC", text)
        if re.search(r"(?:(?:điểm|chỉ số|mức)\s+(?:rủi ro|tin cậy)|điểm tự báo cáo|độ tin cậy|risk score|confidence score)"
                     r"[^.!?;\n]{0,120}?(?:\d|\b(?:một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|trăm)\b)",
                     normalized, re.IGNORECASE):
            raise ReportValidationError("UNSUPPORTED_SCORE", location)
        # Only exact supplied source text may use ambiguous single quotes.
        # Matching the complete source handles possessives without swallowing
        # intervening prose between two quoted titles.
        # One pass over original text prevents edits from manufacturing a new
        # match; longest-first matching preserves nested source apostrophes.
        if location == "self_reported_confidence.basis":
            # This field explains interpretation uncertainty in Vietnamese;
            # quotation exemptions for source titles do not apply here.
            screen_input = re.sub(r'["“”`]', "", normalized)
        else:
            screen_input = re.sub(source_pattern, " ", normalized.casefold()) if source_pattern else normalized
        if not screen_vietnamese(screen_input):
            raise ReportValidationError("NON_VIETNAMESE_PROSE", location)
    return report.model_dump()
