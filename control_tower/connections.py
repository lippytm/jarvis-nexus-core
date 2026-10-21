"""Read-only connector capability registry: unverified until owner authorizes checks."""
CONNECTORS = {
    "github": {"purpose": "repository QA and PR reviews", "status": "connector_available", "write_gate": "owner_review"},
    "hostinger": {"purpose": "landing pages and membership forms", "status": "unverified", "write_gate": "owner_review"},
    "gemini": {"purpose": "cross-model research", "status": "unverified", "write_gate": "owner_review"},
    "claude": {"purpose": "coding and independent review", "status": "unverified", "write_gate": "owner_review"},
    "facebook": {"purpose": "consented promotion", "status": "unverified", "write_gate": "owner_review"},
    "instagram": {"purpose": "consented promotion", "status": "unverified", "write_gate": "owner_review"},
    "threads": {"purpose": "consented promotion", "status": "unverified", "write_gate": "owner_review"},
    "linkedin": {"purpose": "consented outreach and attribution", "status": "unverified", "write_gate": "owner_review"},
    "substack": {"purpose": "newsletter and membership referrals", "status": "unverified", "write_gate": "owner_review"},
}
def connector_report():
    return {name: dict(details) for name, details in sorted(CONNECTORS.items())}
