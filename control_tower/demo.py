"""Offline seven-workflow demonstration: no external API or production side effects."""
from control_tower.events import ingest
from control_tower.funnels import route_lead
from control_tower.roundtrip import run_synthetic_roundtrip
from control_tower.builder import ToolSpec, generate_candidate
from control_tower.evaluator import evaluate_candidate
from control_tower.dashboard import build_dashboard
from control_tower.connections import connector_report

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
                       "approval_state": "pending"})
    report = run_synthetic_roundtrip(events)
    candidate = generate_candidate(ToolSpec("synthetic_validator", "validation_tool", "Offline template"))
    evaluation = evaluate_candidate(candidate)
    dashboard = build_dashboard([{"name":"Hostinger", "status":"unknown"}], {})
    return {
        "mode": "synthetic_only", "routes": routes, "roundtrip": report,
        "builder_candidate": {"filename":candidate["filename"], "sha256":candidate["sha256"]},
        "static_evaluation": evaluation, "dashboard": dashboard,
        "connectors": connector_report(), "external_actions": 0,
    }
