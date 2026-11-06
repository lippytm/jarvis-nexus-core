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
            # A second inactive target exercises the shared context contract in
            # the same ledger without changing the existing Gemini packet.
            codex = ledger.stage({**draft, "target": "codex"}, swarm,
                assistant_id="demo-ai-jarvis.builder", handoff_id="demo-codex-context")
            profile = {"schema_version": 3, "kind": "jarvis.handoff_context",
                "handoff_id": "demo-codex-context", "handoff_sha256": codex["handoff_sha256"],
                "project_id": "ai-jarvis", "mission_id": "demo-codex-context",
                "source_revision": BASE_REVISION, "asset_id": "demo-ai-jarvis.builder",
                "platform": "codex", "destination_id": "synthetic-local-codex",
                "configuration_version": "codex-draft.v1", "memory_revision": 1,
                "visibility": "owner_private", "allowed_actions": ["prepare_draft"],
                "context_refs": [], "evidence_refs": [],
                "budget": {"max_attempts": 2, "time_limit_seconds": 120, "paid_execution_authorized": False},
                "control": {"state": "paused", "actor_id": "demo-owner", "reason": "Synthetic pause; no dispatch."},
                "execution": {"state": "execution_blocked", "context_id": "synthetic-codex",
                    "attempts": 1, "checkpoint_ref": "https://example.invalid/checkpoint",
                    "detail": "Synthetic blocked attempt; no real runtime failure is asserted."}}
            saved = ledger.save_context(profile, expected_revision=0)
            ledger.review("demo-codex-context", reviewer_id="demo-evaluator", expected_sha256=codex["handoff_sha256"])
            ledger.review_context("demo-codex-context", reviewer_id="demo-evaluator", expected_sha256=saved["context_sha256"])
            guards = dict(expected_source_revision=BASE_REVISION, expected_memory_revision=1,
                          expected_sha256=saved["context_sha256"])
            ledger.checkpoint_context("demo-codex-context", **guards)
        with HandoffLedger(path) as ledger:
            restored = ledger.load_context("demo-codex-context", **guards)
            duplicate = ledger.checkpoint_context("demo-codex-context", **guards)
            edited = {**profile, "memory_revision": 2,
                      "execution": {**profile["execution"], "detail": "Synthetic updated evidence; retain pause and blocked state."}}
            updated = ledger.save_context(edited, expected_revision=1)
        with HandoffLedger(path, read_only=True) as ledger:
            current = ledger.load_context("demo-codex-context", expected_source_revision=BASE_REVISION,
                expected_memory_revision=2, expected_sha256=updated["context_sha256"])
            history = ledger.load_checkpoint("demo-codex-context", 1, **guards)
            inspection = ledger.inspect_recovery("demo-codex-context", expected_source_revision=BASE_REVISION,
                expected_memory_revision=2, expected_sha256=updated["context_sha256"])
            status = ledger.status()
            recovery = {"mode": "local_synthetic_context_recovery", "platform": "codex",
                "destination_id": current["profile"]["destination_id"], "context_sha256": current["context_sha256"],
                "context_revision": current["revision"], "memory_revision": current["profile"]["memory_revision"],
                "profile_retained_after_reopen": restored["profile"] == profile,
                "prior_local_review_retained": restored["review_state"] == "locally_reviewed",
                "duplicate_checkpoint": duplicate["duplicate"],
                "historical_profile_retained": history["profile"] == profile,
                "review_state_after_edit": current["review_state"],
                "execution_state": current["profile"]["execution"]["state"],
                "control_state": current["profile"]["control"]["state"],
                "holds": inspection["lineage"][0]["holds"],
                "visibility": "owner_private", "sender_authentication": "not_established",
                "review_authority": "local_record_only_not_identity_authentication",
                "dispatch_authorized": False, "retry_authorized": False, "external_actions": 0}
    return {"mode": "local_synthetic_fixture", "project_count": len(swarms),
            "inactive_assistant_specifications": sum(len(s["assistants"]) for s in swarms),
            "target_provider_count": len(TARGETS), "swarm_manifest_sha256": {s["project_id"]: s["manifest_sha256"] for s in swarms},
            "export_prepared": exported["mode"] == "manual_handoff", "reopen_retry_is_duplicate": retry["duplicate"],
            "return_state": returned["state"], "ledger": status, "context_recovery": recovery,
            "external_agents_started": 0, "model_calls": 0, "external_actions": 0}
