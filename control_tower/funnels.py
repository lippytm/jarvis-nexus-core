"""Pure offline membership and affiliate lead routing, synthetic events only."""
from urllib.parse import urlparse

KINDS = {"member", "funding_customer", "funding_partner"}
DESTINATIONS = {
    "funding_customer": ("https://lippytmai.getbizfunds.com", "https://www.7figurescredit.com?a_aid=lippytm"),
    "funding_partner": ("https://lendtrack.ai/join/lippytmai", "https://join.7figurespartners.com/?a_aid=lippytm"),
}
def route_lead(record):
    kind = record.get("kind")
    if kind not in KINDS:
        return {"status": "rejected", "reason": "unknown journey"}
    if record.get("consent") is not True:
        return {"status": "rejected", "reason": "consent required"}
    if any(k in record for k in ("ssn", "credit_report", "card_number", "password")):
        return {"status": "rejected", "reason": "sensitive fields forbidden"}
    if kind == "member":
        return {"status": "sandbox_only", "action": "membership_registration_review", "source": record.get("utm_source", "unknown")}
    return {"status": "sandbox_only", "action": "provider_redirect_review",
            "destinations": DESTINATIONS[kind], "source": record.get("utm_source", "unknown")}
