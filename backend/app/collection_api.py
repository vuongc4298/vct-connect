from hashlib import sha256
import json
from fastapi import Depends, HTTPException, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from .extraction.supplier_bundle import MAX_BUNDLE_BYTES, MAX_HTML_BUNDLE_BYTES, SupplierBundle, normalize_bundle
from .storage_errors import CollectionConflict


def register_collection_routes(app, store, settings, customer_dependency, admission_error):
    async def read_bundle(request):
        if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
            raise HTTPException(415, "Submit selected JSON evidence")
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > MAX_HTML_BUNDLE_BYTES:
                raise HTTPException(413, "HTML collection exceeds 8 MB")
        try:
            decoded = json.loads(bytes(content))
            if len(content) > MAX_BUNDLE_BYTES and (not isinstance(decoded, dict) or not decoded.get("html_sources")):
                raise HTTPException(413, "Collection exceeds 32 KB")
            bundle = SupplierBundle.model_validate_json(bytes(content))
            if not bundle.html_sources and len(content) > MAX_BUNDLE_BYTES:
                raise HTTPException(413, "Collection exceeds 32 KB")
            payload = await run_in_threadpool(normalize_bundle, bundle)
            canonical = json.dumps(bundle.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
            return bundle, payload, sha256(canonical.encode("utf-8")).hexdigest()
        except (ValidationError, ValueError, TypeError, RecursionError) as exc:
            raise HTTPException(422, "Invalid linked supplier evidence") from exc

    @app.post("/api/v1/analyses/collection/begin", status_code=202)
    async def begin(request: Request, principal=Depends(customer_dependency)):
        bundle, payload, digest = await read_bundle(request)
        if bundle.shop or bundle.factory or bundle.outcomes:
            raise HTTPException(422, "Begin with product evidence only")
        try:
            await run_in_threadpool(store.begin_collection, bundle.job_id, principal.user_id, payload, digest,
                customer_limit=settings.customer_limit, trial_limit=settings.trial_customer_limit,
                window_seconds=settings.admission_window_seconds, guided=bundle.guided)
        except admission_error as exc:
            raise HTTPException(429, "Submission limit reached") from exc
        except CollectionConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"id": str(bundle.job_id), "status": "PROCESSING"}

    @app.post("/api/v1/analyses/collection/finish", status_code=202)
    async def finish(request: Request, principal=Depends(customer_dependency)):
        bundle, payload, digest = await read_bundle(request)
        if len(bundle.outcomes) != 2:
            raise HTTPException(422, "Finish with outcomes for both linked pages")
        try:
            await run_in_threadpool(store.finish_collection, bundle.job_id, principal.user_id, payload, digest,
                                   azure=settings.queue_transport == "azure")
        except LookupError as exc:
            raise HTTPException(404, "Collection not found") from exc
        except CollectionConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        row = await run_in_threadpool(store.get_for_user, bundle.job_id, principal.user_id)
        return {"id": str(bundle.job_id), "status": row["status"]}
