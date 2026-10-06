"""Manual Story 3.1 tracer for one already-completed supplier snapshot."""
from __future__ import annotations

import argparse
import os
from uuid import UUID

from backend.app.storage import Store

from .service import interpret_analysis_snapshot
from .yescale import YEScaleProvider


def main() -> None:
    parser = argparse.ArgumentParser(description="Interpret one completed VCT supplier snapshot through YEScale")
    parser.add_argument("analysis_id", type=UUID)
    parser.add_argument("--model", default=os.getenv("YESCALE_MODEL", "gpt-4o-mini"))
    args = parser.parse_args()
    api_key = os.getenv("YESCALE_API_KEY")
    if not api_key:
        parser.error("YESCALE_API_KEY is required")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        parser.error("DATABASE_URL is required")

    with YEScaleProvider(api_key) as provider:
        run_id, run = interpret_analysis_snapshot(
            Store(database_url), args.analysis_id, provider=provider, model=args.model,
        )
    response = run.provider_response
    # Deliberately print only non-secret operational provenance.
    print(f"run_id={run_id}")
    print(f"provider_request_id={response.request_id or 'unavailable'}")
    print(f"model={response.response_model}")
    print(f"tokens={response.usage.total_tokens}")
    print(f"cost_usd={response.usage.cost_usd if response.usage.cost_usd is not None else 'unavailable'}")
    print(f"confidence={run.interpretation.confidence:.4f}")


if __name__ == "__main__":
    main()

