"""Strict canonical source URLs used at admission and every fetch hop."""

import re
from urllib.parse import parse_qsl, urlsplit

_OFFER_PATH = re.compile(r"/offer/([0-9]{6,20})\.html")


def normalize_1688_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048 or value != value.strip():
        raise ValueError("A valid HTTPS 1688 offer URL is required")
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme == "https"
            and parsed.netloc == "detail.1688.com"
            and parsed.username is None
            and parsed.password is None
            and parsed.fragment == ""
            and _OFFER_PATH.fullmatch(parsed.path) is not None
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("A valid HTTPS 1688 offer URL is required")
    # Tracking parameters are not evidence and must never reach the fetcher.
    return f"https://detail.1688.com{parsed.path}"


def offer_id(value: str) -> str:
    return _OFFER_PATH.fullmatch(urlsplit(normalize_1688_url(value)).path).group(1)


_SHOP_HOST = re.compile(r"shop([1-9][0-9]{0,19})\.(?:world\.)?taobao\.com")
_NUMERIC_ID = re.compile(r"[1-9][0-9]{0,19}")


def normalize_taobao_url(value: str) -> str:
    """Only audited product and numeric shop forms; never expand short links."""
    if not isinstance(value, str) or len(value) > 2048 or value != value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError("A supported HTTPS Taobao product or shop URL is required")
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.fragment or parsed.username or parsed.password:
            raise ValueError
        if parsed.netloc == "item.taobao.com" and parsed.path == "/item.htm":
            ids = [v for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k == "id"]
            if len(ids) != 1 or not _NUMERIC_ID.fullmatch(ids[0]):
                raise ValueError
            return f"https://item.taobao.com/item.htm?id={ids[0]}"
        if _SHOP_HOST.fullmatch(parsed.netloc) and parsed.path in {"/", "/index.htm", "/category.htm"}:
            return f"https://{parsed.netloc}{parsed.path}"
    except ValueError:
        pass
    raise ValueError("A supported HTTPS Taobao product or shop URL is required")


def taobao_identity(value: str) -> tuple[str, str]:
    parsed = urlsplit(normalize_taobao_url(value))
    if parsed.netloc == "item.taobao.com":
        return "item", parse_qsl(parsed.query)[0][1]
    return "shop", _SHOP_HOST.fullmatch(parsed.netloc).group(1)


def normalize_source_url(value: str) -> str:
    try:
        return normalize_1688_url(value)
    except ValueError:
        return normalize_taobao_url(value)


def source_platform(value: str) -> str:
    canonical = normalize_source_url(value)
    return "1688" if urlsplit(canonical).netloc == "detail.1688.com" else "TAOBAO"
