"""Synthetic local recovery fixtures; no provider call or hosted service."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from control_tower.handoffs import HandoffLedger
from control_tower.network_contract import TARGETS, digest, validate_draft
from control_tower.swarm_factory import build_swarm

REVISION = "0825e98c5cd148f0cf708e81dbe77fe462164ac2"


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.path = Path(self.directory.name) / "handoffs.sqlite3"
        self.ledger = HandoffLedger(self.path)
        self.manifest = build_swarm("ai-jarvis", sorted(TARGETS),
                                   swarm_id="memory-pilot", source_revision=REVISION)
        self.receipt = self.stage("mission-one")
        self.profile = self.context("mission-one")

    def tearDown(self):
        self.ledger.close()
        self.directory.cleanup()

    def stage(self, identifier, target="codex"):
        return self.ledger.stage({"schema_version": 1, "kind": "jarvis.draft",
            "project_id": "ai-jarvis", "target": target, "text": "Synthetic local draft."},
            self.manifest, assistant_id="memory-pilot.builder", handoff_id=identifier)

    def context(self, identifier):
        _, handoff = self.ledger._handoff(identifier)
        return {"schema_version": 1, "kind": "jarvis.handoff_context",
            "handoff_id": identifier, "handoff_sha256": digest(handoff),
            "project_id": "ai-jarvis", "mission_id": identifier,
            "source_revision": REVISION, "asset_id": "memory-pilot.builder",
            "platform": handoff["draft"]["target"], "configuration_version": "codex-draft.v1",
            "memory_revision": 1, "visibility": "owner_private", "allowed_actions": ["prepare_draft"],
            "context_refs": [{"url": "https://example.invalid/context", "revision": 1, "visibility": "owner_private"}],
            "evidence_refs": [], "budget": {"max_attempts": 2, "time_limit_seconds": 120,
            "paid_execution_authorized": False}, "execution": {"state": "execution_blocked",
            "context_id": "synthetic-offline-context", "attempts": 1,
            "checkpoint_ref": "https://example.invalid/checkpoint", "detail": "Synthetic failed command; retain unfinished work."}}

    def load(self, identifier="mission-one", **changes):
        args = {"expected_source_revision": REVISION, "expected_memory_revision": 1, **changes}
        return self.ledger.load_context(identifier, **args)

    def save(self):
        return self.ledger.save_context(self.profile, expected_revision=0)

    def approve(self):
        saved = self.save()
        self.ledger.review("mission-one", reviewer_id="local-evaluator", expected_sha256=self.receipt["handoff_sha256"])
        self.ledger.review_context("mission-one", reviewer_id="local-evaluator", expected_sha256=saved["context_sha256"])
        return saved

    def export(self, checksum, **changes):
        return self.ledger.export_context("mission-one", expected_sha256=checksum,
            expected_source_revision=REVISION, expected_memory_revision=1, **changes)

    def test_restart_retains_blocked_checkpoint_and_original_packet(self):
        saved = self.approve()
        first = self.export(saved["context_sha256"])
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        resumed = self.load()
        self.assertEqual(resumed["profile"], self.profile)
        self.assertEqual(resumed["profile"]["execution"]["state"], "execution_blocked")
        self.assertEqual(self.export(saved["context_sha256"]), first)
        self.assertEqual(digest(first["handoff"]), self.receipt["handoff_sha256"])
        self.assertEqual(first["external_actions"], 0)
        self.assertEqual(resumed["sender_authentication"], "not_established")

    def test_v1_migration_preserves_existing_rows_reviews_and_returns(self):
        self.ledger.review("mission-one", reviewer_id="local-evaluator", expected_sha256=self.receipt["handoff_sha256"])
        self.ledger.export("mission-one", expected_sha256=self.receipt["handoff_sha256"])
        self.ledger.import_return({"schema_version": 1, "kind": "jarvis.return", "return_id": "result-one",
            "handoff_id": "mission-one", "handoff_sha256": self.receipt["handoff_sha256"],
            "source_provider": "codex", "text": "Synthetic unverified return.", "evidence_urls": []})
        tables = ("handoffs", "swarms", "returns")
        before = {t: [tuple(r) for r in self.ledger.db.execute("SELECT * FROM " + t)] for t in tables}
        self.ledger.db.execute("DROP TABLE handoff_contexts")
        self.ledger.db.execute("PRAGMA user_version=1")
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        self.assertEqual(self.ledger.db.execute("PRAGMA user_version").fetchone()[0], 2)
        for table in tables:
            self.assertEqual([tuple(r) for r in self.ledger.db.execute("SELECT * FROM " + table)], before[table])
        self.assertTrue(self.stage("mission-one")["duplicate"])
        self.save()
        self.assertEqual(self.ledger.status()["return_count"], 1)

    def test_independent_records_and_defensive_retrieval(self):
        self.save()
        self.stage("mission-two")
        other = self.context("mission-two")
        self.ledger.save_context(other, expected_revision=0)
        self.profile["execution"]["detail"] = "Changed after write."
        retrieved = self.load()
        retrieved["profile"]["execution"]["detail"] = "Changed after read."
        self.assertNotEqual(self.load()["profile"]["execution"]["detail"], self.profile["execution"]["detail"])
        self.assertEqual(self.load("mission-two")["profile"], other)

    def test_stale_writer_and_duplicate_after_reopen(self):
        saved = self.save()
        with HandoffLedger(self.path) as second:
            self.assertTrue(second.save_context(self.profile, expected_revision=1)["duplicate"])
            changed = deepcopy(self.profile)
            changed["execution"]["detail"] = "Fresh observation."
            second.save_context(changed, expected_revision=1)
        with self.assertRaises(ValueError):
            self.ledger.save_context(self.profile, expected_revision=saved["revision"])
        self.assertEqual(self.load()["revision"], 2)

    def test_source_and_memory_mismatch_rejected_without_overwrite(self):
        self.save()
        for change in ({"expected_source_revision": "f" * 40}, {"expected_memory_revision": 2},
                       {"expected_memory_revision": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.load(**change)
        self.assertEqual(self.load()["profile"], self.profile)

    def test_private_reference_and_detail_do_not_enter_public_bundle(self):
        self.save()
        with self.assertRaises(ValueError):
            self.load(audience="public_candidate")
        public = deepcopy(self.profile)
        public["visibility"] = "public_candidate"
        with self.assertRaises(ValueError):
            self.ledger.save_context(public, expected_revision=1)
        public["context_refs"][0]["visibility"] = "public_candidate"
        self.ledger.save_context(public, expected_revision=1)
        self.assertEqual(self.load(audience="public_candidate")["profile"], public)

    def test_public_profile_cannot_declassify_unlabelled_v1_draft_text(self):
        self.profile["visibility"] = "public_candidate"
        self.profile["context_refs"] = []
        saved = self.approve()
        with self.assertRaises(ValueError):
            self.export(saved["context_sha256"], audience="public_candidate")
        self.assertEqual(self.ledger.status()["handoffs"][0]["state"], "reviewed")

    def test_every_edit_invalidates_context_review(self):
        saved = self.approve()
        self.profile["execution"]["detail"] = "New checkpoint; review again."
        updated = self.ledger.save_context(self.profile, expected_revision=1)
        self.assertEqual(self.load()["review_state"], "proposed")
        for checksum in (saved["context_sha256"], updated["context_sha256"]):
            with self.assertRaises(ValueError):
                self.export(checksum)
        # The old strict handoff and its review are still valid on their own.
        self.assertEqual(self.ledger.export("mission-one", expected_sha256=self.receipt["handoff_sha256"])["handoff_sha256"], self.receipt["handoff_sha256"])

    def test_context_cannot_bypass_handoff_review_or_self_review(self):
        saved = self.save()
        with self.assertRaises(ValueError):
            self.ledger.review_context("mission-one", reviewer_id="memory-pilot.builder", expected_sha256=saved["context_sha256"])
        self.ledger.review_context("mission-one", reviewer_id="local-evaluator", expected_sha256=saved["context_sha256"])
        with self.assertRaises(ValueError):
            self.export(saved["context_sha256"])

    def test_unknown_outcome_preserved_and_not_automatically_requeued(self):
        self.profile["execution"]["state"] = "outcome_unknown"
        self.save()
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        for _ in range(2):
            self.assertEqual(self.load()["profile"]["execution"], self.profile["execution"])

    def test_return_binding_is_not_replaced_by_context(self):
        saved = self.approve()
        envelope = self.export(saved["context_sha256"])
        self.ledger.import_return({"schema_version": 1, "kind": "jarvis.return", "return_id": "result-one",
            "handoff_id": "mission-one", "handoff_sha256": envelope["handoff_sha256"],
            "source_provider": "codex", "text": "Synthetic reply.", "evidence_urls": []})
        self.assertEqual(self.ledger.status()["return_count"], 1)
        self.assertEqual(self.load()["profile"]["execution"]["state"], "execution_blocked")

    def test_strict_v1_packets_reject_silently_added_context(self):
        with self.assertRaises(ValueError):
            validate_draft({"schema_version": 1, "kind": "jarvis.draft", "project_id": "ai-jarvis",
                "target": "codex", "text": "Fixture", "context": self.profile})

    def test_all_seventeen_targets_use_the_same_profile(self):
        with TemporaryDirectory() as directory, HandoffLedger(Path(directory) / "all.sqlite3") as ledger:
            for i, target in enumerate(sorted(TARGETS)):
                manifest = build_swarm("ai-jarvis", [target], swarm_id=f"target-{i}", source_revision=REVISION)
                staged = ledger.stage({"schema_version": 1, "kind": "jarvis.draft", "project_id": "ai-jarvis",
                    "target": target, "text": "Synthetic profile fixture."}, manifest,
                    assistant_id=f"target-{i}.builder", handoff_id=f"task-{i}")
                profile = deepcopy(self.profile)
                profile.update(handoff_id=f"task-{i}", handoff_sha256=staged["handoff_sha256"],
                               platform=target, asset_id=f"target-{i}.builder")
                ledger.save_context(profile, expected_revision=0)
                self.assertEqual(ledger.load_context(f"task-{i}", expected_source_revision=REVISION,
                    expected_memory_revision=1)["profile"]["platform"], target)

    def test_tampered_binding_permissions_and_bounds_rejected(self):
        changes = [{"schema_version": True}, {"platform": "openai"}, {"handoff_sha256": "0" * 64},
            {"source_revision": "f" * 40}, {"asset_id": "someone-else"}, {"project_id": "linux-education"},
            {"memory_revision": True}, {"allowed_actions": ["publish"]}, {"extra": True}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.ledger.save_context({**self.profile, **change}, expected_revision=0)
        for key, value in (("attempts", 3), ("state", "running"), ("checkpoint_ref", "http://example.invalid")):
            changed = deepcopy(self.profile)
            changed["execution"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.ledger.save_context(changed, expected_revision=0)
        self.assertEqual(self.ledger.db.execute("SELECT count(*) FROM handoff_contexts").fetchone()[0], 0)

    def test_memory_attempts_and_mission_history_cannot_regress(self):
        self.profile["memory_revision"] = 2
        self.save()
        for changed in ({"memory_revision": 1}, {"mission_id": "replacement-mission"}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.ledger.save_context({**self.profile, **changed}, expected_revision=1)
        decreased = deepcopy(self.profile)
        decreased["execution"]["attempts"] = 0
        with self.assertRaises(ValueError):
            self.ledger.save_context(decreased, expected_revision=1)

    def test_corrupt_context_fails_closed(self):
        self.save()
        self.ledger.db.execute("UPDATE handoff_contexts SET body=?", (json.dumps({**self.profile, "memory_revision": 2}),))
        with self.assertRaises(ValueError):
            self.load()

    def test_fresh_process_reads_checkpoint_without_retry(self):
        self.save()
        self.ledger.close()
        command = """import json, sys
