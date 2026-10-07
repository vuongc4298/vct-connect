"""Evidence-backed reporting contracts for VCT Connect."""

from .builder import build_report
from .contracts import GUEST_PREVIEW_SCHEMA_VERSION, REPORT_SCHEMA_VERSION, GuestPreviewPayload, ReportPayload
from .store import get_report_for_user, persist_report_and_complete

__all__ = [
    "REPORT_SCHEMA_VERSION",
    "GUEST_PREVIEW_SCHEMA_VERSION",
    "ReportPayload",
    "GuestPreviewPayload",
    "build_report",
    "get_report_for_user",
    "persist_report_and_complete",
]
