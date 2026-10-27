"""Bounded structural checks for offline JSON records; not a PII detector."""
import json
import re
from urllib.parse import urlsplit

SENSITIVE_FIELDS = frozenset({
    "ssn", "socialsecuritynumber", "creditcard", "cardnumber", "password",
    "apikey", "accesstoken", "refreshtoken", "secret", "creditreport",
    "authorization", "cookie", "privatekey",
})


def json_record_errors(record):
    """Reject non-JSON, oversized, deep, or known sensitive-field records.

    Only field names are inspected for sensitive data. A passing record may
    still contain personal data in ordinary strings and is not approved for
    production ingestion. Errors never echo field values.
    """
    if not isinstance(record, dict):
        return ["record must be an object"]
    try:
        encoded = json.dumps(record, allow_nan=False, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError):
        return ["record must be finite acyclic JSON"]
    if len(encoded) > 65536:
        return ["record exceeds 64 KiB"]
    errors, stack, nodes = [], [(record, 0)], 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if depth > 16 or nodes > 2048:
            return ["record structure limit exceeded"]
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str) or not key or len(key) > 128:
                    errors.append("object keys must be bounded nonempty strings")
                elif re.sub(r"[^a-z0-9]", "", key.lower()) in SENSITIVE_FIELDS:
                    errors.append("disallowed sensitive field")
                stack.append((item, depth + 1))
        elif isinstance(value, list):
            stack.extend((item, depth + 1) for item in value)
        elif value is not None and type(value) not in (str, int, float, bool):
            errors.append("unsupported JSON value")
    return list(dict.fromkeys(errors))


def valid_identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value) is not None


def valid_https_url(value):
    """Validate URL shape only; this neither fetches nor trusts the destination."""
    if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value):
        return False
    try:
        value.encode("utf-8")
        parsed = urlsplit(value)
        return bool(parsed.scheme == "https" and parsed.hostname and parsed.username is None
                    and parsed.password is None and parsed.port in (None, 443)
                    and "\\" not in value)
    except (ValueError, UnicodeError):
        return False