from control_tower.handoffs import HandoffLedger
with HandoffLedger(sys.argv[1]) as ledger:
    print(json.dumps(ledger.load_context('mission-one',
        expected_source_revision=sys.argv[2], expected_memory_revision=1)))
"""
        try:
            result = subprocess.run([sys.executable, "-c", command, str(self.path), REVISION],
                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=10)
        finally:
            self.ledger = HandoffLedger(self.path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["profile"]["execution"], self.profile["execution"])

    def test_sqlite_backup_restores_original_and_context_together(self):
        self.save()
        backup_path = Path(self.directory.name) / "backup.sqlite3"
        with sqlite3.connect(backup_path) as destination:
            self.ledger.db.backup(destination)
        self.profile["execution"]["detail"] = "Later observation."
        self.ledger.save_context(self.profile, expected_revision=1)
        with HandoffLedger(backup_path) as restored:
            previous = restored.load_context("mission-one", expected_source_revision=REVISION,
                                              expected_memory_revision=1)
            self.assertEqual(previous["revision"], 1)
            self.assertNotEqual(previous["profile"]["execution"]["detail"], self.profile["execution"]["detail"])
            self.assertEqual(restored.status()["handoffs"][0]["handoff_sha256"], self.receipt["handoff_sha256"])


    def control_profile(self, state):
        return {**deepcopy(self.profile), "schema_version": 2,
                "control": {"state": state, "actor_id": "local-owner-label",
                            "reason": "Synthetic bounded control fixture."}}

    def assert_exports_blocked(self, checksum):
        with self.assertRaises(ValueError):
            self.ledger.export("mission-one", expected_sha256=self.receipt["handoff_sha256"])
        with self.assertRaises(ValueError):
            self.export(checksum)

    def test_v1_is_unchanged_and_control_requires_explicit_v2(self):
        self.save()
        self.assertEqual(self.load()["profile"], self.profile)
        with self.assertRaises(ValueError):
            self.ledger.save_context({**self.profile, "control": self.control_profile("paused")["control"]}, expected_revision=1)
        self.assertEqual(self.load()["revision"], 1)

    def test_paused_and_cancelled_block_both_exports_after_reopen(self):
        for state in ("paused", "cancelled"):
            with self.subTest(state=state):
                self.profile = self.control_profile(state)
                # Reset just this test fixture between independent cases.
                self.ledger.db.execute("DELETE FROM handoff_contexts")
                saved = self.approve()
                self.ledger.close()
                self.ledger = HandoffLedger(self.path)
                self.assert_exports_blocked(saved["context_sha256"])
                self.assertEqual(self.load()["profile"]["control"]["state"], state)
                self.assertEqual(self.load()["profile"]["execution"]["state"], "execution_blocked")

    def test_resume_requires_fresh_context_review_and_cannot_downgrade(self):
        self.profile = self.control_profile("paused")
        self.approve()
        legacy = {k: v for k, v in self.profile.items() if k != "control"}
        legacy["schema_version"] = 1
        with self.assertRaises(ValueError):
            self.ledger.save_context(legacy, expected_revision=1)
        active = self.control_profile("active")
        updated = self.ledger.save_context(active, expected_revision=1)
        with self.assertRaises(ValueError):
            self.export(updated["context_sha256"])
        self.ledger.review_context("mission-one", reviewer_id="local-evaluator", expected_sha256=updated["context_sha256"])
        self.assertEqual(self.export(updated["context_sha256"])["context"]["control"]["state"], "active")

    def test_cancel_is_terminal_but_allows_unverified_late_return(self):
        saved = self.approve()
        self.export(saved["context_sha256"])
        cancelled = self.control_profile("cancelled")
        cancelled["execution"]["state"] = "outcome_unknown"
        self.ledger.save_context(cancelled, expected_revision=1)
        for state in ("active", "paused"):
            with self.subTest(state=state), self.assertRaises(ValueError):
                self.ledger.save_context({**cancelled, "control": {**cancelled["control"], "state": state}}, expected_revision=2)
        packet = {"schema_version": 1, "kind": "jarvis.return", "return_id": "late-result",
                  "handoff_id": "mission-one", "handoff_sha256": self.receipt["handoff_sha256"],
                  "source_provider": "codex", "text": "Synthetic late evidence.", "evidence_urls": []}
        self.assertEqual(self.ledger.import_return(packet)["state"], "returned_unverified")
        loaded = self.load()
        self.assertEqual(loaded["profile"]["execution"]["state"], "outcome_unknown")
        self.assertEqual(loaded["profile"]["control"]["state"], "cancelled")
        self.assert_exports_blocked(loaded["context_sha256"])

    def test_control_duplicate_stale_writer_and_independent_handoff(self):
        self.profile = self.control_profile("paused")
        self.approve()
        with HandoffLedger(self.path) as other:
            self.assertTrue(other.save_context(self.profile, expected_revision=1)["duplicate"])
            with self.assertRaises(ValueError):
                other.save_context(self.control_profile("active"), expected_revision=0)
        self.stage("mission-two")
        other_profile = self.context("mission-two")
        self.ledger.save_context(other_profile, expected_revision=0)
        self.assertNotIn("control", self.load("mission-two")["profile"])
        self.assertEqual(self.load()["profile"]["control"]["state"], "paused")

    def test_control_schema_rejects_unknown_or_authority_fields(self):
        for change in ({"state": "running"}, {"state": True}, {"actor_id": "../outside"},
                       {"reason": ""}, {"authenticated": True}):
            bad = self.control_profile("paused")
            bad["control"].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.ledger.save_context(bad, expected_revision=0)
        self.assertEqual(self.ledger.db.execute("SELECT count(*) FROM handoff_contexts").fetchone()[0], 0)

    def test_corrupt_control_blocks_legacy_export(self):
        self.profile = self.control_profile("active")
        self.approve()
        self.ledger.db.execute("UPDATE handoff_contexts SET body='{}'")
        self.assert_exports_blocked("0" * 64)


if __name__ == "__main__":
    unittest.main()
