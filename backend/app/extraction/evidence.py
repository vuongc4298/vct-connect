"""Generic selected-evidence readers and JSON persistence validation."""
import math


class MalformedPage(ValueError):
    """An observed embedded structure cannot safely supply evidence."""


def validate_json_evidence(value):
    """Reject source values that PostgreSQL JSONB cannot retain."""
    if isinstance(value, str):
        if "\x00" in value:
            raise MalformedPage
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise MalformedPage from exc
    elif isinstance(value, float) and not math.isfinite(value):
        raise MalformedPage
    elif isinstance(value, dict):
        for key, item in value.items():
            validate_json_evidence(key)
            validate_json_evidence(item)
    elif isinstance(value, list):
        for item in value:
            validate_json_evidence(item)


def field(model: dict, *path):
    value = model
    for key in path:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise MalformedPage
        value = value.get(key)
    return value


def object(value) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise MalformedPage
    return value


def string(value) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if value is not None:
        raise MalformedPage
    return None


def text(node) -> str | None:
    if node is None:
        return None
    value = node.text(strip=True)
    return value or None
