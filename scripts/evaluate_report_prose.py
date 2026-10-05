"""Offline synthetic language-contract probe; no provider or database calls.

Run from the repository root with PYTHONPATH set to that root. Labels describe
language, not factual correctness. Report counts are development evidence only.
"""
import argparse
import json
from pathlib import Path

from backend.app.interpretation.contracts import (
    ReportValidationError, VALIDATION_VERSION, screen_vietnamese, validate_report,
)


def evaluate(path):
    rows = []
    identifiers = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        if (not isinstance(case["id"], str) or case["id"] in identifiers
                or type(case["expected_vietnamese"]) is not bool
                or not isinstance(case["text"], str)):
            raise ValueError("Invalid or duplicate synthetic probe case")
        identifiers.add(case["id"])
        envelope = {
            "summary": "Nguồn có thông tin sản phẩm.",
            "findings": [{"kind": "observation", "text": case["text"], "citations": ["E1"]}],
            "limitations": ["Chưa xác minh độc lập."],
            "actions": ["Yêu cầu mẫu trước đặt cọc."],
            "self_reported_confidence": {"score": 0.5, "basis": "Dữ liệu nguồn còn thiếu."},
        }
        rejection = None
        try:
            validate_report(json.dumps(envelope, ensure_ascii=False), [{"id": "E1"}])
        except ReportValidationError as error:
            rejection = {"reason": error.reason, "location": error.location}
        rows.append({"id": case["id"], "expected_vietnamese": case["expected_vietnamese"],
                     "screen_accepts": screen_vietnamese(case["text"]),
                     "report_accepts": rejection is None, "report_rejection": rejection})
    return {"validation_version": VALIDATION_VERSION, "synthetic_cases": len(rows),
            "screen_false_rejections": [r["id"] for r in rows if r["expected_vietnamese"] and not r["screen_accepts"]],
            "screen_false_acceptances": [r["id"] for r in rows if not r["expected_vietnamese"] and r["screen_accepts"]],
            "report_language_mismatches": [r["id"] for r in rows
                if (r["report_rejection"] is None or r["report_rejection"]["reason"] == "NON_VIETNAMESE_PROSE")
                and r["expected_vietnamese"] != r["report_accepts"]],
            "report_other_rejections": [r["id"] for r in rows
                if r["report_rejection"] is not None and r["report_rejection"]["reason"] != "NON_VIETNAMESE_PROSE"],
            "cases": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.fixture), ensure_ascii=False, indent=2))
