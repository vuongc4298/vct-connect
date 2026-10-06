from typing import Annotated, Literal
import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, ValidationError

PROMPT_VERSION = "vi-text.v8"
SCHEMA_VERSION = "text-report.v2"
PIPELINE_VERSION = "saved-evidence.v1"
VALIDATION_VERSION = "vi-prose.v5"
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

    Require Vietnamese cues in each sentence. validate_report exempts exact
    supplied source quotations before this screen; arbitrary quotes stay visible.
    """
    text = unicodedata.normalize("NFC", text).casefold()
    # Remove only numeric technical quantities, not standalone foreign symbols.
    # The existing casefold maps µm and Ω to μm and ω respectively.
    text = re.sub(r"(?<![\w.,])\d+(?:[.,]\d+)?[ \t]*(?:μm|ω)(?!\w)", " ", text)
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
    # Offline compact-clause probes demonstrate ordinary Vietnamese vocabulary.
    words_vi.update("hơi xốp dùng hằng ổn tốt suốt mỗi thùng gói khác thường rời kho "
                    "nói dễ rách ướt đầu tiên nêu quy đóng túi đại diện mọi lô".split())
    words_vi.update("ảnh chụp đường may lệch mép mô tả ghi vải thoáng khí ít nhăn "
                    "nắp hộp gioăng cao su chống tràn bảng cỡ đo vòng eo kiện móp góc "
                    "đồ bên trong nguyên chê khóa kéo kẹt sau vài lần".split())
    words_vi.update("mỏng rẻ".split())
    foreign_words = set("the this that is are and with should supplier reliable before order "
                        "shipping guaranteed dispatch delivery payment terms subject credit approval "
                        "freight collect duties excluded buyer protection refund tracking pending must clear".split())
    sentences = re.split(r"[!?;\n]+|(?<!\d)\.|\.(?!\d)", text)
    checked = False
    for sentence in sentences:
        word_matches = list(re.finditer(r"[^\W\d_]+", sentence, re.UNICODE))
        words = [match.group() for match in word_matches]
        if not words:
            continue
        # Count the fabric homograph as Vietnamese only immediately after 'vải'.
        # Keep every token and the existing sentence/ratio thresholds intact.
        fabric_words = {index for index, word in enumerate(words)
                        if word == "the" and index > 0 and words[index - 1] == "vải"
                        and re.fullmatch(r"[ \t]+", sentence[word_matches[index - 1].end():word_matches[index].start()])}
        checked = True
        if (any(character.isalpha() and not unicodedata.name(character, "").startswith("LATIN")
                for character in sentence)
                or any(word in foreign_words and index not in fabric_words for index, word in enumerate(words))
                or sum(word in words_vi or index in fabric_words for index, word in enumerate(words)) < max(2, len(words) / 2)
                or not re.search(r"[ăâđêôơưà-ỹ]", sentence)):
            return False
    return checked


def _unsupported_score(text: str) -> bool:
    # Keep the supplier-risk guard independent of interpretation confidence.
    number_words = r"một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|trăm"
    if re.search(r"(?:(?:điểm|chỉ số|mức)\s+rủi ro|risk score)"
                 rf"[^.!?;\n]{{0,120}}?(?:\d|\b(?:{number_words})\b)", text, re.IGNORECASE):
        return True
    # A label must connect to a value through score syntax, not arbitrary prose
    # such as 'còn hạn chế vì chỉ có 2 đánh giá' or a later source price.
    label = (r"(?:(?:điểm|chỉ số|mức)\s+tin cậy|điểm tự báo cáo|độ tin cậy|"
             r"confidence score|chắc chắn|tự tin)")
    connectors = r"(?:\s+(?:của|mô|hình|được|hệ|thống|tính|là|ở|mức|khoảng|bằng|đạt|tổng|thể|diễn|giải|này|đến|đánh|giá))*"
    value = (rf"(?:[+-]?\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?|"
             rf"\b(?:{number_words})(?:\s+(?:{number_words}|mươi|phần|trên))*\b)"
             r"(?:\s*(?:%|phần trăm))?")
    for match in re.finditer(rf"\b{label}\s*[:=]?{connectors}\s*[:=]?\s*(?P<value>{value})", text, re.IGNORECASE):
        score = match.group("value").casefold()
        # Unquantified 'một phần' expresses qualitative uncertainty, not a score.
        if (re.fullmatch(r"một\s+phần", score)
                and not re.match(r"\s*(?:[+-]?\d|%|/)", text[match.end():])):
            continue
        # Explicit evidence counts are quantities, never inferred confidence.
        is_count = re.match(r"\s+(?:đánh giá|sản phẩm|mẫu|nguồn|tờ|lớp)\b", text[match.end():], re.IGNORECASE)
        if is_count and not any(marker in score for marker in ("%", "/", "phần", "trên")):
            continue
        return True
    return False


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
                      for opening, closing in (("'", "'"), ("‘", "’"), ('"', '"'), ("“", "”"), ("`", "`"))
                      for quoted in (opening + variant + closing,)}
    source_pattern = "|".join(re.escape(quoted) for quoted in sorted(quoted_sources, key=lambda value: (-len(value), value)))
    for location, text in prose:
        normalized = unicodedata.normalize("NFC", text)
        if _unsupported_score(normalized):
            raise ReportValidationError("UNSUPPORTED_SCORE", location)
        # Only complete exact supplied source text receives a quote exemption.
        # Matching the complete source handles possessives without swallowing
        # intervening prose between two quoted titles.
        # One pass over original text prevents edits from manufacturing a new
        # match; longest-first matching preserves nested source apostrophes.
        if location == "self_reported_confidence.basis":
            # This field explains interpretation uncertainty in Vietnamese;
            # quotation exemptions for source titles do not apply here.
            screen_input = normalized
        else:
            screen_input = re.sub(source_pattern, " ", normalized.casefold()) if source_pattern else normalized
        if not screen_vietnamese(screen_input):
            raise ReportValidationError("NON_VIETNAMESE_PROSE", location)
    return report.model_dump()
