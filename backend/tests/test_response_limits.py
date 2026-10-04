"""Independent transport regressions: inspect output allocations, not just rejection."""
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import gzip
import zlib

import httpx
import pytest

from backend.app.extraction import (
    extract_1688, extract_taobao, extract_alibaba,
    parse_1688_page, parse_taobao_page, parse_alibaba_page,
)
from backend.app.extraction import fetch


URL = "https://detail.1688.com/offer/996518024136.html"
HTML = (f'<link rel="canonical" href="{URL}">'
        '<div class="title-content"><h1>Dress</h1></div>').encode()
LAYOUTS = {
    "1688_offer": (extract_1688, parse_1688_page, "1688_offer_996518024136.html", URL),
    "taobao_item": (extract_taobao, parse_taobao_page, "taobao_item_1076425861755.html", "https://item.taobao.com/item.htm?id=1076425861755"),
    "taobao_shop": (extract_taobao, parse_taobao_page, "taobao_shop_159450000.html", "https://shop159450000.world.taobao.com/category.htm"),
    "alibaba_product": (extract_alibaba, parse_alibaba_page, "alibaba_product_1600147809763.html", "https://www.alibaba.com/product-detail/100-Cotton-180gsm-T-shirts-Men_1600147809763.html"),
    "alibaba_profile": (extract_alibaba, parse_alibaba_page, "alibaba_profile_dgxuandele.html", "https://dgxuandele.en.alibaba.com/company_profile.html"),
}


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 3, tzinfo=timezone.utc).astimezone(tz)


def encode(content, encoding):
    if encoding == "gzip":
        return gzip.compress(content)
    if encoding == "deflate":
        return zlib.compress(content)
    if encoding == "raw-deflate":
        compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        return compressor.compress(content) + compressor.flush()
    return content


class Stream(httpx.SyncByteStream):
    def __init__(self, chunks, before=None):
        self.chunks = chunks
        self.before = before or (lambda: None)
        self.closed = False
        self.reads = 0

    def __iter__(self):
        for chunk in self.chunks:
            self.before()
            self.reads += 1
            yield chunk

    def close(self):
        self.closed = True


def extract(stream, encoding="identity", **kwargs):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8",
                                           "content-encoding": encoding}, stream=stream)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True, **kwargs)
    return result, calls


@pytest.fixture
def allocations(monkeypatch):
    """Observe both HTTPX's old decoder and the replacement at the zlib boundary."""
    factory = zlib.decompressobj
    records = []

    class Observed:
        def __init__(self, *args, **kwargs):
            self.decoder = factory(*args, **kwargs)

        def decompress(self, data, max_length=0):
            output = self.decoder.decompress(data, max_length)
            records.append((max_length, len(output)))
            return output

        def flush(self, *args):
            output = self.decoder.flush(*args)
            records.append((0, len(output)))
            return output

        def __getattr__(self, name):
            return getattr(self.decoder, name)

    monkeypatch.setattr(zlib, "decompressobj", Observed)
    return records


@pytest.mark.parametrize("encoding", ["gzip", "deflate", "raw-deflate"])
@pytest.mark.parametrize("fragmented", [False, True])
def test_compressed_bomb_bounds_every_output_allocation_and_total(encoding, fragmented, allocations):
    wire = encode(b"x" * (fetch.MAX_HTML_BYTES * 16), encoding)
    chunks = [wire[i:i + 113] for i in range(0, len(wire), 113)] if fragmented else [wire]
    stream = Stream(chunks)
    result, calls = extract(stream, "deflate" if encoding == "raw-deflate" else encoding)
    assert result == {"source_url": URL, "extraction_status": "PARSE_FAILED", "reason": "PAGE_TOO_LARGE"}
    assert stream.closed and len(calls) == 1
    assert allocations
    # One overflow byte distinguishes an exact-cap page from one exceeding it.
    assert sum(size for _, size in allocations) <= fetch.MAX_DECODED_BYTES
    produced = 0
    for maximum, size in allocations:
        assert 0 < maximum <= min(65536, fetch.MAX_HTML_BYTES - produced + 1)
        assert size <= maximum
        produced += size


