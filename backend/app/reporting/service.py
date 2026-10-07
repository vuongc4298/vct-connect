"""Worker-facing deterministic report generation."""
from __future__ import annotations

from backend.app.storage import Store

from .builder import build_report
from .store import load_report_source, persist_report_and_complete


def run_worker_report(store: Store, claim: dict) -> None:
    source = load_report_source(
        store,
        claim["analysis_id"],
        claim["token"],
    )
    assessment = source["assessment"]
    report = build_report(
        analysis_id=source["analysis_id"],
        source_url=source["source_url"],
        snapshot=source["snapshot"],
        assessment=assessment,
        findings=source["findings"],
        evidence=source["evidence"],
        raw_reviews=source["raw_reviews"],
    )
    persist_report_and_complete(
        store,
        analysis_id=claim["analysis_id"],
        token=claim["token"],
        assessment_id=assessment["id"],
        scoring_version=assessment["scoring_version"],
        report=report,
    )
