"""Story 3.1 service: interpret one persisted SupplierData snapshot and store provenance."""
from __future__ import annotations

from uuid import UUID

from backend.app.storage import Store

from .interpretation import InterpretationRun, interpret_supplier_data
from .provider import LLMProvider
from .store import load_supplier_snapshot, persist_interpretation_run


def interpret_analysis_snapshot(
    store: Store,
    analysis_id: UUID,
    *,
    provider: LLMProvider,
    model: str,
) -> tuple[UUID, InterpretationRun]:
    snapshot_id, supplier_data = load_supplier_snapshot(store, analysis_id)
    run = interpret_supplier_data(
        supplier_data,
        provider=provider,
        model=model,
        metadata={
            "feature": "supplier_interpretation",
            "session_id": str(analysis_id),
        },
    )
    run_id = persist_interpretation_run(
        store,
        analysis_id=analysis_id,
        supplier_snapshot_id=snapshot_id,
        run=run,
    )
    return run_id, run

