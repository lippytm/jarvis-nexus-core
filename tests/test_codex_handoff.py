"""Codex handoffs preserve review, persistence and honest availability boundaries."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from control_tower.connections import connector_report, read_observation
from control_tower.handoffs import HandoffLedger
from control_tower.network_contract import TARGETS, validate_draft
from control_tower.provider_catalog import provider_catalog, provider_details
from control_tower.swarm_factory import build_swarm

REVISION = "437edf958f8ea23e5767db49cef174d69a8e7d43"


class CodexHandoffTests(unittest.TestCase):
    def test_codex_is_distinct_from_chatgpt_and_openai_api(self):
        self.assertIn("codex", TARGETS)
        self.assertEqual(len(TARGETS), 17)
        self.assertEqual(set(provider_catalog()), set(TARGETS))
        row = provider_details("codex")
        self.assertEqual(row["category"], "engineering_assistant")
        self.assertNotEqual(row["category"], provider_details("chatgpt")["category"])
        self.assertNotEqual(row["category"], provider_details("openai")["category"])
        self.assertEqual(row["connection_status"], "unverified")
        self.assertEqual(row["write_operations"], "not_implemented")
        self.assertEqual(row["live_api_adapter"], "not_implemented")

    def test_codex_draft_preserves_exact_review_and_return_binding_after_reopen(self):
        draft = {"schema_version": 1, "kind": "jarvis.draft",
                 "project_id": "ai-jarvis", "target": "codex",
                 "text": "Synthetic coding mission; no Codex service is invoked."}
        self.assertEqual(validate_draft(draft), draft)
        manifest = build_swarm("ai-jarvis", ["codex"], swarm_id="codex-pilot",
                               source_revision=REVISION)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "handoffs.sqlite3"
            with HandoffLedger(path) as ledger:
                staged = ledger.stage(draft, manifest, assistant_id="codex-pilot.builder",
                                      handoff_id="codex-first")
                checksum = staged["handoff_sha256"]
                with self.assertRaises(ValueError):
                    ledger.export("codex-first", expected_sha256=checksum)
                with self.assertRaises(ValueError):
                    ledger.review("codex-first", reviewer_id="owner-review-label",
                                  expected_sha256="0" * 64)
                ledger.review("codex-first", reviewer_id="owner-review-label",
                              expected_sha256=checksum)
                self.assertEqual(ledger.export("codex-first", expected_sha256=checksum)["mode"],
                                 "manual_handoff")
            packet = {"schema_version": 1, "kind": "jarvis.return",
                      "return_id": "codex-result", "handoff_id": "codex-first",
                      "handoff_sha256": checksum, "source_provider": "codex",
                      "text": "Synthetic fixture, not an actual Codex response.",
                      "evidence_urls": []}
            with HandoffLedger(path) as ledger:
                with self.assertRaises(ValueError):
                    ledger.import_return({**packet, "source_provider": "openai"})
                result = ledger.import_return(packet)
                self.assertEqual(result["state"], "returned_unverified")
                self.assertEqual(result["sender_authentication"], "not_established")
            with HandoffLedger(path) as ledger:
                self.assertEqual(ledger.status()["return_count"], 1)
                self.assertTrue(ledger.import_return(packet)["duplicate"])

    def test_read_metadata_cannot_claim_codex_execution_or_write_authority(self):
        record = read_observation(
            "codex", observed_at="2026-10-27T18:00:00Z",
            evidence_url="https://example.invalid/synthetic-receipt",
            response_sha256="0" * 64, scope="synthetic metadata read only",
            source_revision=REVISION)
        row = connector_report([record], now=datetime(2026, 10, 27, 19, tzinfo=timezone.utc))["codex"]
        self.assertEqual(row["status"], "read_observed")
        self.assertEqual(row["observation_verification"], "integrity_only")
        self.assertEqual(row["runtime_available"], "unknown")
        self.assertEqual(row["write_gate"], "owner_review")
        self.assertEqual(row["last_observation"]["operation"], "read")

    def test_codex_factory_roles_remain_bounded_and_inactive(self):
        result = build_swarm("ai-jarvis", ["codex", "github", "claude", "gemini"],
                             swarm_id="codex-core", source_revision=REVISION)
        self.assertEqual(len(result["assistants"]), 5)
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["external_actions"], 0)
        self.assertTrue(all(role["state"] == "inactive_proposal"
                            and role["capabilities"] == ["prepare_draft"]
                            for role in result["assistants"]))


if __name__ == "__main__":
    unittest.main()
