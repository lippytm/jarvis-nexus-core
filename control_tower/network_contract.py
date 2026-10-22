"""Portable draft contracts. Text and imported AI results are data, never commands."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat

from control_tower.validation import json_record_errors, valid_https_url

MAX_PACKET_BYTES = 65536
MAX_TEXT_BYTES = 20000
TARGETS = frozenset({"chatgpt", "openai", "gemini", "claude", "hostinger", "facebook",
                     "linkedin", "substack", "instagram", "threads", "youtube", "github"})
PROJECTS = {
    "ai-jarvis": "AI Jarvis engineering and coordination",
    "ai-evolutionary-evolutions": "Hostinger education and membership inquiries",
    "funding-affiliates": "Separate funding-customer and referral-partner journeys",
    "publishing-studio": "Source-backed books, audio, video and social drafts",
    "linux-education": "Programming and Linux learning materials",
    "robotics-research": "Simulation-first robotics research and education",
    "business-operations": "Business project records and operating checklists",
}


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError):
        raise ValueError("invalid canonical JSON") from None


def digest(value):
    return sha256(canonical(value)).hexdigest()


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_.-]{1,95}", value) is not None


def require_identifier(value, label="identifier"):
    if not identifier(value):
        raise ValueError("invalid " + label)


def require_digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("invalid SHA-256 digest")


def require_text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("text must be nonempty")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError:
        raise ValueError("text must be valid UTF-8") from None
    if size > MAX_TEXT_BYTES or any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise ValueError("text exceeds bounds or contains control characters")


def require_record(record, keys):
    if json_record_errors(record) or set(record) != set(keys):
        raise ValueError("unexpected or invalid record fields")
    if len(canonical(record)) > MAX_PACKET_BYTES:
        raise ValueError("packet exceeds 64 KiB")


def validate_draft(draft):
    require_record(draft, {"schema_version", "kind", "project_id", "target", "text"})
    if type(draft["schema_version"]) is not int or draft["schema_version"] != 1 or draft["kind"] != "jarvis.draft":
        raise ValueError("unsupported draft schema")
    if not isinstance(draft["project_id"], str) or draft["project_id"] not in PROJECTS:
        raise ValueError("unknown project")
    if not isinstance(draft["target"], str) or draft["target"] not in TARGETS:
        raise ValueError("unknown draft target")
    require_text(draft["text"])
    return deepcopy(draft)


def validate_return(packet):
    require_record(packet, {"schema_version", "kind", "return_id", "handoff_id",
                            "handoff_sha256", "source_provider", "text", "evidence_urls"})
    if type(packet["schema_version"]) is not int or packet["schema_version"] != 1 or packet["kind"] != "jarvis.return":
        raise ValueError("unsupported return schema")
    require_identifier(packet["return_id"], "return ID")
    require_identifier(packet["handoff_id"], "handoff ID")
    require_digest(packet["handoff_sha256"])
    if not isinstance(packet["source_provider"], str) or packet["source_provider"] not in TARGETS:
        raise ValueError("unknown claimed source provider")
    require_text(packet["text"])
    urls = packet["evidence_urls"]
    if not isinstance(urls, list) or len(urls) > 5 or any(not valid_https_url(u) for u in urls):
        raise ValueError("at most five HTTPS evidence URLs are accepted")
    return deepcopy(packet)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _invalid_constant(_):
    raise ValueError("nonfinite JSON value")


def load_packet(path):
    """Bound bytes before parsing; caller controls the local file path."""
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(Path(path), flags), "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("packet input must be a regular file")
        content = handle.read(MAX_PACKET_BYTES + 1)
    if len(content) > MAX_PACKET_BYTES:
        raise ValueError("packet exceeds 64 KiB")
    try:
        value = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=_invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("invalid JSON packet") from None
    if json_record_errors(value):
        raise ValueError("invalid JSON record")
    return value
