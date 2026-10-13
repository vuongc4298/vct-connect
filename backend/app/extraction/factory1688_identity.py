"""Canonical identity for named and b2b 1688 factory profiles."""
import re
from urllib.parse import parse_qs, urlsplit

MEMBER = r"[a-z0-9][a-z0-9_-]{0,62}[a-z0-9]"


def factory_identity(value):
    p = urlsplit(value)
    if p.scheme != "https" or p.username or p.password or p.port:
        raise ValueError("Unsupported factory link")
    member = None
    if p.netloc == "sale.1688.com" and p.path == "/factory/card.html":
        query = parse_qs(p.query, keep_blank_values=True)
        ids = query.get("memberId", [])
        if len(ids) == 1 and query.get("facMemId", []) in ([], ids):
            member = ids[0]
    elif p.netloc == "www.1688.com":
        match = re.fullmatch(r"/factory/(" + MEMBER + r")\.html", p.path)
        member = match[1] if match else None
    if not member or not re.fullmatch(MEMBER, member):
        raise ValueError("Unsupported factory member identity")
    return f"https://www.1688.com/factory/{member}.html"
