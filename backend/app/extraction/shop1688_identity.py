"""Identity validation for linked shop claims; this never fetches a URL."""
import re
from urllib.parse import urlsplit

RESERVED = {"www", "m", "detail", "sale", "login", "passport", "auth", "accounts",
            "cart", "trade", "air", "work", "systemjs", "mindx", "member", "open",
            "api", "h5", "cbu", "service", "help", "search", "s", "buy", "offer"}


def shop_host(host):
    match = re.fullmatch(r"([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.1688\.com", host)
    return bool(match and match[1] not in RESERVED)


def shop_identity(value):
    p = urlsplit(value)
    if (p.scheme != "https" or p.username or p.password or p.port or
            not shop_host(p.netloc) or p.path not in {"", "/"}):
        raise ValueError("Unsupported supplier shop link")
    return f"https://{p.netloc}/"
