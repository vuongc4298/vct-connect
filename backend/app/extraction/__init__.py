"""Public supplier evidence extraction contracts and adapters."""

from .offer1688 import extract_1688, parse_1688_page
from .contracts import SupplierData, ExtractionStatus
from .urls import normalize_1688_url
from .urls import normalize_source_url, normalize_taobao_url, source_platform
from .taobao import extract_taobao, parse_taobao_page

__all__ = ["SupplierData", "ExtractionStatus", "extract_1688", "parse_1688_page", "normalize_1688_url",
           "extract_taobao", "parse_taobao_page", "normalize_taobao_url", "normalize_source_url", "source_platform"]