@pytest.mark.parametrize("encoding", ["identity", "gzip", "deflate", "raw-deflate"])
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_incremental_exact_capacity_and_one_byte_overflow(encoding, delta):
    body = HTML + b" " * (fetch.MAX_HTML_BYTES + delta - len(HTML))
    wire = encode(body, encoding)
    # Split headers and trailers as well as the compressed payload.
    stream = Stream([wire[i:i + 17] for i in range(0, len(wire), 17)])
    result, calls = extract(stream, "deflate" if encoding == "raw-deflate" else encoding)
    assert stream.closed and len(calls) == 1
    if delta > 0:
        assert result == {"source_url": URL, "extraction_status": "PARSE_FAILED", "reason": "PAGE_TOO_LARGE"}
    else:
        assert result["extraction_status"] == "PARTIAL"
        assert result["raw_payload"]["html_sha256"] == sha256(body).hexdigest()


@pytest.mark.parametrize("encoding", ["identity", "gzip", "deflate", "raw-deflate"])
@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("pre_read", [False, True])
def test_audited_pages_keep_selected_fields_and_decoded_hashes(layout, encoding, pre_read):
    extractor, parser, filename, url = LAYOUTS[layout]
    body = (Path(__file__).parent / "fixtures" / filename).read_bytes()
    wire = encode(body, encoding)
    headers = {"content-type": "text/html; charset=utf-8",
               "content-encoding": "deflate" if encoding == "raw-deflate" else encoding}
    with patch(parser.__module__ + ".datetime", FixedDatetime):
        byte_argument = {"uploaded_bytes": body} if layout == "1688_offer" else {"page_bytes": body}
        expected = parser(body.decode(), url, **byte_argument)

        def respond(_):
            if pre_read:
                return httpx.Response(200, headers=headers, content=wire)
            return httpx.Response(200, headers=headers,
                                  stream=Stream([wire[i:i + 101] for i in range(0, len(wire), 101)]))

        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            result = extractor(url, client=client, dns_check=lambda _: True)
    assert result == expected
    assert result["raw_payload"]["html_sha256"] == sha256(body).hexdigest()


@pytest.mark.parametrize(("encoding", "damage"), [
    (encoding, damage)
    for encoding in ("gzip", "deflate", "raw-deflate")
    for damage in ("invalid", "truncated", "junk")
] + [("gzip", "checksum"), ("deflate", "checksum")])
def test_malformed_compression_has_no_snapshot_or_retry(encoding, damage):
    wire = encode(HTML, encoding)
    if damage == "invalid":
        wire = b"not a compressed HTML page"
    elif damage == "truncated":
        wire = wire[:-1]
    elif damage == "junk":
        wire += b"junk"
    else:
        wire = wire[:-1] + bytes([wire[-1] ^ 255])
    stream = Stream([wire[:1], wire[1:]])
    result, calls = extract(stream, "deflate" if encoding == "raw-deflate" else encoding)
    assert result == {"source_url": URL, "extraction_status": "PARSE_FAILED", "reason": "HTTP_ERROR"}
    assert stream.closed and len(calls) == 1


@pytest.mark.parametrize("encoding", ["br", "zstd", "compress", "gzip, deflate", "identity, gzip"])
def test_unsupported_codings_fail_before_reading(encoding):
    stream = Stream([HTML])
    result, calls = extract(stream, encoding)
    assert result == {"source_url": URL, "extraction_status": "PARSE_FAILED", "reason": "HTTP_ERROR"}
    assert stream.closed and stream.reads == 0 and len(calls) == 1


