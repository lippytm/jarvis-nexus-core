"""Connector plans and bounded read observations; never grants access or calls APIs.

Hashes check record integrity, not authenticity. A trusted collector must supply
observations from real connector responses. Even a fresh observation describes a
past read and does not establish current availability or permission to write.
"""
from datetime import datetime, timezone, timedelta
from copy import deepcopy
from hashlib import sha256
import json
import re
from control_tower.validation import json_record_errors, valid_https_url
from control_tower.network_contract import PROJECTS, TARGETS, require_identifier, require_record

CONNECTORS = {
    "chatgpt": {"purpose": "reviewed manual assistant handoffs", "status": "unverified", "write_gate": "owner_review"},
    "openai": {"purpose": "separately configured API assistant work", "status": "unverified", "write_gate": "owner_review"},
    "youtube": {"purpose": "video draft and attribution planning", "status": "unverified", "write_gate": "owner_review"},
    "codex": {"purpose": "AI Building AI coding, diagnostics and evidence-producing development", "status": "unverified", "write_gate": "owner_review"},
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


def _github_repository(repository):
    if (not isinstance(repository, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", repository)
            or repository.rsplit("/", 1)[1] in {".", ".."}):
        raise ValueError("invalid declared GitHub repository")


def validate_destination_registry(registry):
    """Validate a supplied private configuration snapshot, never its authority.

    Keep this alongside existing connector contracts, outside strict v1 packets.
    A hosted collector must obtain the snapshot through authenticated storage.
    """
    require_record(registry, {"schema_version", "kind", "registry_id", "revision",
        "source_revision", "configuration_version", "visibility", "entries"})
    if (type(registry["schema_version"]) is not int or registry["schema_version"] != 1
        or registry["kind"] != "jarvis.destination_registry"
        or registry["visibility"] != "owner_private"):
        raise ValueError("unsupported or non-private destination registry")
    require_identifier(registry["registry_id"], "registry ID")
    require_identifier(registry["configuration_version"], "configuration version")
    if type(registry["revision"]) is not int or not 1 <= registry["revision"] <= 2147483647:
        raise ValueError("invalid registry revision")
    if not isinstance(registry["source_revision"], str) or not re.fullmatch(r"[a-f0-9]{40}", registry["source_revision"]):
        raise ValueError("registry requires an exact source revision")
    entries = registry["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 100:
        raise ValueError("registry requires one to 100 entries")
    seen = set()
    for entry in entries:
        require_record(entry, {"project_id", "platform", "destination_id", "resource_id", "allowed_actions"})
        if (not isinstance(entry["project_id"], str) or entry["project_id"] not in PROJECTS
            or not isinstance(entry["platform"], str) or entry["platform"] not in TARGETS
            or entry["allowed_actions"] != ["read"]):
            raise ValueError("invalid registry project, platform or read scope")
        require_identifier(entry["destination_id"], "destination ID")
        if entry["platform"] == "github":
            _github_repository(entry["resource_id"])
        else:
            require_identifier(entry["resource_id"], "opaque resource ID")
        key = (entry["project_id"], entry["platform"], entry["destination_id"])
        if key in seen:
            raise ValueError("duplicate registry destination scope")
        seen.add(key)
    return deepcopy(registry)


def verify_github_commit_response(content, observation, repository):
    """Check retained Git-data commit identity, not provider/collector authenticity."""
    if not isinstance(content, bytes) or len(content) > 65536:
        raise ValueError("commit response must be bounded bytes")
    _github_repository(repository)
    if not isinstance(observation, dict) or observation.get("connector") != "github":
        raise ValueError("commit response requires a GitHub observation")
    source = observation.get("source_revision")
    if not isinstance(source, str) or not re.fullmatch(r"[a-f0-9]{40}", source):
        raise ValueError("commit response requires an exact source SHA")
    expected_url = f"https://api.github.com/repos/{repository}/git/commits/{source}"
    if observation.get("evidence_url") != expected_url:
        raise ValueError("observation URL does not match declared commit resource")
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate commit response field")
            result[key] = value
        return result
    try:
        response = json.loads(content.decode("utf-8"), object_pairs_hook=unique_fields)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("invalid commit response JSON") from None
    if json_record_errors(response) or response.get("sha") != source or response.get("url") != expected_url:
        raise ValueError("response identity does not match declared commit resource")
    if sha256(content).hexdigest() != observation.get("response_sha256"):
        raise ValueError("retained response digest does not match observation")


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
