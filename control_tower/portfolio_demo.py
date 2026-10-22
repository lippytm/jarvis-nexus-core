"""Synthetic demonstration of portfolio planning, not dispatched work."""
from urllib.parse import parse_qs, urlsplit

from control_tower.campaigns import campaign_briefs
from control_tower.missions import compile_mission
from control_tower.portfolio import portfolio_catalog

BASE_REVISION = "a67e743e8b32e552ccddd9e16a2108fe2f816274"


def demonstrate_portfolio():
    catalog = portfolio_catalog()
    missions = []
    for item in catalog["initiatives"]:
        request = {"schema_version": 1, "kind": "jarvis.mission_request", "initiative_id": item["id"],
                   "target": "gemini", "objective": "Prepare one bounded planning example for " + item["title"] + ".",
                   "timebox_minutes": 30}
        missions.append(compile_mission(request, mission_id="example-" + item["id"], source_revision=BASE_REVISION))
    samples = []
    for key in ("funding-customers", "referral-partners"):
        mission = next(m for m in missions if m["initiative"]["id"] == key)
        packet = campaign_briefs(mission, destination_index=1)
        samples.append({"initiative_id": key, "journey_kind": packet["journey_kind"],
                        "channel_briefs": len(packet["briefs"]),
                        "referral_parameter_preserved": all(parse_qs(urlsplit(b["candidate_url"]).query).get("a_aid") == ["lippytm"] for b in packet["briefs"]),
                        "url_status": "not_live_checked", "actual_metrics": packet["actual_metrics"]})
    return {"mode": "local_synthetic_planning", "catalog_sha256": catalog["catalog_sha256"],
            "initiative_count": len(missions), "project_count": len({m["initiative"]["project_id"] for m in missions}),
            "inactive_role_drafts": sum(len(m["tasks"]) for m in missions),
            "campaign_samples": samples, "model_calls": 0, "external_actions": 0,
            "external_agents_started": 0, "live_metrics": None,
            "source_context_revision": BASE_REVISION}