def test_concatenated_gzip_members_share_one_budget(allocations):
    stream = Stream([gzip.compress(b"x" * (fetch.MAX_HTML_BYTES // 2)),
                     gzip.compress(b"y" * fetch.MAX_HTML_BYTES)])
    result, calls = extract(stream, "gzip")
    assert result["reason"] == "PAGE_TOO_LARGE" and len(calls) == 1 and stream.closed
    assert sum(size for _, size in allocations) <= fetch.MAX_HTML_BYTES + 1


def test_valid_concatenated_gzip_members_hash_complete_decoded_body():
    stream = Stream([gzip.compress(HTML[:45]), gzip.compress(HTML[45:])])
    result, _ = extract(stream, "gzip")
    assert result["extraction_status"] == "PARTIAL"
    assert result["raw_payload"]["html_sha256"] == sha256(HTML).hexdigest()


@pytest.mark.parametrize("fragment", [1, 2, 5, 17, 1000])
def test_raw_stored_block_with_zlib_header_replays_before_first_output(fragment, allocations):
    body = HTML + b" " * (156 - len(HTML))
    wire = b"\x78\x9c\x00\x63\xff" + body + b"\x01\x00\x00\xff\xff"
    assert zlib.decompress(wire, -zlib.MAX_WBITS) == body
    result, calls = extract(Stream([wire[i:i + fragment] for i in range(0, len(wire), fragment)]), "deflate")
    assert result["extraction_status"] == "PARTIAL" and len(calls) == 1
    assert result["raw_payload"]["html_sha256"] == sha256(body).hexdigest()
    assert sum(size for _, size in allocations) <= fetch.MAX_DECODED_BYTES
    assert all(0 < maximum <= fetch.DECODE_CHUNK_BYTES and size <= maximum for maximum, size in allocations)


def test_wrapped_checksum_failure_after_accepted_output_never_replays(monkeypatch):
    factory = zlib.decompressobj
    modes = []
    def observed(mode):
        modes.append(mode)
        return factory(mode)
    monkeypatch.setattr(zlib, "decompressobj", observed)
    wire = zlib.compress(HTML)
    result, calls = extract(Stream([wire[:-4], b"\0\0\0\0"]), "deflate")
    assert result == {"source_url": URL, "extraction_status": "PARSE_FAILED", "reason": "HTTP_ERROR"}
    assert modes == [zlib.MAX_WBITS] and len(calls) == 1


def test_deflate_undecided_wire_replay_has_explicit_capacity():
    # Arbitrarily many empty nonfinal stored blocks are valid, but retaining
    # an unbounded undecided prefix is outside the bounded fallback boundary.
    wire = b"\x78\x9c" + b"\x00\x00\x00\xff\xff" * (fetch.DEFLATE_REPLAY_BYTES // 5 + 1)
    stream = Stream([wire, b"unread"])
    result, calls = extract(stream, "deflate")
    assert result == {"source_url": URL, "extraction_status": "PARSE_FAILED", "reason": "HTTP_ERROR"}
    assert stream.reads == 1 and stream.closed and len(calls) == 1


def test_decoding_checks_deadline_between_output_chunks(monkeypatch, allocations):
    now = [0.0]
    factory = zlib.decompressobj

    class Slow:
        def __init__(self, *args, **kwargs):
            self.decoder = factory(*args, **kwargs)

        def decompress(self, *args, **kwargs):
            result = self.decoder.decompress(*args, **kwargs)
            now[0] += 26
            return result

        def __getattr__(self, name):
            return getattr(self.decoder, name)

    monkeypatch.setattr(zlib, "decompressobj", Slow)
    stream = Stream([gzip.compress(HTML + b" " * 100000)])
    result, calls = extract(stream, "gzip", clock=lambda: now[0], sleep=lambda _: pytest.fail("no retry"))
    assert result == {"source_url": URL, "extraction_status": "TIMEOUT", "reason": "HTTP_TIMEOUT"}
    assert len(calls) == 1 and stream.closed and len(allocations) == 1


@pytest.mark.parametrize("encoding", ["gzip", "deflate"])
@pytest.mark.parametrize("layout", LAYOUTS)
def test_size_rejection_never_parses_or_starts_browser(layout, encoding):
    extractor, parser, _, url = LAYOUTS[layout]
    stream = Stream([encode(HTML + b" " * fetch.MAX_HTML_BYTES, encoding)])
    with patch(parser.__module__ + "." + parser.__name__, side_effect=AssertionError("must not parse")):
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
                200, headers={"content-type": "text/html", "content-encoding": encoding}, stream=stream))) as client:
            result = extractor(url, client=client, dns_check=lambda _: True, browser_fallback=True,
                               browser_renderer=lambda *_: pytest.fail("must not render"))
    assert result == {"source_url": url, "extraction_status": "PARSE_FAILED", "reason": "PAGE_TOO_LARGE"}
    assert stream.closed


