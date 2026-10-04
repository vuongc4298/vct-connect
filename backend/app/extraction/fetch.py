"""Shared bounded public HTTP transport; adapters supply identity and parsing policies."""
import ipaddress
import socket
import ssl
import time
import zlib
from http.cookiejar import CookieJar, DefaultCookiePolicy
from urllib.parse import urljoin, urlsplit
import certifi
import httpcore
import httpx

MAX_HTML_BYTES = 2_000_000
# A single unretained sentinel distinguishes an exact-cap page from overflow.
MAX_DECODED_BYTES = MAX_HTML_BYTES + 1
MAX_REDIRECTS = 3
FETCH_BUDGET_SECONDS = 25
RETRY_DELAYS = (0.5, 1.0)
TRANSIENT_HTTP_STATUSES = {500, 502, 503, 504}
DECODE_CHUNK_BYTES = 64 * 1024
# Deflate has no reliable wire marker: raw stored blocks can resemble zlib.
# Retain at most this much initial wire data until wrapped output is accepted.
DEFLATE_REPLAY_BYTES = 64 * 1024


class PageTooLarge(Exception):
    """Decoded response exceeds the shared page capacity."""


def _bounded_response_bytes(response, *, deadline, clock):
    """Decode wire bytes with a bounded zlib output buffer before retaining them.

    A single overflow byte distinguishes an exact-cap body from a larger one.
    It is never retained or passed to a parser. No unbounded decoder flush is
    used: EOF and checksums must be reached by bounded decompress calls.
    """
    encoding = response.headers.get("content-encoding", "identity").strip().lower()
    if encoding not in {"identity", "gzip", "deflate"}:
        raise httpx.DecodingError("Unsupported content encoding")

    def check_deadline():
        if clock() >= deadline:
            raise httpx.ReadTimeout("Extraction deadline elapsed")

    # HTTPX response constructors and pre-read MockTransport responses already
    # decoded their content. iter_raw would raise StreamConsumed and decoding
    # again would corrupt it. Check the existing bytes without copying them.
    if response.is_stream_consumed:
        check_deadline()
        content = response.content
        if len(content) > MAX_HTML_BYTES:
            raise PageTooLarge
        return content

    content = bytearray()
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == "gzip" else None
    replay = bytearray()
    wrapped_pending = encoding == "deflate"
    chunks = iter(response.iter_raw())
    while True:
        check_deadline()
        try:
            chunk = next(chunks)
        except StopIteration:
            break
        check_deadline()
        if not chunk:
            continue
        if encoding == "identity":
            if len(chunk) > MAX_HTML_BYTES - len(content):
                raise PageTooLarge
            content.extend(chunk)
            continue
        if encoding == "deflate" and decoder is None:
            decoder = zlib.decompressobj(zlib.MAX_WBITS)
        while chunk:
            check_deadline()
            if decoder.eof:
                if encoding != "gzip":
                    raise httpx.DecodingError("Trailing compressed data")
                # RFC gzip members concatenate their decoded bytes; all
                # members spend the same page budget.
                decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
            maximum = min(DECODE_CHUNK_BYTES, MAX_DECODED_BYTES - len(content))
            remainder = b""
            if wrapped_pending:
                # Split before copying so a large transport chunk cannot grow
                # the replay buffer beyond its independent wire capacity.
                capacity = DEFLATE_REPLAY_BYTES - len(replay)
                if capacity == 0:
                    raise httpx.DecodingError("Deflate format undecided within replay capacity")
                remainder = chunk[capacity:]
                chunk = chunk[:capacity]
                replay.extend(chunk)
            try:
                output = decoder.decompress(chunk, maximum)
            except zlib.error:
                if not wrapped_pending:
                    raise
                # HTTPX-compatible first-decode fallback, including a valid raw
                # stream with a plausible zlib header. Once any wrapped output
                # was accepted (or wrapped EOF reached), never retry corruption.
                decoder = zlib.decompressobj(-zlib.MAX_WBITS)
                wrapped_pending = False
                chunk = bytes(replay)
                replay.clear()
                output = decoder.decompress(chunk, maximum)
            check_deadline()
            if len(output) > MAX_HTML_BYTES - len(content):
                raise PageTooLarge
            content.extend(output)
            if wrapped_pending and (output or decoder.eof):
                wrapped_pending = False
                replay.clear()
            del output
            chunk = (decoder.unused_data if decoder.eof else decoder.unconsumed_tail) + remainder
    check_deadline()
    if encoding != "identity" and (decoder is None or not decoder.eof):
        raise httpx.DecodingError("Incomplete compressed response")
    return bytes(content)


class UnsafeDestination(OSError):
    """DNS did not resolve only to public addresses for the approved host."""


class TemporaryDNSFailure(OSError):
    """A resolver failure that may recover within the extraction budget."""


class DNSResolutionFailed(OSError):
    """A permanent resolver failure, without exposing resolver details."""


class _RejectCookies(DefaultCookiePolicy):
    """Anonymous adapters can decline source cookies, including redirect state."""

    def set_ok(self, cookie, request):
        return False

    def return_ok(self, cookie, request):
        return False


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
                    accept_cookies=True, browser_fallback=False, browser_renderer=None,
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
                              cookies=None if accept_cookies else CookieJar(policy=_RejectCookies()),
                              timeout=httpx.Timeout(10.0, connect=5.0),
                              headers={"User-Agent": "VCTConnectPublicEvidence/1.0", "Accept": "text/html",
                                       "Accept-Encoding": "gzip, deflate"})
    if not accept_cookies:
        client.cookies.clear()
        client.cookies.jar.set_policy(_RejectCookies())
        client.headers.pop('cookie', None)
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
                        content = _bounded_response_bytes(response, deadline=deadline, clock=clock)
                        if clock() >= deadline:
                            return outcome("TIMEOUT", "HTTP_TIMEOUT")
                        html = decode(content, response) if decode else content.decode(response.encoding or "utf-8", errors="replace")
                        if is_transient:
                            access = classify_access(html)
                            if access:
                                return outcome(*access)
                            transient = ("PARSE_FAILED", "UPSTREAM_UNAVAILABLE")
                        else:
                            result = parse(html, source_url, analysis_mode=analysis_mode, page_bytes=content)
                            if clock() >= deadline:
                                return outcome("TIMEOUT", "HTTP_TIMEOUT")
                            from .browser import maybe_render
                            return maybe_render(result, html, content, enabled=browser_fallback,
                                                csp=response.headers.get_list("content-security-policy"),
                                                renderer=browser_renderer)
            except PageTooLarge:
                return outcome("PARSE_FAILED", "PAGE_TOO_LARGE")
            except zlib.error:
                return outcome("PARSE_FAILED", "HTTP_ERROR")
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
