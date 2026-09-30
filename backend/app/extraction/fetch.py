"""Shared bounded public HTTP transport; adapters supply identity and parsing policies."""
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit
import certifi
import httpcore
import httpx

MAX_HTML_BYTES = 2_000_000
MAX_REDIRECTS = 3
FETCH_BUDGET_SECONDS = 25
RETRY_DELAYS = (0.5, 1.0)
TRANSIENT_HTTP_STATUSES = {500, 502, 503, 504}


class UnsafeDestination(OSError):
    """DNS did not resolve only to public addresses for the approved host."""


class TemporaryDNSFailure(OSError):
    """A resolver failure that may recover within the extraction budget."""


class DNSResolutionFailed(OSError):
    """A permanent resolver failure, without exposing resolver details."""


def _public_addresses(host, port):
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        if exc.errno == socket.EAI_AGAIN:
            raise TemporaryDNSFailure("Temporary DNS failure") from exc
        raise DNSResolutionFailed("DNS resolution failed") from exc
    except TimeoutError as exc:
        raise httpx.ConnectTimeout("DNS timeout") from exc
    except OSError as exc:
        raise TemporaryDNSFailure("Temporary DNS failure") from exc
    try:
        if not addresses or not all(ipaddress.ip_address(address).is_global for address in addresses):
            raise UnsafeDestination("Destination must have only public addresses")
    except ValueError as exc:
        raise UnsafeDestination("Invalid DNS address") from exc
    return addresses


class DeadlineStream(httpcore.NetworkStream):
    """Clamp every socket operation, including later body reads, to one deadline."""

    def __init__(self, stream, deadline, clock):
        self.stream, self.deadline, self.clock = stream, deadline, clock

    def _timeout(self, timeout, error):
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise error("Extraction deadline elapsed")
        return min(timeout, remaining) if timeout is not None else remaining

    def read(self, max_bytes, timeout=None):
        return self.stream.read(max_bytes, timeout=self._timeout(timeout, httpcore.ReadTimeout))

    def write(self, buffer, timeout=None):
        return self.stream.write(buffer, timeout=self._timeout(timeout, httpcore.WriteTimeout))

    def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        stream = self.stream.start_tls(ssl_context, server_hostname=server_hostname,
                                       timeout=self._timeout(timeout, httpcore.ConnectTimeout))
        return DeadlineStream(stream, self.deadline, self.clock)

    def close(self):
        self.stream.close()

    def get_extra_info(self, info):
        return self.stream.get_extra_info(info)


class PublicOnlyBackend(httpcore.SyncBackend):
    def __init__(self, *, deadline=None, clock=time.monotonic, allowed_hosts=("detail.1688.com",)):
        self.deadline, self.clock = deadline, clock
        self.allowed_hosts = frozenset(allowed_hosts)

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if host not in self.allowed_hosts or port != 443:
            raise UnsafeDestination("Unapproved connection destination")
        started = self.clock()
        addresses = _public_addresses(host, port)
        # OS DNS resolution cannot be forcibly cancelled here. Recheck the
        # budget before connecting, and debit its elapsed time from connect.
        if timeout is not None:
            timeout -= self.clock() - started
        if self.deadline is not None:
            remaining = self.deadline - self.clock()
            timeout = min(timeout, remaining) if timeout is not None else remaining
        if timeout is not None and timeout <= 0:
            raise httpcore.ConnectTimeout("Extraction deadline elapsed")
        # Connect to the checked literal IP. The HTTP origin stays the hostname,
        # so TLS verifies the approved hostname and sends the correct SNI.
        stream = super().connect_tcp(sorted(addresses)[0], port, timeout, local_address, socket_options)
        return DeadlineStream(stream, self.deadline, self.clock) if self.deadline is not None else stream


def _public_transport(*, deadline, clock, allowed_hosts=("detail.1688.com",)) -> httpx.HTTPTransport:
    transport = httpx.HTTPTransport(trust_env=False)
    transport._pool.close()
    transport._pool = httpcore.ConnectionPool(
        ssl_context=ssl.create_default_context(cafile=certifi.where()),
        network_backend=PublicOnlyBackend(deadline=deadline, clock=clock, allowed_hosts=allowed_hosts),
        max_connections=1,
        max_keepalive_connections=0,
    )
    return transport


def _public_dns(host: str) -> bool:
    _public_addresses(host, 443)
    return True


