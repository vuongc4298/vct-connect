from uuid import UUID
from ipaddress import ip_address
import re
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
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
from .extraction import normalize_1688_url
from .storage import AdmissionDenied, Store


class Submission(BaseModel):
    source_url: str

    @field_validator("source_url")
    @classmethod
    def supported_offer(cls, value: str) -> str:
        try:
            return validate_fixture_url(value)
        except ValueError:
            return normalize_1688_url(value)


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
