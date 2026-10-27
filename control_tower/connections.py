"""Connector plans and bounded read observations; never grants access or calls APIs.

Hashes check record integrity, not authenticity. A trusted collector must supply
observations from real connector responses. Even a fresh observation describes a
past read and does not establish current availability or permission to write.
"""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import re
from control_tower.validation import json_record_errors, valid_https_url

CONNECTORS = {
    "chatgpt": {"purpose": "reviewed manual assistant handoffs", "status": "unverified", "write_gate": "owner_review"},
    "openai": {"purpose": "separately configured API assistant work", "status": "unverified", "write_gate": "owner_review"},
    "youtube": {"purpose": "video draft and attribution planning", "status": "unverified", "write_gate": "owner_review"},
    "github": {"purpose": "repository QA and PR reviews", "status": "unverified", "write_gate": "owner_review"},
    "hostinger": {"purpose": "landing pages and membership forms", "status": "unverified", "write_gate": "owner_review"},
    "gemini": {"purpose": "cross-model research", "status": "unverified", "write_gate": "owner_review"},
    "claude": {"purpose": "coding and independent review", "status": "unverified", "write_gate": "owner_review"},
    "facebook": {"purpose": "consented promotion", "status": "unverified", "write_gate": "owner_review"},
    "instagram": {"purpose": "consented promotion", "status": "unverified", "write_gate": "owner_review"},
    "threads": {"purpose": "consented promotion", "status": "unverified", "write_gate": "owner_review"},
    "linkedin": {"purpose": "consented outreach and attribution", "status": "unverified", "write_gate": "owner_review"},
    "substack": {"purpose": "newsletter and membership referrals", "status": "unverified", "write_gate": "owner_review"},
    "slack": {"purpose": "reviewed internal mission handoffs", "status": "unverified", "write_gate": "owner_review"},
    "zapier": {"purpose": "reviewed workflow and approval planning", "status": "unverified", "write_gate": "owner_review"},
    "claude-cowork": {"purpose": "workspace file and project draft collaboration", "status": "unverified", "write_gate": "owner_review"},
    "perplexity": {"purpose": "source discovery and research handoffs", "status": "unverified", "write_gate": "owner_review"},
    "hubspot": {"purpose": "consented CRM routing", "status": "unverified", "write_gate": "owner_review"},
    "airtable": {"purpose": "project and evidence records", "status": "unverified", "write_gate": "owner_review"},
}


def _digest(record):
    return sha256(json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _time(value):
    if not isinstance(value, str):
        raise ValueError("observation time must be text")
    try:
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid observation time") from None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("observation time must include timezone")
    return value


def read_observation(connector, *, observed_at, evidence_url, response_sha256, scope, source_revision):
    """Package a successful read's metadata; caller must retain the real response."""
    if not isinstance(connector, str) or connector not in CONNECTORS:
        raise ValueError("unknown connector")
    _time(observed_at)
    if not valid_https_url(evidence_url):
        raise ValueError("invalid evidence URL")
    if not isinstance(response_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", response_sha256):
        raise ValueError("invalid response digest")
    if not isinstance(scope, str) or not scope.strip() or len(scope) > 160:
        raise ValueError("invalid observation scope")
    if not isinstance(source_revision, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", source_revision):
        raise ValueError("invalid source revision")
    record = {"connector": connector, "operation": "read", "observed_at": observed_at,
              "evidence_url": evidence_url, "response_sha256": response_sha256,
              "scope": scope, "source_revision": source_revision}
    return {**record, "record_sha256": _digest(record)}


def connector_report(observations=(), *, now=None, max_age_hours=24):
    """Show recent recorded reads without turning them into live connection claims."""
    if not isinstance(observations, (list, tuple)) or len(observations) > 100:
        raise ValueError("at most 100 observations are accepted")
    if type(max_age_hours) is not int or not 1 <= max_age_hours <= 168:
        raise ValueError("invalid observation freshness window")
    now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("current time must include timezone")
    result = {name: {**details, "runtime_available": "unknown"}
              for name, details in sorted(CONNECTORS.items())}
    parsed = []
    for observation in observations:
        if json_record_errors(observation):
            raise ValueError("invalid observation record")
        expected_keys = {"connector", "operation", "observed_at", "evidence_url", "response_sha256",
                         "scope", "source_revision", "record_sha256"}
        if set(observation) != expected_keys or observation.get("operation") != "read":
            raise ValueError("unexpected observation fields or operation")
        expected = read_observation(observation["connector"], **{
            key: observation[key] for key in ("observed_at", "evidence_url", "response_sha256", "scope", "source_revision")})
        if expected != observation:
            raise ValueError("observation integrity mismatch")
        observed = _time(observation["observed_at"])
        if observed > now + timedelta(minutes=5):
            raise ValueError("observation is in the future")
        parsed.append((observed, observation))
    for observed, observation in sorted(parsed, key=lambda item: item[0]):
        row = result[observation["connector"]]
        row.update({"last_observation": dict(observation), "observation_verification": "integrity_only",
                    "status": "read_observed" if now - observed <= timedelta(hours=max_age_hours) else "unverified"})
    return result
