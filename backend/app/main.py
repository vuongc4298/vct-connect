from uuid import UUID
from ipaddress import ip_address
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
from .storage import Store


class Submission(BaseModel):
    source_url: str

    @field_validator("source_url")
    @classmethod
    def fixture_only(cls, value: str) -> str:
        return validate_fixture_url(value)


def create_app(
    store: Store | None = None,
    settings: Settings | None = None,
    azure_queue=None,
    verifier: TokenVerifier | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or Store(settings.database_url)
    verifier = verifier or ClerkTokenVerifier(settings)
    app = FastAPI(title="VCT Connect authenticated tracer")

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

    @app.post("/api/v1/analyses", status_code=202)
    def submit(
        body: Submission,
        principal: Annotated[Principal, Depends(require_roles(CUSTOMER))],
    ):
        try:
            if settings.queue_transport == "local":
                analysis_id = store.submit_local(body.source_url, principal.user_id)
            else:
                analysis_id = store.submit_azure(body.source_url, principal.user_id)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Queue or database unavailable") from exc
        return {"id": analysis_id, "status": "QUEUED"}

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
