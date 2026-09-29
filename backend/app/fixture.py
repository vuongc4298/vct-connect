from urllib.parse import urlparse
import re

FIXTURE_URL = "https://detail.1688.com/offer/123456789012.html"


def validate_fixture_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "detail.1688.com"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or not re.fullmatch(r"/offer/[0-9]+\.html", parsed.path)
        or parsed.query
        or parsed.fragment
        or value != FIXTURE_URL
    ):
        raise ValueError(f"Only the developer fixture URL is supported: {FIXTURE_URL}")
    return value


def fixture_result(source_url: str) -> dict:
    return {"source_url": source_url, "supplier_name": "Developer Fixture Supplier", "fixture": True}
