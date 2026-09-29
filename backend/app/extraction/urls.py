"""Strict, canonical 1688 offer URLs used at admission and every fetch hop."""

import re
from urllib.parse import urlsplit

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
