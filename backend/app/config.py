from dataclasses import dataclass
import base64
import os


@dataclass(frozen=True)
class Settings:
    database_url: str
    queue_transport: str
    azure_service_bus_connection_string: str | None
    azure_service_bus_queue: str | None
    developer_mode: bool
    clerk_secret_key: str | None = None
    clerk_jwt_key: str | None = None
    clerk_issuer: str | None = None
    clerk_audience: str = "vct-connect-api"
    clerk_authorized_parties: tuple[str, ...] = (
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    )
    processing_max_attempts: int = 5
    processing_lease_seconds: int = 300
    azure_lock_renewal_seconds: int = 300
    outbox_max_attempts: int = 10
    outbox_lease_seconds: int = 60
    outbox_base_backoff_seconds: int = 2
    outbox_max_backoff_seconds: int = 60
    api_runtime: str = "local"
    azure_service_bus_namespace: str | None = None
    guest_browser_limit: int = 3
    guest_global_limit: int = 100
    customer_limit: int = 20
    admission_window_seconds: int = 86400
    public_browser_fallback: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.processing_max_attempts <= 10:
            raise ValueError("PROCESSING_MAX_ATTEMPTS must be between 1 and 10")
        if self.processing_lease_seconds < self.azure_lock_renewal_seconds:
            raise ValueError(
                "PROCESSING_LEASE_SECONDS must be at least AZURE_LOCK_RENEWAL_SECONDS"
            )
        for name in ("guest_browser_limit", "guest_global_limit", "customer_limit", "admission_window_seconds"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")

    @classmethod
    def from_env(cls) -> "Settings":
        transport = os.getenv("QUEUE_TRANSPORT", "local")
        if transport not in {"local", "azure"}:
            raise ValueError("QUEUE_TRANSPORT must be local or azure")
        developer_mode = os.getenv("DEVELOPER_MODE", "false").lower() == "true"
        api_runtime = os.getenv("API_RUNTIME", "local")
        if api_runtime not in {"local", "azure", "worker"}:
            raise ValueError("API_RUNTIME must be local, azure, or worker")
        if api_runtime == "local" and not developer_mode:
            raise ValueError("Local API requires DEVELOPER_MODE=true")
        if api_runtime == "azure" and developer_mode:
            raise ValueError("Azure API must not enable DEVELOPER_MODE")
        if api_runtime in {"azure", "worker"} and transport != "azure":
            raise ValueError("Azure runtime requires Azure queue transport")
        settings = cls(
            database_url=os.environ["DATABASE_URL"],
            queue_transport=transport,
            azure_service_bus_connection_string=os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING"),
            azure_service_bus_queue=os.getenv("AZURE_SERVICE_BUS_QUEUE"),
            azure_service_bus_namespace=os.getenv("AZURE_SERVICE_BUS_NAMESPACE"),
            api_runtime=api_runtime,
            developer_mode=developer_mode,
            clerk_secret_key=os.getenv("CLERK_SECRET_KEY"),
            clerk_jwt_key=os.getenv("CLERK_JWT_KEY"),
            clerk_issuer=os.getenv("CLERK_ISSUER") or _issuer_from_publishable_key(
                os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY")
            ),
            clerk_audience=os.getenv("CLERK_AUDIENCE", "vct-connect-api"),
            clerk_authorized_parties=tuple(
                party.strip()
                for party in os.getenv(
                    "CLERK_AUTHORIZED_PARTIES",
                    "http://127.0.0.1:3000,http://localhost:3000",
                ).split(",")
                if party.strip()
            ),
            processing_max_attempts=_bounded_int("PROCESSING_MAX_ATTEMPTS", 5, 1, 10),
            processing_lease_seconds=_bounded_int("PROCESSING_LEASE_SECONDS", 300, 10, 3600),
            azure_lock_renewal_seconds=_bounded_int(
                "AZURE_LOCK_RENEWAL_SECONDS", 300, 30, 3600
            ),
            outbox_max_attempts=_bounded_int("OUTBOX_MAX_ATTEMPTS", 10, 1, 100),
            outbox_lease_seconds=_bounded_int("OUTBOX_LEASE_SECONDS", 60, 10, 3600),
            outbox_base_backoff_seconds=_bounded_int(
                "OUTBOX_BASE_BACKOFF_SECONDS", 2, 1, 300
            ),
            outbox_max_backoff_seconds=_bounded_int(
                "OUTBOX_MAX_BACKOFF_SECONDS", 60, 1, 3600
            ),
            guest_browser_limit=_bounded_int("GUEST_BROWSER_LIMIT", 3, 1, 10000),
            guest_global_limit=_bounded_int("GUEST_GLOBAL_LIMIT", 100, 1, 1000000),
            customer_limit=_bounded_int("CUSTOMER_LIMIT", 20, 1, 100000),
            admission_window_seconds=_bounded_int("ADMISSION_WINDOW_SECONDS", 86400, 60, 31536000),
            public_browser_fallback=os.getenv("PUBLIC_BROWSER_FALLBACK", "false").lower() == "true",
        )
        if transport == "azure" and not (
            settings.azure_service_bus_queue and (
                settings.azure_service_bus_connection_string or settings.azure_service_bus_namespace
            )
        ):
            raise ValueError("Azure transport requires a queue and namespace or connection string")
        if settings.outbox_max_backoff_seconds < settings.outbox_base_backoff_seconds:
            raise ValueError(
                "OUTBOX_MAX_BACKOFF_SECONDS must be at least OUTBOX_BASE_BACKOFF_SECONDS"
            )
        if api_runtime == "azure" and not (
            settings.clerk_issuer and settings.clerk_authorized_parties
            and (settings.clerk_secret_key or settings.clerk_jwt_key)
        ):
            raise ValueError("Azure API requires Clerk issuer, authorized party, and verification key")
        return settings


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _issuer_from_publishable_key(publishable_key: str | None) -> str | None:
    """Derive Clerk's Frontend API issuer without exposing or persisting a token."""
    if not publishable_key or "_" not in publishable_key:
        return None
    encoded = publishable_key.split("_", 2)[-1]
    try:
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    host = decoded.removesuffix("$").strip()
    return f"https://{host}" if host else None
