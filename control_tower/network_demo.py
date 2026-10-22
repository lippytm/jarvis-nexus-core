"""Exercise one local fixture round trip and prepare cross-project assistant drafts."""
from pathlib import Path
from tempfile import TemporaryDirectory

from control_tower.handoffs import HandoffLedger
from control_tower.network_contract import PROJECTS, TARGETS
from control_tower.swarm_factory import build_swarm

BASE_REVISION = "575ebc777fae0165c93247e8c6da44c440539c4d"


def demonstrate_network():
    swarms = [build_swarm(project, sorted(TARGETS), swarm_id=f"demo-{project}",
                           source_revision=BASE_REVISION) for project in PROJECTS]
    swarm = swarms[0]
    draft = {"schema_version": 1, "kind": "jarvis.draft", "project_id": "ai-jarvis",
             "target": "gemini", "text": "Synthetic local fixture: propose one tested Jarvis integration improvement. No message is sent."}
    with TemporaryDirectory(prefix="jarvis-network-") as tmp:
        path = Path(tmp) / "ledger.sqlite3"
        with HandoffLedger(path) as ledger:
            staged = ledger.stage(draft, swarm, assistant_id="demo-ai-jarvis.builder", handoff_id="demo-handoff")
            ledger.review("demo-handoff", reviewer_id="demo-independent-reviewer", expected_sha256=staged["handoff_sha256"])
            exported = ledger.export("demo-handoff", expected_sha256=staged["handoff_sha256"])
        # Reopen deliberately to exercise persisted identity and limits.
        with HandoffLedger(path) as ledger:
            retry = ledger.stage(draft, swarm, assistant_id="demo-ai-jarvis.builder", handoff_id="demo-handoff")
            returned = ledger.import_return({"schema_version": 1, "kind": "jarvis.return",
                "return_id": "demo-return", "handoff_id": "demo-handoff",
                "handoff_sha256": staged["handoff_sha256"], "source_provider": "gemini",
                "text": "Synthetic response authored by the local fixture, not received from Gemini.", "evidence_urls": []})
            status = ledger.status()
    return {"mode": "local_synthetic_fixture", "project_count": len(swarms),
            "inactive_assistant_specifications": sum(len(s["assistants"]) for s in swarms),
            "target_provider_count": len(TARGETS), "swarm_manifest_sha256": {s["project_id"]: s["manifest_sha256"] for s in swarms},
            "export_prepared": exported["mode"] == "manual_handoff", "reopen_retry_is_duplicate": retry["duplicate"],
            "return_state": returned["state"], "ledger": status,
            "external_agents_started": 0, "model_calls": 0, "external_actions": 0}
