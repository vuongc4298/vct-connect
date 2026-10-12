"""Operator-only offline import. Run from the repository root; no source fetching.

Dry run is the default. --submit admits a new analysis for the base analysis's
owner through normal quotas and the configured queue, leaving its report intact.
"""
import argparse
import json
from pathlib import Path
from uuid import UUID

from ..config import Settings
from ..storage import Store
from .factory1688_saved import MAX_PAGE_BYTES, enrich_saved_factory


def read_page(path):
    if path.stat().st_size > MAX_PAGE_BYTES:
        raise ValueError("Saved supplier page exceeds the size limit")
    return path.read_text(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-analysis", type=UUID, required=True)
    for name in ("product-html", "shop-html", "factory-html"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--factory-url", required=True)
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    store = Store(settings.database_url)
    row = store.get(args.base_analysis)
    if not row or row["status"] != "COMPLETED" or not row.get("supplier_data"):
        raise ValueError("Base analysis must have a completed supplier snapshot")
    with store.connect() as connection:
        owner = connection.execute("SELECT user_id, actor_type FROM analyses WHERE id = %s",
                                   (args.base_analysis,)).fetchone()
    if not owner or not owner["user_id"] or owner["actor_type"] != "CUSTOMER":
        raise ValueError("Base analysis must belong to a customer")
    payload = enrich_saved_factory(
        {"source_url": row["source_url"], "supplier_data": row["supplier_data"],
         "supplier_snapshot_id": str(row["supplier_snapshot_id"]),
         "raw_payload": row["raw_evidence"], "reviews": row["reviews"]},
        product_html=read_page(args.product_html), shop_html=read_page(args.shop_html),
        factory_html=read_page(args.factory_html), factory_url=args.factory_url)
    if args.submit:
        analysis_id = store.import_customer_page(
            row["source_url"], owner["user_id"], payload,
            customer_limit=settings.customer_limit, trial_limit=settings.trial_customer_limit,
            window_seconds=settings.admission_window_seconds,
            azure=settings.queue_transport == "azure")
        print(json.dumps({"analysis_id": str(analysis_id), "queued": True}))
    else:
        print(json.dumps({"queued": False, "years_active": payload["supplier_data"]["years_active"],
                          "profile_claims": payload["raw_payload"]["profile_claims"],
                          "reviews": len(payload["reviews"]),
                          "missing_fields": payload["supplier_data"]["missing_fields"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