@pytest.mark.parametrize("encoding", ["gzip", "deflate", "raw-deflate"])
@pytest.mark.parametrize("charset", ["meta", "mime"])
def test_compressed_taobao_preserves_gbk_fields_and_response_byte_hash(encoding, charset):
    _, parser, filename, url = LAYOUTS["taobao_shop"]
    html = (Path(__file__).parent / "fixtures" / filename).read_text(encoding="utf-8")
    html = html.replace('charset="utf-8"', 'charset="GBK"' if charset == "meta" else "")
    body = html.encode("gb18030")
    wire = encode(body, encoding)
    headers = {"content-type": "text/html" + ("; charset=GBK" if charset == "mime" else ""),
               "content-encoding": "deflate" if encoding == "raw-deflate" else encoding}
    with patch(parser.__module__ + ".datetime", FixedDatetime):
        expected = parser(html, url, page_bytes=body)
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
                200, headers=headers, stream=Stream([wire[:1], wire[1:]])))) as client:
            result = extract_taobao(url, client=client, dns_check=lambda _: True)
    assert result == expected
    assert result["supplier_data"]["supplier_name"] == "心相印维达生活馆"
    assert result["raw_payload"]["html_sha256"] == sha256(body).hexdigest()


@pytest.mark.parametrize("encoding", ["gzip", "deflate"])
def test_compressed_retry_discards_partial_body_and_closes_before_backoff(encoding):
    wire = encode(HTML, encoding)

    def partial():
        yield wire[:-1]
        raise httpx.ReadError("source diagnostic must not escape")

    streams = [Stream(partial()), Stream([wire])]
    calls, delays = [], []

    def respond(request):
        stream = streams[len(calls)]
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "text/html", "content-encoding": encoding}, stream=stream)

    def sleep(delay):
        assert streams[0].closed
        delays.append(delay)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True, sleep=sleep)
    assert result["extraction_status"] == "PARTIAL"
    assert result["raw_payload"]["html_sha256"] == sha256(HTML).hexdigest()
    assert delays == [0.5] and len(calls) == 2 and all(stream.closed for stream in streams)


@pytest.mark.parametrize("encoding", ["gzip", "deflate"])
@pytest.mark.parametrize("status", [200, 503])
@pytest.mark.parametrize(("html", "status_name", "reason"), [
    (b"<title>Captcha</title>", "BLOCKED", "ACCESS_CHALLENGE"),
    (b"<title>Login required</title>", "AUTH_REQUIRED", "LOGIN_REQUIRED"),
])
def test_compressed_access_walls_keep_finite_outcomes_without_retries(encoding, status, html, status_name, reason):
    stream = Stream([encode(html, encoding)])
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
            status, headers={"content-type": "text/html", "content-encoding": encoding}, stream=stream))) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True,
                              sleep=lambda _: pytest.fail("must not retry access wall"))
    assert result == {"source_url": URL, "extraction_status": status_name, "reason": reason}
    assert stream.closed


@pytest.mark.parametrize('layout', ['1688_offer', 'taobao_item', 'alibaba_product'])
@pytest.mark.parametrize('preferred', ['gzip', 'deflate'])
def test_default_client_negotiates_only_supported_compression_and_preserves_selected_evidence(monkeypatch, layout, preferred):
    adapter, parser, filename, url = LAYOUTS[layout]
    body = (Path(__file__).parent / 'fixtures' / filename).read_bytes()
    requests, streams = [], []
    def respond(request):
        requests.append(request)
        advertised = {value.strip() for value in request.headers['accept-encoding'].split(',')}
        # Select from the real outgoing header; advertising an unsupported
        # encoding changes the response and must fail this production-path gate.
        encoding = next((value for value in ('br', 'zstd', preferred, 'gzip', 'deflate') if value in advertised), 'identity')
        stream = Stream([encode(body, encoding)])
        streams.append(stream)
        return httpx.Response(200, headers={'content-type': 'text/html; charset=utf-8',
                                          'content-encoding': encoding}, stream=stream)
    monkeypatch.setattr(fetch, '_public_transport', lambda **kwargs: httpx.MockTransport(respond))
    with patch(parser.__module__ + '.datetime', FixedDatetime):
        byte_argument = {'uploaded_bytes': body} if layout == '1688_offer' else {'page_bytes': body}
        expected = parser(body.decode('utf-8'), url, **byte_argument)
        result = adapter(url, dns_check=lambda _: True)
    assert len(requests) == 1
    assert {value.strip() for value in requests[0].headers['accept-encoding'].split(',')} == {'gzip', 'deflate'}
    assert result == expected
    assert result['raw_payload']['html_sha256'] == sha256(body).hexdigest()
    assert all(stream.closed for stream in streams)
