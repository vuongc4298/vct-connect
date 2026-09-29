from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from clerk_backend_api import AuthenticateRequestOptions, authenticate_request
from clerk_backend_api.security.types import TokenVerificationErrorReason
from fastapi import Request
import httpx

from .config import Settings


CUSTOMER = "CUSTOMER"
INTERNAL_REVIEWER = "INTERNAL_REVIEWER"
ADMIN = "ADMIN"
ALL_ROLES = frozenset({CUSTOMER, INTERNAL_REVIEWER, ADMIN})


class InvalidIdentity(Exception):
    """The request did not contain a valid Clerk session identity."""


class AuthenticationUnavailable(Exception):
    """The server is missing required Clerk configuration."""


@dataclass(frozen=True)
class VerifiedIdentity:
    subject: str
    email: str | None = None


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    clerk_user_id: str
    role: str


class TokenVerifier(Protocol):
    def verify(self, request: Request) -> VerifiedIdentity: ...


class ClerkTokenVerifier:
    """Verify Clerk session tokens, including claims not checked by SDK v6."""

    def __init__(self, settings: Settings):
        self.secret_key = settings.clerk_secret_key
        self.jwt_key = settings.clerk_jwt_key
        self.issuer = settings.clerk_issuer
        self.audience = settings.clerk_audience
        self.authorized_parties = list(settings.clerk_authorized_parties)

    def verify(self, request: Request) -> VerifiedIdentity:
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer ") or not authorization[7:].strip():
            raise InvalidIdentity
        if not (self.secret_key or self.jwt_key) or not self.issuer:
            raise AuthenticationUnavailable

        try:
            state = authenticate_request(
                request,
                AuthenticateRequestOptions(
                    secret_key=self.secret_key,
                    jwt_key=self.jwt_key,
                    audience=self.audience,
                    authorized_parties=self.authorized_parties,
                    accepts_token=["session_token"],
                ),
            )
        except (httpx.RequestError, TimeoutError, OSError) as exc:
            raise AuthenticationUnavailable from exc
        if state.reason in {
            TokenVerificationErrorReason.JWK_FAILED_TO_LOAD,
            TokenVerificationErrorReason.JWK_REMOTE_INVALID,
            TokenVerificationErrorReason.JWK_FAILED_TO_RESOLVE,
            TokenVerificationErrorReason.SERVER_ERROR,
        }:
            raise AuthenticationUnavailable
        payload = state.payload if state.is_signed_in else None
        if not payload or payload.get("iss") != self.issuer:
            raise InvalidIdentity

        subject = payload.get("sub")
        session_id = payload.get("sid")
        if (
            not isinstance(subject, str)
            or not subject.strip()
            or not isinstance(session_id, str)
            or not session_id.strip()
        ):
            raise InvalidIdentity
        email = payload.get("email")
        return VerifiedIdentity(
            subject=subject,
            email=email if isinstance(email, str) and email.strip() else None,
        )
