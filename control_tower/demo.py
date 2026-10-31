"""Offline seven-workflow demonstration: no external API or production side effects."""
from control_tower.events import ingest
from control_tower.funnels import route_lead
from control_tower.roundtrip import run_synthetic_roundtrip
from control_tower.builder import ToolSpec, generate_candidate
from control_tower.evaluator import evaluate_candidate
from control_tower.dashboard import build_dashboard
from control_tower.connections import connector_report
from control_tower.journeys import reconcile_journeys
from control_tower.network_demo import demonstrate_network
from control_tower.portfolio_demo import demonstrate_portfolio

def demonstrate():
    leads = [
        {"kind": "member", "consent": True, "utm_source": "linkedin"},
        {"kind": "funding_customer", "consent": True, "utm_source": "facebook"},
        {"kind": "funding_partner", "consent": True, "utm_source": "threads"},
    ]
    routes = [route_lead(lead) for lead in leads]
    events = []
    for idx, source in enumerate(("linkedin", "facebook", "threads"), 1):
        events.append({"event_id": f"synthetic-{idx}", "event_type": "campaign_visit",
                       "source": source, "utm_source": source,
                       "occurred_at": "2026-10-21T09:30:00-07:00",
                       "project_id": "synthetic-marketing",
                       "consent_status": "not_applicable",
                       "approval_state": "pending", "payload": {"synthetic": True}})
    report = run_synthetic_roundtrip(events)
    candidate = generate_candidate(ToolSpec("synthetic_validator", "validation_tool", "Offline template"))
    evaluation = evaluate_candidate(candidate)
    dashboard = build_dashboard([{"name":"Hostinger", "status":"unknown"}], {})
    envelope = {"journey_id": "synthetic-member-1", "kind": "member",
                "occurred_at": "2026-10-22T12:00:00-07:00", "source": "linkedin", "synthetic": True}
    journey = reconcile_journeys([
        {**envelope, "event_id": "synthetic-signup-1", "event_type": "member_signup",
         "service_consent": True, "marketing_opt_in": False},
        {**envelope, "event_id": "synthetic-payment-1", "event_type": "member_payment_confirmed",
         "payment_id": "synthetic-receipt-1", "provider_event_id": "synthetic-provider-1",
         "confirmation_kind": "simulated_provider", "amount_minor": 500, "currency": "USD"},
        {**envelope, "event_id": "synthetic-access-1", "event_type": "member_access_granted",
         "payment_id": "synthetic-receipt-1", "entitlement_id": "synthetic-access-right-1"},
    ])
    return {
        "mode": "synthetic_only", "routes": routes, "roundtrip": report,
        "membership_journey": journey,
        "assistant_network": demonstrate_network(),
        "portfolio_planning": demonstrate_portfolio(),
        "builder_candidate": {"filename":candidate["filename"], "sha256":candidate["sha256"]},
        "static_evaluation": evaluation, "dashboard": dashboard,
        "connectors": connector_report(), "external_actions": 0,
    }
