from uuid import UUID
from ipaddress import ip_address
from email.message import Message
import re
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ValidationError, field_validator
from .auth import (
    ADMIN,
    ALL_ROLES,
    CUSTOMER,
    INTERNAL_REVIEWER,
    AuthenticationUnavailable,
    ClerkTokenVerifier,
    InvalidIdentity,
    Principal,
    TokenVerifier,
)
from .config import Settings
from .fixture import validate_fixture_url
from .extraction import normalize_1688_url, normalize_source_url
from .extraction.urls import source_platform
from .extraction.taobao import parse_taobao_page, decode_taobao_html
from .extraction.extensiontaobao import TaobaoCapture, normalize_taobao_capture
from .extraction.offer1688 import MAX_HTML_BYTES, parse_1688_page
from .extraction.extension1688 import DomCapture, MAX_CAPTURE_BYTES, normalize_capture
from .storage import AdmissionDenied, Store


class Submission(BaseModel):
    source_url: str

    @field_validator("source_url")
    @classmethod
    def supported_offer(cls, value: str) -> str:
        try:
            return validate_fixture_url(value)
        except ValueError:
            return normalize_source_url(value)


def create_app(
    store: Store | None = None,
    settings: Settings | None = None,
    azure_queue=None,
    verifier: TokenVerifier | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or Store(settings.database_url)
    verifier = verifier or ClerkTokenVerifier(settings)
    app = FastAPI(title="VCT Connect tracer")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.middleware("http")
    async def loopback_only(request: Request, call_next):
        host = request.client.host if request.client else ""
        try:
            allowed = ip_address(host).is_loopback
        except ValueError:
            allowed = host == "testclient"
        if settings.api_runtime == "local" and not allowed:
            return JSONResponse(status_code=403, content={"detail": "Developer tracer is loopback only"})
        return await call_next(request)

    def current_principal(request: Request) -> Principal:
        try:
            identity = verifier.verify(request)
        except InvalidIdentity as exc:
            raise HTTPException(status_code=401, detail="Unauthorized") from exc
        except AuthenticationUnavailable as exc:
            raise HTTPException(status_code=503, detail="Authentication unavailable") from exc
        try:
            user = store.resolve_user(identity.subject, identity.email)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Database unavailable") from exc
        if user["role"] not in ALL_ROLES:
            raise HTTPException(status_code=403, detail="Forbidden")
        return Principal(
            user_id=user["id"],
            clerk_user_id=user["clerk_user_id"],
            role=user["role"],
        )

    def require_roles(*allowed_roles: str):
        allowed = frozenset(allowed_roles)

        def dependency(
            principal: Annotated[Principal, Depends(current_principal)],
        ) -> Principal:
            if principal.role not in allowed:
                raise HTTPException(status_code=403, detail="Forbidden")
            return principal

        return dependency

    def guest_key(request: Request) -> str:
        key = request.headers.get("x-vct-guest-key", "")
        if not re.fullmatch(r"[0-9a-f]{64}", key):
            raise HTTPException(status_code=404, detail="Analysis not found")
        return key

    @app.post("/api/v1/analyses", status_code=202)
    def submit(
        body: Submission,
        principal: Annotated[Principal, Depends(require_roles(CUSTOMER))],
    ):
        try:
            analysis_id = store.submit_customer(
                body.source_url, principal.user_id,
                azure=settings.queue_transport == "azure",
                customer_limit=settings.customer_limit,
                window_seconds=settings.admission_window_seconds,
            )
        except AdmissionDenied as exc:
            raise HTTPException(status_code=429, detail="Submission limit reached") from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Queue or database unavailable") from exc
        return {"id": analysis_id, "status": "QUEUED"}

    @app.post("/api/v1/analyses/import", status_code=201)
    async def import_saved_page(
        request: Request,
        source_url: str,
        principal: Annotated[Principal, Depends(require_roles(CUSTOMER))],
    ):
        try:
            source_url = normalize_source_url(source_url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Unsupported source URL") from exc
        platform = source_platform(source_url)
        if platform == "ALIBABA":
            raise HTTPException(status_code=422, detail="Alibaba saved-page import is not supported")
        taobao = platform == "TAOBAO"
        media = Message()
        media["content-type"] = request.headers.get("content-type", "")
        charsets = [value for name, value in (media.get_params(header="content-type") or [])[1:]
                    if name.lower() == "charset"]
        if media.get_content_type() != "text/html" or not taobao and any(
            not isinstance(value, str) or value.lower() not in {"utf-8", "utf8"}
            for value in charsets
        ):
            raise HTTPException(status_code=415, detail="Upload a UTF-8 HTML page")
        try:
            declared_size = int(request.headers.get("content-length", "0"))
        except ValueError:
            declared_size = 0
        if declared_size > MAX_HTML_BYTES:
            raise HTTPException(status_code=413, detail="HTML page exceeds 2 MB")
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > MAX_HTML_BYTES:
                raise HTTPException(status_code=413, detail="HTML page exceeds 2 MB")
        if not content:
            raise HTTPException(status_code=422, detail="HTML page is empty")
        try:
            html = decode_taobao_html(bytes(content), charsets, strict=True) if taobao else content.decode("utf-8-sig")
        except (UnicodeError, ValueError) as exc:
            raise HTTPException(status_code=415, detail="Unsupported or conflicting HTML encoding") from exc
        declared_charset = re.search(
            r'''<meta\b[^>]*\bcharset\s*=\s*["']?([a-z0-9_-]+)''', html[:8192], re.IGNORECASE,
        )
        if not taobao and declared_charset and declared_charset.group(1).lower() not in {"utf-8", "utf8"}:
            raise HTTPException(status_code=415, detail="Upload a UTF-8 HTML page")
        try:
            payload = await run_in_threadpool(
                parse_taobao_page if taobao else parse_1688_page, html, source_url, extraction_method="USER_UPLOAD",
                uploaded_bytes=bytes(content),
            )
        except RecursionError:
            payload = {"source_url": source_url, "extraction_status": "PARSE_FAILED",
                       "reason": "PARSER_LIMIT"}
        try:
            analysis_id = await run_in_threadpool(
                store.import_customer_page,
                source_url, principal.user_id, payload,
                customer_limit=settings.customer_limit,
                window_seconds=settings.admission_window_seconds,
            )
        except AdmissionDenied as exc:
            raise HTTPException(status_code=429, detail="Submission limit reached") from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Database unavailable") from exc
        return {"id": analysis_id, "status": "COMPLETED"}

    @app.post("/api/v1/analyses/capture", status_code=201)
    async def capture_browser_evidence(
        request: Request,
        principal: Annotated[Principal, Depends(require_roles(CUSTOMER))],
    ):
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(status_code=415, detail="Submit selected JSON evidence")
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > MAX_CAPTURE_BYTES:
                raise HTTPException(status_code=413, detail="Capture exceeds 16 KB")
        try:
            import json
            selected = json.loads(bytes(content))
            if not isinstance(selected, dict):
                raise ValueError("Invalid selected evidence")
            platform = source_platform(selected.get("source_url", ""))
            if platform == "ALIBABA":
                raise ValueError("Alibaba browser capture is not supported")
            if platform == "TAOBAO":
                payload = normalize_taobao_capture(TaobaoCapture.model_validate_json(bytes(content)))
            else:
                payload = normalize_capture(DomCapture.model_validate_json(bytes(content)))
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail="Invalid selected evidence") from exc
        except RecursionError as exc:
            raise HTTPException(status_code=422, detail="Selected evidence is too deeply nested") from exc
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            analysis_id = await run_in_threadpool(
                store.capture_customer_page,
                payload["source_url"], principal.user_id, payload,
                customer_limit=settings.customer_limit,
                window_seconds=settings.admission_window_seconds,
            )
        except AdmissionDenied as exc:
            raise HTTPException(status_code=429, detail="Submission limit reached") from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Database unavailable") from exc
        return {"id": analysis_id, "status": "COMPLETED",
                "extraction_status": payload["extraction_status"]}

    @app.post("/api/v1/guest-analyses", status_code=202)
    def submit_guest(body: Submission, request: Request):
        key = guest_key(request)
        try:
            analysis_id = store.submit_guest(
                body.source_url, key, azure=settings.queue_transport == "azure",
                browser_limit=settings.guest_browser_limit,
                global_limit=settings.guest_global_limit,
                window_seconds=settings.admission_window_seconds,
            )
        except AdmissionDenied as exc:
            raise HTTPException(status_code=429, detail="Submission limit reached") from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Queue or database unavailable") from exc
        return {"id": analysis_id, "status": "QUEUED"}

    @app.get("/api/v1/guest-analyses/{analysis_id}")
    def guest_status(analysis_id: UUID, request: Request):
        key = guest_key(request)
        try:
            row = store.get_for_guest(analysis_id, key)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Database unavailable") from exc
        if row is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return row

    @app.get("/api/v1/analyses/{analysis_id}")
    def status(
        analysis_id: UUID,
        principal: Annotated[
            Principal,
            Depends(require_roles(CUSTOMER, INTERNAL_REVIEWER, ADMIN)),
        ],
    ):
        try:
            if principal.role == CUSTOMER:
                row = store.get_for_user(analysis_id, principal.user_id)
            else:
                row = store.get(analysis_id)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Database unavailable") from exc
        if row is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return row

    return app


app = create_app()
