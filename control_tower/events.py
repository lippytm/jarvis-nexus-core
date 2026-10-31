"""Sandbox-only event contract for Jarvis Control Tower. No network, secrets, or writes."""
from datetime import datetime
from control_tower.validation import json_record_errors, valid_https_url, valid_identifier

ALLOWED_TYPES = {
    "campaign_visit", "newsletter_optin", "member_signup",
    "affiliate_application", "funding_referral_click",
    "funding_partner_signup", "agent_proposal", "qa_result",
}
APPROVAL_STATES = {"not_required", "pending", "approved", "rejected"}
CONSENT_STATES = {"not_applicable", "opted_in", "opted_out"}
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
    shape_errors = json_record_errors(event)
    if shape_errors:
        return shape_errors
    errors = [f"missing {key}" for key in REQUIRED if not event.get(key)]
    for key in ("event_id", "source", "project_id"):
        if not valid_identifier(event.get(key)):
            errors.append(f"invalid {key}")
    if "utm_source" in event and not valid_identifier(event["utm_source"]):
        errors.append("invalid utm_source")
    if not isinstance(event.get("event_type"), str) or event.get("event_type") not in ALLOWED_TYPES:
        errors.append("unsupported event_type")
    if not isinstance(event.get("consent_status"), str) or event.get("consent_status") not in CONSENT_STATES:
        errors.append("invalid consent_status")
    if not isinstance(event.get("approval_state"), str) or event.get("approval_state") not in APPROVAL_STATES:
        errors.append("invalid approval_state")
    if not _valid_timestamp(event.get("occurred_at")):
        errors.append("occurred_at must be timezone-aware ISO 8601")
    evidence_url = event.get("evidence_url")
    if evidence_url is not None and not valid_https_url(evidence_url):
        errors.append("evidence_url must be HTTPS")
    if isinstance(event.get("event_type"), str) and event.get("event_type") in {
        "newsletter_optin", "member_signup", "affiliate_application", "funding_partner_signup"
    } and event.get("consent_status") != "opted_in":
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
