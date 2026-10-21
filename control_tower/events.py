"""Sandbox-only event contract for Jarvis Control Tower. No network, secrets, or writes."""
from datetime import datetime
from urllib.parse import urlparse

ALLOWED_TYPES = {
    "campaign_visit", "newsletter_optin", "member_signup",
    "affiliate_application", "funding_referral_click",
    "funding_partner_signup", "agent_proposal", "qa_result",
}
APPROVAL_STATES = {"not_required", "pending", "approved", "rejected"}
CONSENT_STATES = {"not_applicable", "opted_in", "opted_out"}
SENSITIVE_KEYS = {
    "ssn", "social_security_number", "credit_card", "card_number",
    "password", "api_key", "access_token", "secret", "credit_report",
}
REQUIRED = (
    "event_id", "event_type", "source", "occurred_at",
    "project_id", "consent_status", "approval_state",
)

def _valid_timestamp(text):
    if not isinstance(text, str):
        return False
    try:
        obj = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return obj.tzinfo is not None and obj.utcoffset() is not None
    except (TypeError, ValueError):
        return False

def validate_event(event):
    """Return a list of errors. Fail closed on malformed or sensitive records."""
    if not isinstance(event, dict):
        return ["event must be an object"]
    errors = [f"missing {key}" for key in REQUIRED if not event.get(key)]
    if event.get("event_type") not in ALLOWED_TYPES:
        errors.append("unsupported event_type")
    if event.get("consent_status") not in CONSENT_STATES:
        errors.append("invalid consent_status")
    if event.get("approval_state") not in APPROVAL_STATES:
        errors.append("invalid approval_state")
    if not _valid_timestamp(event.get("occurred_at")):
        errors.append("occurred_at must be timezone-aware ISO 8601")
    evidence_url = event.get("evidence_url")
    if evidence_url is not None:
        parsed = urlparse(evidence_url) if isinstance(evidence_url, str) else None
        if not parsed or parsed.scheme != "https" or not parsed.netloc:
            errors.append("evidence_url must be HTTPS")
    def scan(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower().replace("-", "_") in SENSITIVE_KEYS:
                    errors.append("disallowed sensitive field")
                scan(item)
        elif isinstance(value, list):
            for item in value:
                scan(item)
    scan(event)
    if event.get("event_type") in {"newsletter_optin", "member_signup", "affiliate_application"} and event.get("consent_status") != "opted_in":
        errors.append("explicit opt-in required")
    return errors

def ingest(event, seen_ids):
    """Pure-memory idempotent accept/reject helper, caller owns persistence."""
    errors = validate_event(event)
    if errors:
        return "rejected", errors
    if event["event_id"] in seen_ids:
        return "duplicate", []
    seen_ids.add(event["event_id"])
    return "accepted", []
