"""Offline round-trip sandbox; no network, model calls, or deployments."""
import hashlib
import json
from control_tower.events import ingest
from control_tower.orchestrator import AgentPassport, Proposal, plan
from control_tower.attribution import aggregate
from control_tower.briefing import project_summary

def run_synthetic_roundtrip(events):
    seen, accepted, rejected = set(), [], []
    for event in events:
        status, errors = ingest(event, seen)
        if status == "accepted":
            accepted.append(event)
        elif status == "rejected":
            rejected.append({"event_id": event.get("event_id"), "errors": errors})
    passport = AgentPassport("jarvis-builder", frozenset({"write_code"}), max_tasks=1)
    candidate = Proposal("candidate-1", "write_code", "sandbox", evidence_ref="synthetic-input")
    decisions = plan(passport, (candidate,))
    report = {
        "fixture_only": True,
        "accepted_count": len(accepted),
        "rejected": rejected,
        "proposed_tasks": [p.proposal_id for p in decisions["proposed_sandbox_tasks"]],
        "attribution": {f"{channel}:{kind}": count for (channel, kind), count in sorted(aggregate(accepted).items())},
        "status": project_summary([{"name": "Hostinger connection", "status": "unknown"}]),
        "independent_qa": "not_run",
        "deployment": "not_deployed",
    }
    digest = hashlib.sha256(json.dumps(report, sort_keys=True).encode("utf-8")).hexdigest()
    report["sha256"] = digest
    return report
