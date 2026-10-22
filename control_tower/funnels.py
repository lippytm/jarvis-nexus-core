"""Pure offline membership and affiliate lead routing, synthetic events only."""
from control_tower.validation import json_record_errors, valid_identifier

KINDS = {"member", "funding_customer", "funding_partner"}
DESTINATIONS = {
    "funding_customer": ("https://lippytmai.getbizfunds.com", "https://www.7figurescredit.com?a_aid=lippytm"),
    "funding_partner": ("https://lendtrack.ai/join/lippytmai", "https://join.7figurespartners.com/?a_aid=lippytm"),
}
def route_lead(record):
    if json_record_errors(record):
        return {"status": "rejected", "reason": "invalid or sensitive record"}
    kind = record.get("kind")
    if not isinstance(kind, str) or kind not in KINDS:
        return {"status": "rejected", "reason": "unknown journey"}
    if "utm_source" in record and not valid_identifier(record["utm_source"]):
        return {"status": "rejected", "reason": "invalid source"}
    if record.get("consent") is not True:
        return {"status": "rejected", "reason": "consent required"}
    if any(k in record for k in ("ssn", "credit_report", "card_number", "password")):
        return {"status": "rejected", "reason": "sensitive fields forbidden"}
    if kind == "member":
        return {"status": "sandbox_only", "action": "membership_registration_review", "source": record.get("utm_source", "unknown")}
    return {"status": "sandbox_only", "action": "provider_redirect_review",
            "destinations": DESTINATIONS[kind], "source": record.get("utm_source", "unknown")}
