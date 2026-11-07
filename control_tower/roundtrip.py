"""Offline round-trip sandbox; no network, model calls, or deployments."""
import hashlib
import json
from control_tower.events import ingest, validate_event
from control_tower.validation import valid_identifier
from control_tower.orchestrator import AgentPassport, Proposal, plan
from control_tower.attribution import aggregate
from control_tower.briefing import project_summary

def run_synthetic_roundtrip(events):
    if not isinstance(events, (list, tuple)) or len(events) > 1000:
        raise ValueError("a batch must contain at most 1000 fixture events")
    seen, accepted, rejected, fingerprints = set(), [], [], {}
    duplicate_count = 0
    for event in events:
        errors = validate_event(event)
        event_id = event.get("event_id") if isinstance(event, dict) else None
        if not valid_identifier(event_id):
            event_id = None
        if not errors and (not isinstance(event.get("payload"), dict)
                           or event["payload"].get("synthetic") is not True):
            errors = ["explicit synthetic fixture marker required"]
        if errors:
            rejected.append({"event_id": event_id, "errors": errors})
            continue
        fingerprint = hashlib.sha256(json.dumps(event, sort_keys=True, allow_nan=False).encode()).hexdigest()
        if event_id in fingerprints and fingerprints[event_id] != fingerprint:
            rejected.append({"event_id": event_id, "errors": ["conflicting duplicate event"]})
            continue
        status, errors = ingest(event, seen)
        if status == "accepted":
            accepted.append(event)
            fingerprints[event_id] = fingerprint
        elif status == "duplicate":
            duplicate_count += 1
        elif status == "rejected":
            rejected.append({"event_id": event_id, "errors": errors})
    passport = AgentPassport("jarvis-builder", frozenset({"write_code"}), max_tasks=1)
    candidate = Proposal("candidate-1", "write_code", "sandbox", evidence_ref="synthetic-input")
    decisions = plan(passport, (candidate,))
    report = {
        "fixture_only": True,
        "accepted_count": len(accepted),
        "duplicate_count": duplicate_count,
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