def _certificate_failure(exc: Exception) -> bool:
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, ssl.SSLCertVerificationError):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def bounded_extract(source_url: str, *, normalize, identity, parse, classify_access, login_destination,
                    allowed_hosts, decode=None, mismatch_reason="OFFER_MISMATCH",
                    analysis_mode: str = "ACCOUNT_PUBLIC",
                 client: httpx.Client | None = None, dns_check=_public_dns,
                 clock=time.monotonic, sleep=time.sleep) -> dict:
    try:
        source_url = normalize(source_url)
    except ValueError:
        return {"source_url": source_url, "extraction_status": "UNSUPPORTED_PAGE", "reason": "INVALID_URL"}
    deadline = clock() + FETCH_BUDGET_SECONDS

    def outcome(status, reason):
        return {"source_url": source_url, "extraction_status": status, "reason": reason}

    owns_client = client is None
    if client is None:
        client = httpx.Client(transport=_public_transport(deadline=deadline, clock=clock, allowed_hosts=allowed_hosts),
                              follow_redirects=False, trust_env=False,
                              timeout=httpx.Timeout(10.0, connect=5.0),
                              headers={"User-Agent": "VCTConnectPublicEvidence/1.0", "Accept": "text/html"})
    try:
        current = source_url
        redirects = retries = 0
        seen_redirects = {source_url}
        while True:
            transient = None
            try:
                if clock() >= deadline:
                    return outcome("TIMEOUT", "HTTP_TIMEOUT")
                if not dns_check(urlsplit(current).hostname):
                    return outcome("BLOCKED", "UNSAFE_DESTINATION")
                remaining = deadline - clock()
                if remaining <= 0:
                    return outcome("TIMEOUT", "HTTP_TIMEOUT")
                timeout = httpx.Timeout(min(10.0, remaining), connect=min(5.0, remaining))
                with client.stream("GET", current, follow_redirects=False, timeout=timeout) as response:
                    if clock() >= deadline:
                        return outcome("TIMEOUT", "HTTP_TIMEOUT")
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location", "")
                        try:
                            target = urljoin(current, location)
                            if login_destination(target):
                                return outcome("AUTH_REQUIRED", "LOGIN_REQUIRED")
                            destination = normalize(target)
                        except ValueError:
                            return outcome("BLOCKED", "UNSAFE_REDIRECT")
                        if identity(destination) != identity(source_url):
                            return outcome("BLOCKED", mismatch_reason)
                        if destination in seen_redirects:
                            return outcome("BLOCKED", "REDIRECT_LOOP")
                        if redirects >= MAX_REDIRECTS:
                            return outcome("BLOCKED", "REDIRECT_LIMIT")
                        redirects += 1
                        seen_redirects.add(destination)
                        current = destination
                        continue
                    if response.status_code == 401:
                        return outcome("AUTH_REQUIRED", "LOGIN_REQUIRED")
                    if response.status_code in (403, 429):
                        return outcome("BLOCKED", "ACCESS_CHALLENGE")
                    is_transient = response.status_code in TRANSIENT_HTTP_STATUSES
                    if response.status_code != 200 and not is_transient:
                        status = "UNSUPPORTED_PAGE" if response.status_code in (404, 410) else "PARSE_FAILED"
                        return outcome(status, "HTTP_ERROR")
                    is_html = response.headers.get("content-type", "").split(";", 1)[0].strip().lower() == "text/html"
                    if not is_html:
                        if not is_transient:
                            return outcome("PARSE_FAILED", "NON_HTML")
                        transient = ("PARSE_FAILED", "UPSTREAM_UNAVAILABLE")
                    else:
                        content = bytearray()
                        chunks = iter(response.iter_bytes())
                        while True:
                            if clock() >= deadline:
                                return outcome("TIMEOUT", "HTTP_TIMEOUT")
                            try:
                                chunk = next(chunks)
                            except StopIteration:
                                break
                            if clock() >= deadline:
                                return outcome("TIMEOUT", "HTTP_TIMEOUT")
                            if len(chunk) > MAX_HTML_BYTES - len(content):
                                return outcome("PARSE_FAILED", "PAGE_TOO_LARGE")
                            content.extend(chunk)
                        if clock() >= deadline:
                            return outcome("TIMEOUT", "HTTP_TIMEOUT")
                        html = decode(bytes(content), response) if decode else content.decode(response.encoding or "utf-8", errors="replace")
                        if is_transient:
                            access = classify_access(html)
                            if access:
                                return outcome(*access)
                            transient = ("PARSE_FAILED", "UPSTREAM_UNAVAILABLE")
                        else:
                            result = parse(html, source_url, analysis_mode=analysis_mode, page_bytes=bytes(content))
                            return outcome("TIMEOUT", "HTTP_TIMEOUT") if clock() >= deadline else result
            except UnsafeDestination:
                return outcome("BLOCKED", "UNSAFE_DESTINATION")
            except DNSResolutionFailed:
                return outcome("PARSE_FAILED", "DNS_ERROR")
            except httpx.TimeoutException:
                transient = ("TIMEOUT", "HTTP_TIMEOUT")
            except TemporaryDNSFailure:
                transient = ("PARSE_FAILED", "DNS_ERROR")
            except httpx.RemoteProtocolError as exc:
                if str(exc).startswith("Invalid URL in location header:"):
                    return outcome("BLOCKED", "UNSAFE_REDIRECT")
                transient = ("PARSE_FAILED", "HTTP_ERROR")
            except httpx.NetworkError as exc:
                if _certificate_failure(exc):
                    return outcome("PARSE_FAILED", "HTTP_ERROR")
                transient = ("PARSE_FAILED", "HTTP_ERROR")
            except (httpx.HTTPError, UnicodeError, LookupError):
                return outcome("PARSE_FAILED", "HTTP_ERROR")
            # The response context has closed before a retry or backoff. Each
            # attempt starts with a fresh body; failed stream bytes are discarded.
            remaining = deadline - clock()
            if remaining <= 0:
                return outcome("TIMEOUT", "HTTP_TIMEOUT")
            if retries >= len(RETRY_DELAYS):
                return outcome(*transient)
            delay = RETRY_DELAYS[retries]
            if remaining <= delay:
                return outcome("TIMEOUT", "HTTP_TIMEOUT")
            sleep(delay)
            retries += 1
    finally:
        if owns_client:
            client.close()
