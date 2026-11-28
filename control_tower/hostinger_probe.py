"""Read-only Hostinger Horizons inventory probe with an injected transport.

Endpoint/schema reviewed against Hostinger's official OpenAPI on 2026-10-22.
No default HTTP sender, credential discovery, logging, persistence or publishing.
The caller-supplied transport is trusted code and must enforce timeout, byte limit
and redirect policy before returning. Offline transports cannot prove live access.
"""
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import json
from urllib.parse import urlsplit


ENDPOINT = "https://developers.hostinger.com/api/horizons/v1/websites"
TIMEOUT_SECONDS = 5.0
MAX_RESPONSE_BYTES = 64 * 1024
_REQUIRED = {"website_id", "status", "created_at", "website_url"}
_OPTIONAL = {"description", "domain"}
_STATUSES = {"active", "suspended", "deleting", "deleted"}


@dataclass(frozen=True)
class PreparedRequest:
    """Fixed request descriptor; repr excludes the credential.

    Only the trusted transport should call headers_for_transport(). Never serialize
    this object using dataclasses.asdict(), log its internals, or persist headers.
    """
    _authorization: str = field(repr=False)
    method: str = field(default="GET", init=False)
    url: str = field(default=ENDPOINT, init=False)
    timeout_seconds: float = field(default=TIMEOUT_SECONDS, init=False)
    max_response_bytes: int = field(default=MAX_RESPONSE_BYTES, init=False)
    follow_redirects: bool = field(default=False, init=False)

    def headers_for_transport(self):
        return {"Authorization": self._authorization, "Accept": "application/json",
                "Content-Type": "application/json", "Accept-Encoding": "identity"}


@dataclass(frozen=True)
class ProbeResponse:
    """Transport result. Body and final URL are excluded from repr and all reports."""
    status_code: int
    body: bytes = field(repr=False)
    final_url: str = field(default=ENDPOINT, repr=False)
    redirect_count: int = 0
    content_type: str = "application/json"
    content_encoding: str = "identity"


def prepare_request(token):
    """Create a fixed GET descriptor without reading environment or making a call."""
    if (not isinstance(token, str) or not 1 <= len(token) <= 4096
            or any(ord(character) < 33 or ord(character) > 126 for character in token)):
        raise ValueError("invalid_token")
    return PreparedRequest("Bearer " + token)


def _result(status, *, reason=None, http_status=None, transport_calls=0):
    result = {"provider": "hostinger", "status": status, "connection_status": "unverified",
              "operation": "read_horizons_inventory", "requested_method": "GET",
              "writes_requested": 0, "transport_calls": transport_calls,
              "live_access_verified": False}
    if reason:
        result["reason"] = reason
    if http_status is not None:
        result["http_status"] = http_status
    return result


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonfinite_json_value")


def _valid_date(value):
    if not isinstance(value, str) or len(value) > 64:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except (ValueError, TypeError, OverflowError):
        return False


def _inventory_counts(value):
    if not isinstance(value, list) or len(value) > 1000:
        raise ValueError("unexpected_inventory_shape")
    counts = {status: 0 for status in sorted(_STATUSES)}
    ids = set()
    for row in value:
        if not isinstance(row, dict) or not _REQUIRED.issubset(row) or set(row) - (_REQUIRED | _OPTIONAL):
            raise ValueError("unexpected_inventory_shape")
        website_id = row["website_id"]
        if not isinstance(website_id, str) or not 1 <= len(website_id) <= 256 or website_id in ids:
            raise ValueError("invalid_or_duplicate_website_id")
        status = row["status"]
        if not isinstance(status, str) or status not in _STATUSES or not _valid_date(row["created_at"]):
            raise ValueError("unexpected_inventory_shape")
        website_url = row["website_url"]
        if not isinstance(website_url, str) or not 1 <= len(website_url) <= 2048:
            raise ValueError("unexpected_inventory_shape")
        parsed = urlsplit(website_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("unexpected_inventory_shape")
        for key in _OPTIONAL:
            if key in row and row[key] is not None and (not isinstance(row[key], str) or len(row[key]) > 4096):
                raise ValueError("unexpected_inventory_shape")
        ids.add(website_id)
        counts[status] += 1
    return counts


def probe(transport, token):
    """Request one read using trusted transport(request) -> ProbeResponse.

    No retries or redirects are requested. A valid response yields only an aggregate
    count, status counts and a digest. Success is response validation, not a claim
    that this package has authenticated a live account. A caller must separately
    establish the transport's provenance before making any connection observation.
    """
    try:
        request = prepare_request(token)
    except ValueError:
        return _result("invalid_configuration", reason="invalid_token")
    if not callable(transport):
        return _result("invalid_configuration", reason="transport_required")
    try:
        response = transport(request)
    except Exception:
        # Provider or transport errors may contain credentials or customer data.
        return _result("transport_error", reason="transport_failed", transport_calls=1)
    if not isinstance(response, ProbeResponse) or type(response.status_code) is not int or not 100 <= response.status_code <= 599:
        return _result("invalid_response", reason="invalid_transport_response", transport_calls=1)
    status = response.status_code
    if (type(response.redirect_count) is not int or response.redirect_count != 0
            or response.final_url != ENDPOINT or 300 <= status < 400):
        return _result("rejected", reason="redirects_forbidden", http_status=status, transport_calls=1)
    if status in {401, 403}:
        return _result("authorization_failed", http_status=status, transport_calls=1)
    if status == 429:
        return _result("rate_limited", http_status=status, transport_calls=1)
    if status != 200:
        return _result("provider_error", http_status=status, transport_calls=1)
    if (not isinstance(response.content_type, str)
            or response.content_type.split(";", 1)[0].strip().lower() != "application/json"
            or response.content_encoding not in ("identity", "")):
        return _result("invalid_response", reason="unsupported_content_type_or_encoding", transport_calls=1)
    if not isinstance(response.body, bytes) or len(response.body) > MAX_RESPONSE_BYTES:
        return _result("invalid_response", reason="body_type_or_size_limit", transport_calls=1)
    try:
        decoded = json.loads(response.body.decode("utf-8"), object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
        status_counts = _inventory_counts(decoded)
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        return _result("invalid_response", reason="invalid_json_or_inventory_schema", transport_calls=1)
    digest = sha256(response.body).hexdigest()
    result = _result("response_validated", http_status=200, transport_calls=1)
    result.update(website_count=len(decoded), website_status_counts=status_counts, response_sha256=digest,
                  observation={"connector": "hostinger", "operation": "read",
                               "endpoint": ENDPOINT, "response_sha256": digest,
                               "scope": "Horizons inventory schema and aggregate count only",
                               "provenance": "caller_supplied_transport_unverified",
                               "live_access_verified": False})
    return result
