"""Synthetic-only channel attribution aggregation for membership/affiliate experiments."""
from collections import Counter

CHANNELS = frozenset({"facebook", "instagram", "threads", "linkedin", "substack", "hostinger"})
CONVERSIONS = frozenset({"newsletter_optin", "member_signup", "affiliate_application", "funding_partner_signup"})

def aggregate(events):
    """Counts only supplied events. Missing data is not represented as zero live performance."""
    totals = Counter()
    seen = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = event.get("event_id")
        channel = event.get("utm_source", event.get("source"))
        if not isinstance(event_id, str) or not event_id or event_id in seen or not isinstance(channel, str) or channel not in CHANNELS:
            continue
        if not isinstance(event.get("event_type"), str):
            continue
        seen.add(event_id)
        if event.get("event_type") == "campaign_visit":
            totals[(channel, "visits")] += 1
        elif event.get("event_type") in CONVERSIONS and event.get("consent_status") == "opted_in":
            totals[(channel, event["event_type"])] += 1
    return dict(totals)
