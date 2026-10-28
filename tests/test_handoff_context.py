"""Synthetic local recovery fixtures; no provider call or hosted service."""
from copy import deepcopy
from datetime import datetime, timezone
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
from control_tower.connections import read_observation

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

    def test_unknown_outcome_blocks_both_export_paths_after_reopen(self):
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.approve()
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        self.assert_exports_blocked(saved["context_sha256"])
        self.assertEqual(self.load()["profile"], self.profile)
        controlled = self.control_profile("active")
        updated = self.ledger.save_context(controlled, expected_revision=1)
        self.ledger.review_context("mission-one", reviewer_id="local-evaluator", expected_sha256=updated["context_sha256"])
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        self.assert_exports_blocked(updated["context_sha256"])
        self.assertEqual(self.load()["profile"], controlled)

    def test_unknown_outcome_cannot_be_cleared_or_retried_by_context_edit(self):
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.approve()
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        for change in ({"state": "pending"}, {"state": "execution_blocked"},
                       {"attempts": 2}, {"context_id": "replacement-worker"}):
            changed = deepcopy(self.profile)
            changed["execution"].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.ledger.save_context(changed, expected_revision=1)
        loaded = self.load()
        self.assertEqual(loaded["profile"], self.profile)
        self.assertEqual(loaded["context_sha256"], saved["context_sha256"])
        self.assertEqual(loaded["review_state"], "locally_reviewed")
        self.assertTrue(self.ledger.save_context(self.profile, expected_revision=1)["duplicate"])

    def test_unknown_outcome_accepts_evidence_and_cancel_but_stays_held(self):
        self.profile = self.control_profile("active")
        self.profile["execution"]["state"] = "outcome_unknown"
        self.approve()
        changed = deepcopy(self.profile)
        changed["control"]["state"] = "cancelled"
        changed["execution"]["detail"] = "Synthetic observation retained for reconciliation."
        changed["evidence_refs"] = [{"url": "https://example.invalid/observation", "revision": 1,
                                     "visibility": "owner_private"}]
        saved = self.ledger.save_context(changed, expected_revision=1)
        self.assertEqual(self.load()["profile"], changed)
        self.assertEqual(self.load()["review_state"], "proposed")
        self.ledger.review_context("mission-one", reviewer_id="local-evaluator", expected_sha256=saved["context_sha256"])
        self.assert_exports_blocked(saved["context_sha256"])

    def returned_parent(self):
        saved = self.approve()
        self.export(saved["context_sha256"])
        self.ledger.import_return({"schema_version": 1, "kind": "jarvis.return", "return_id": "parent-return",
            "handoff_id": "mission-one", "handoff_sha256": self.receipt["handoff_sha256"],
            "source_provider": "codex", "text": "Synthetic unverified parent result.", "evidence_urls": []})

    def stage_followup(self):
        return self.ledger.stage({"schema_version": 1, "kind": "jarvis.draft", "project_id": "ai-jarvis",
            "target": "codex", "text": "Synthetic follow-up draft."}, self.manifest,
            assistant_id="memory-pilot.builder", handoff_id="followup-one", parent_id="mission-one")

    def test_parent_hold_blocks_new_child_without_consuming_budget(self):
        self.returned_parent()
        held = deepcopy(self.profile)
        held["execution"]["state"] = "outcome_unknown"
        self.ledger.save_context(held, expected_revision=1)
        with self.assertRaises(ValueError):
            self.stage_followup()
        self.assertEqual(len(self.ledger.status()["handoffs"]), 1)
        self.assertEqual(self.ledger.status()["return_count"], 1)

    def test_cyclic_stored_ancestry_fails_closed(self):
        _, body = self.ledger._handoff("mission-one")
        body["parent_id"] = "mission-one"
        checksum = digest(body)
        self.ledger.db.execute("UPDATE handoffs SET body=?,digest=?,reviewed_digest=?,state='reviewed' WHERE id=?",
                              (json.dumps(body), checksum, checksum, "mission-one"))
        with self.assertRaisesRegex(ValueError, "ancestry"):
            self.ledger.export("mission-one", expected_sha256=checksum)

    def test_existing_child_exports_observe_parent_pause_and_resume_review(self):
        self.profile = self.control_profile("active")
        self.returned_parent()
        child = self.stage_followup()
        profile = self.context("followup-one")
        saved = self.ledger.save_context(profile, expected_revision=0)
        self.ledger.review("followup-one", reviewer_id="local-evaluator", expected_sha256=child["handoff_sha256"])
        self.ledger.review_context("followup-one", reviewer_id="local-evaluator", expected_sha256=saved["context_sha256"])
        paused = self.control_profile("paused")
        self.ledger.save_context(paused, expected_revision=1)
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        def export_child():
            return self.ledger.export_context("followup-one", expected_sha256=saved["context_sha256"],
                expected_source_revision=REVISION, expected_memory_revision=1)
        for export in (lambda: self.ledger.export("followup-one", expected_sha256=child["handoff_sha256"]), export_child):
            with self.assertRaises(ValueError):
                export()
        active = self.control_profile("active")
        resumed = self.ledger.save_context(active, expected_revision=2)
        with self.assertRaises(ValueError):
            export_child()
        self.ledger.review_context("mission-one", reviewer_id="local-evaluator", expected_sha256=resumed["context_sha256"])
        self.assertEqual(export_child()["handoff_sha256"], child["handoff_sha256"])
        self.assertEqual(self.load("followup-one")["profile"], profile)

    def test_cancelled_ancestor_blocks_depth_two_legacy_export(self):
        with TemporaryDirectory() as directory, HandoffLedger(Path(directory) / "chain.sqlite3") as ledger:
            swarm = build_swarm("ai-jarvis", ["codex"], swarm_id="chain-pilot", source_revision=REVISION,
                                max_depth=2, max_handoffs_per_assistant=3)
            parent = None
            records = []
            for i in range(3):
                identifier = f"chain-{i}"
                item = ledger.stage({"schema_version": 1, "kind": "jarvis.draft", "project_id": "ai-jarvis",
                    "target": "codex", "text": "Synthetic chain."}, swarm, assistant_id="chain-pilot.builder",
                    handoff_id=identifier, parent_id=parent)
                ledger.review(identifier, reviewer_id="local-evaluator", expected_sha256=item["handoff_sha256"])
                ledger.export(identifier, expected_sha256=item["handoff_sha256"])
                ledger.import_return({"schema_version": 1, "kind": "jarvis.return", "return_id": f"chain-return-{i}",
                    "handoff_id": identifier, "handoff_sha256": item["handoff_sha256"], "source_provider": "codex",
                    "text": "Synthetic returned evidence.", "evidence_urls": []})
                records.append(item)
                parent = identifier
            cancelled = self.control_profile("cancelled")
            cancelled.update(handoff_id="chain-0", handoff_sha256=records[0]["handoff_sha256"], asset_id="chain-pilot.builder")
            ledger.save_context(cancelled, expected_revision=0)
            with self.assertRaises(ValueError):
                ledger.export("chain-2", expected_sha256=records[2]["handoff_sha256"])
            self.assertEqual(ledger.status()["return_count"], 3)

    def test_corrupt_context_fails_closed(self):
        self.save()
        self.ledger.db.execute("UPDATE handoff_contexts SET body=?", (json.dumps({**self.profile, "memory_revision": 2}),))
        with self.assertRaises(ValueError):
            self.load()

    def inspect(self, identifier="mission-one", **changes):
        context = self.load(identifier)
        return self.ledger.inspect_recovery(identifier, **{
            "expected_sha256": context["context_sha256"], "expected_source_revision": REVISION,
            "expected_memory_revision": 1, **changes})

    def test_recovery_inspection_survives_restart_without_releasing_unknown_hold(self):
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.approve()
        before = list(self.ledger.db.iterdump())
        first = self.inspect()
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        self.assertEqual(self.inspect(), first)
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.assertEqual(first["lineage"][0]["holds"], ["outcome_unknown"])
        self.assertEqual(first["lineage"][0]["context"]["attempts"], 1)
        self.assertFalse(first["retry_authorized"])
        checksum = first.pop("inspection_sha256")
        self.assertEqual(digest(first), checksum)
        self.assert_exports_blocked(saved["context_sha256"])

    def test_recovery_inspection_retains_parent_bindings_without_other_missions_or_text(self):
        self.returned_parent()
        child = self.stage_followup()
        self.ledger.save_context(self.context("followup-one"), expected_revision=0)
        held = self.control_profile("paused")
        held["execution"]["state"] = "outcome_unknown"
        self.ledger.save_context(held, expected_revision=1)
        self.ledger.stage({"schema_version": 1, "kind": "jarvis.draft", "project_id": "ai-jarvis",
            "target": "github", "text": "Unrelated synthetic mission."}, self.manifest,
            assistant_id="memory-pilot.evaluator", handoff_id="unrelated-mission")
        packet = self.inspect("followup-one")
        self.assertEqual([r["handoff_id"] for r in packet["lineage"]], ["followup-one", "mission-one"])
        leaf, parent = packet["lineage"]
        self.assertEqual(leaf["handoff_sha256"], child["handoff_sha256"])
        self.assertEqual(parent["holds"], ["outcome_unknown", "paused", "context_review_required"])
        self.assertEqual(parent["context"]["revision"], 2)
        self.assertEqual(parent["returned_evidence"]["return_id"], "parent-return")
        self.assertEqual(parent["returned_evidence"]["state"], "returned_unverified")
        text = json.dumps(packet)
        for private_text in ("Synthetic", "https://", "unrelated-mission"):
            self.assertNotIn(private_text, text)
        self.assertEqual(packet["visibility"], "owner_private")
        self.assertEqual(packet["sender_authentication"], "not_established")
        parent["context"]["revision"] = 999
        self.assertEqual(self.inspect("followup-one")["lineage"][1]["context"]["revision"], 2)

    def test_recovery_inspection_rejects_stale_content_and_revisions(self):
        saved = self.save()
        first = self.inspect()
        self.profile["execution"]["detail"] = "New observation without changing memory revision."
        self.ledger.save_context(self.profile, expected_revision=1)
        for change in ({"expected_sha256": saved["context_sha256"]},
                       {"expected_source_revision": "f" * 40}, {"expected_memory_revision": 2},
                       {"expected_memory_revision": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.inspect(**change)
        self.assertNotEqual(self.inspect()["inspection_sha256"], first["inspection_sha256"])
        self.assertEqual(self.load()["revision"], 2)

    def test_recovery_inspection_keeps_legacy_parent_without_context(self):
        self.returned_parent()
        self.ledger.db.execute("DELETE FROM handoff_contexts WHERE handoff_id='mission-one'")
        self.stage_followup()
        public = self.context("followup-one")
        public.update(visibility="public_candidate", context_refs=[])
        self.ledger.save_context(public, expected_revision=0)
        packet = self.inspect("followup-one")
        self.assertEqual(packet["visibility"], "owner_private")
        self.assertFalse(packet["retry_authorized"])
        parent = packet["lineage"][1]
        self.assertIsNone(parent["context"])
        self.assertEqual(parent["returned_evidence"]["state"], "returned_unverified")

    def test_recovery_inspection_rejects_corrupt_ancestor_evidence(self):
        self.returned_parent()
        self.stage_followup()
        self.ledger.save_context(self.context("followup-one"), expected_revision=0)
        self.ledger.db.execute("UPDATE returns SET digest=?", ("0" * 64,))
        with self.assertRaisesRegex(ValueError, "return integrity"):
            self.inspect("followup-one")

    def check_inspection(self, packet):
        leaf = packet["lineage"][0]
        return self.ledger.check_recovery(packet["handoff_id"],
            expected_inspection_sha256=packet["inspection_sha256"],
            expected_sha256=leaf["context"]["context_sha256"],
            expected_source_revision=leaf["source_revision"],
            expected_memory_revision=leaf["context"]["memory_revision"])

    def test_checked_inspection_survives_restart_but_never_releases_hold(self):
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.approve()
        packet = self.inspect()
        before = list(self.ledger.db.iterdump())
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        checked = self.check_inspection(packet)
        self.assertEqual(checked["state"], "current_local_observation_only")
        self.assertFalse(checked["retry_authorized"])
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.assert_exports_blocked(saved["context_sha256"])
        with self.assertRaises(ValueError):
            self.check_inspection({**packet, "inspection_sha256": "0" * 64})

    def test_parent_context_and_review_changes_invalidate_child_inspection(self):
        self.returned_parent()
        self.stage_followup()
        self.ledger.save_context(self.context("followup-one"), expected_revision=0)
        original = self.inspect("followup-one")
        changed = deepcopy(self.profile)
        changed["execution"]["detail"] = "New ancestor observation."
        saved = self.ledger.save_context(changed, expected_revision=1)
        with self.assertRaisesRegex(ValueError, "inspection is stale"):
            self.check_inspection(original)
        refreshed = self.inspect("followup-one")
        self.assertEqual(original["lineage"][0], refreshed["lineage"][0])
        self.check_inspection(refreshed)
        self.ledger.review_context("mission-one", reviewer_id="local-evaluator", expected_sha256=saved["context_sha256"])
        with self.assertRaisesRegex(ValueError, "inspection is stale"):
            self.check_inspection(refreshed)

    def test_late_return_invalidates_inspection_without_clearing_unknown_outcome(self):
        saved = self.approve()
        self.export(saved["context_sha256"])
        self.profile["execution"]["state"] = "outcome_unknown"
        self.ledger.save_context(self.profile, expected_revision=1)
        original = self.inspect()
        self.ledger.import_return({"schema_version": 1, "kind": "jarvis.return", "return_id": "late-evidence",
            "handoff_id": "mission-one", "handoff_sha256": self.receipt["handoff_sha256"],
            "source_provider": "codex", "text": "Synthetic late return, still unverified.", "evidence_urls": []})
        with self.assertRaisesRegex(ValueError, "inspection is stale"):
            self.check_inspection(original)
        refreshed = self.inspect()
        self.assertEqual(original["lineage"][0]["context"], refreshed["lineage"][0]["context"])
        self.assertFalse(self.check_inspection(refreshed)["retry_authorized"])
        self.assert_exports_blocked(refreshed["lineage"][0]["context"]["context_sha256"])

    def proposal(self, inspection=None, **changes):
        packet = inspection or self.inspect()
        return self.ledger.prepare_reconciliation("mission-one", **{
            "expected_inspection_sha256": packet["inspection_sha256"],
            "expected_sha256": packet["lineage"][0]["context"]["context_sha256"],
            "expected_source_revision": REVISION, "expected_memory_revision": 1, **changes})

    def proposal_fixture(self):
        self.profile["execution"]["state"] = "outcome_unknown"
        self.profile["evidence_refs"] = [{"url": "https://example.invalid/observation", "revision": 2,
                                         "visibility": "owner_private"}]
        return self.approve()

    def test_reconciliation_proposal_retains_evidence_after_restart_without_state_change(self):
        saved = self.proposal_fixture()
        before = list(self.ledger.db.iterdump())
        first = self.proposal()
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        self.assertEqual(self.proposal(), first)
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.assertEqual(first["evidence_refs"], self.profile["evidence_refs"])
        self.assertEqual(first["execution"], self.profile["execution"])
        self.assertEqual(first["visibility"], "owner_private")
        self.assertEqual(first["review_state"], "proposed_unverified")
        self.assertEqual(first["proposed_resolution"], "retain_hold")
        self.assertFalse(first["retry_authorized"])
        self.assertNotIn("context_refs", first)
        checksum = first.pop("proposal_sha256")
        self.assertEqual(digest(first), checksum)
        first["evidence_refs"].clear()
        self.assertEqual(len(self.proposal()["evidence_refs"]), 1)
        self.assert_exports_blocked(saved["context_sha256"])

    def test_reconciliation_proposal_rejects_missing_evidence_and_known_outcomes(self):
        self.save()
        with self.assertRaises(ValueError):
            self.proposal()
        self.profile["execution"]["state"] = "outcome_unknown"
        self.ledger.save_context(self.profile, expected_revision=1)
        with self.assertRaises(ValueError):
            self.proposal()

    def test_reconciliation_proposal_rejects_stale_review_and_context(self):
        self.proposal_fixture()
        old = self.inspect()
        changed = deepcopy(self.profile)
        changed["evidence_refs"][0]["revision"] = 3
        self.ledger.save_context(changed, expected_revision=1)
        with self.assertRaises(ValueError):
            self.proposal(old)
        refreshed = self.inspect()
        self.ledger.review_context("mission-one", reviewer_id="local-evaluator",
            expected_sha256=refreshed["lineage"][0]["context"]["context_sha256"])
        with self.assertRaises(ValueError):
            self.proposal(refreshed)
        with self.assertRaises(ValueError):
            self.proposal(expected_memory_revision=2)

    def destination_profile(self, destination="repository-one"):
        return {**self.control_profile("active"), "schema_version": 3, "destination_id": destination}

    def test_destination_round_trip_requires_both_reviews_and_survives_restart(self):
        self.profile = self.destination_profile()
        saved = self.save()
        self.ledger.review("mission-one", reviewer_id="local-evaluator", expected_sha256=self.receipt["handoff_sha256"])
        self.assert_exports_blocked(saved["context_sha256"])
        self.ledger.review_context("mission-one", reviewer_id="local-evaluator", expected_sha256=saved["context_sha256"])
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        self.assertEqual(self.load()["profile"], self.profile)
        packet = self.export(saved["context_sha256"])
        self.assertEqual(packet["context"]["destination_id"], "repository-one")
        self.assertEqual(packet["handoff_sha256"], self.receipt["handoff_sha256"])
        self.assertNotIn("destination_id", packet["handoff"])

    def test_destination_cannot_be_silently_added_or_changed_or_downgraded(self):
        for version in (1, 2):
            bad = self.destination_profile()
            bad["schema_version"] = version
            if version == 1:
                del bad["control"]
            with self.assertRaises(ValueError):
                self.ledger.save_context(bad, expected_revision=0)
        self.profile = self.destination_profile()
        self.save()
        downgrade = self.control_profile("active")
        downgrade.pop("destination_id")
        for changed in (self.destination_profile("repository-two"), downgrade):
            with self.assertRaises(ValueError):
                self.ledger.save_context(changed, expected_revision=1)
        self.assertEqual(self.load()["profile"], self.profile)

    def test_destination_bound_handoff_cannot_export_without_its_context(self):
        self.profile = self.destination_profile()
        saved = self.approve()
        with self.assertRaisesRegex(ValueError, "context envelope"):
            self.ledger.export("mission-one", expected_sha256=self.receipt["handoff_sha256"])
        self.assertEqual(self.ledger.status()["handoffs"][0]["state"], "reviewed")
        packet = self.export(saved["context_sha256"])
        self.assertEqual(packet["context"]["destination_id"], "repository-one")
        self.assertEqual(packet["handoff_sha256"], self.receipt["handoff_sha256"])

    def test_destination_requires_a_bounded_opaque_identifier(self):
        for value in ("", "../outside", "https://example.invalid/channel", "a" * 129, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.ledger.save_context(self.destination_profile(value), expected_revision=0)
        self.assertEqual(self.ledger.db.execute("SELECT count(*) FROM handoff_contexts").fetchone()[0], 0)

    def test_destination_opt_in_only_before_original_review(self):
        self.save()
        self.profile = self.destination_profile()
        self.ledger.save_context(self.profile, expected_revision=1)
        self.stage("mission-two")
        other = self.context("mission-two")
        self.ledger.save_context(other, expected_revision=0)
        _, handoff = self.ledger._handoff("mission-two")
        self.ledger.review("mission-two", reviewer_id="local-evaluator", expected_sha256=digest(handoff))
        other.update(schema_version=3, destination_id="repository-two", control=self.profile["control"])
        with self.assertRaises(ValueError):
            self.ledger.save_context(other, expected_revision=1)
        self.assertEqual(self.load("mission-two")["profile"]["schema_version"], 1)

    def test_destination_records_are_independent_and_unknown_cancelled_state_is_retained(self):
        self.profile = self.destination_profile()
        self.profile["execution"]["state"] = "outcome_unknown"
        self.profile["control"]["state"] = "cancelled"
        saved = self.approve()
        self.stage("mission-two")
        other = {**self.context("mission-two"), "schema_version": 3, "destination_id": "repository-two",
                 "control": self.control_profile("active")["control"]}
        other["control"]["state"] = "active"
        self.ledger.save_context(other, expected_revision=0)
        self.assertEqual(self.load()["profile"]["destination_id"], "repository-one")
        self.assertEqual(self.load("mission-two")["profile"]["destination_id"], "repository-two")
        self.assert_exports_blocked(saved["context_sha256"])
        with self.assertRaises(ValueError):
            self.export(saved["context_sha256"], audience="public_candidate")
        self.assertEqual(self.load()["profile"]["execution"]["state"], "outcome_unknown")

    def test_destination_status_selects_exact_platform_and_destination_without_private_text(self):
        self.profile = self.destination_profile()
        self.profile["execution"]["state"] = "outcome_unknown"
        self.save()
        self.stage("mission-two", target="github")
        other = {**self.context("mission-two"), "schema_version": 3, "destination_id": "repository-one",
                 "control": self.profile["control"]}
        self.ledger.save_context(other, expected_revision=0)
        for name, destination in (("third", "repository-two"), ("legacy", None)):
            staged = self.ledger.stage({"schema_version": 1, "kind": "jarvis.draft", "project_id": "ai-jarvis",
                "target": "codex", "text": "Unrelated private fixture."}, self.manifest,
                assistant_id="memory-pilot.evaluator", handoff_id=name)
            profile = self.context(name)
            profile["asset_id"] = "memory-pilot.evaluator"
            if destination:
                profile.update(schema_version=3, destination_id=destination, control=self.profile["control"])
            self.ledger.save_context(profile, expected_revision=0)
        before = list(self.ledger.db.iterdump())
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        query = dict(project_id="ai-jarvis", platform="codex", destination_id="repository-one")
        result = self.ledger.destination_status(**query)
        self.assertEqual([r["handoff_id"] for r in result["records"]], ["mission-one"])
        self.assertEqual(result["records"][0]["execution_state"], "outcome_unknown")
        self.assertFalse(result["dispatch_authorized"])
        self.assertEqual(result["visibility"], "owner_private")
        self.assertEqual(result["sender_authentication"], "not_established")
        for text in ("https://", "Synthetic", "Unrelated", "mission-two"):
            self.assertNotIn(text, json.dumps(result))
        result["records"].clear()
        self.assertEqual(len(self.ledger.destination_status(**query)["records"]), 1)
        self.assertEqual(list(self.ledger.db.iterdump()), before)

    def test_destination_status_project_isolation_and_empty_results(self):
        self.profile = self.destination_profile()
        self.save()
        for change in ({"project_id": "publishing-studio"}, {"platform": "github"},
                       {"destination_id": "repository-two"}):
            query = dict(project_id="ai-jarvis", platform="codex", destination_id="repository-one")
            query.update(change)
            self.assertEqual(self.ledger.destination_status(**query)["records"], [])

    def test_destination_status_rejects_invalid_scope_and_corrupt_context(self):
        query = dict(project_id="ai-jarvis", platform="codex", destination_id="repository-one")
        for change in ({"project_id": "unknown"}, {"platform": []}, {"destination_id": "../outside"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.ledger.destination_status(**{**query, **change})
        self.profile = self.destination_profile()
        self.save()
        self.ledger.db.execute("UPDATE handoff_contexts SET body='{}'")
        with self.assertRaises(ValueError):
            self.ledger.destination_status(**query)

    def test_exports_reject_changed_registered_configuration_after_reopen(self):
        saved = self.approve()
        row = self.ledger.db.execute("SELECT * FROM swarms").fetchone()
        manifest = json.loads(row["body"])
        manifest["assistants"][0]["max_handoffs"] = 99
        self.ledger.db.execute("UPDATE swarms SET body=?", (json.dumps(manifest),))
        before = list(self.ledger.db.iterdump())
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        for export in (lambda: self.ledger.export("mission-one", expected_sha256=self.receipt["handoff_sha256"]),
                       lambda: self.export(saved["context_sha256"])):
            with self.subTest(export=export), self.assertRaises(ValueError):
                export()
        self.assertEqual(list(self.ledger.db.iterdump()), before)

    def test_exports_reject_registered_manifest_digest_mismatch(self):
        saved = self.approve()
        self.ledger.db.execute("UPDATE swarms SET digest=?", ("0" * 64,))
        self.assert_exports_blocked(saved["context_sha256"])

    def test_legacy_export_rejects_rehashed_handoff_outside_its_registered_project(self):
        _, handoff = self.ledger._handoff("mission-one")
        handoff["draft"]["project_id"] = "publishing-studio"
        checksum = digest(handoff)
        self.ledger.db.execute("UPDATE handoffs SET body=?,digest=?,reviewed_digest=?,reviewer_id='local-evaluator',state='reviewed' WHERE id=?",
            (json.dumps(handoff), checksum, checksum, "mission-one"))
        before = list(self.ledger.db.iterdump())
        with self.assertRaises(ValueError):
            self.ledger.export("mission-one", expected_sha256=checksum)
        self.assertEqual(list(self.ledger.db.iterdump()), before)

    def observation(self, provider="codex", **changes):
        values = dict(observed_at="2026-10-28T00:00:00Z", evidence_url="https://example.invalid/read",
                      response_sha256="a" * 64, scope="Synthetic metadata read", source_revision=REVISION)
        return read_observation(provider, **{**values, **changes})

    def bind_observation(self, observation, checksum=None):
        return self.ledger.bind_destination_observation("mission-one", observation,
            expected_sha256=checksum or self.load()["context_sha256"], expected_source_revision=REVISION,
            expected_memory_revision=1, now=datetime(2026, 10, 28, 1, tzinfo=timezone.utc))

    def test_destination_observation_retains_bindings_without_changing_holds_or_records(self):
        self.profile = self.destination_profile()
        self.profile["execution"]["state"] = "outcome_unknown"
        self.profile["control"]["state"] = "cancelled"
        saved = self.approve()
        original = self.observation()
        before = list(self.ledger.db.iterdump())
        bound = self.bind_observation(original)
        self.assertEqual(bound["destination_id"], "repository-one")
        self.assertEqual(bound["observation"], original)
        self.assertEqual(bound["observation_status"], "read_observed")
        self.assertEqual(bound["runtime_available"], "unknown")
        self.assertFalse(bound["dispatch_authorized"])
        self.assertNotIn("execution", bound)
        self.assertNotIn("context_refs", bound)
        self.assertEqual(bound["visibility"], "owner_private")
        checksum = bound.pop("receipt_sha256")
        self.assertEqual(digest(bound), checksum)
        bound["observation"]["scope"] = "Changed returned metadata."
        self.assertEqual(self.observation(), original)
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.assert_exports_blocked(saved["context_sha256"])

    def test_destination_observation_rejects_mismatch_tampering_and_legacy_context(self):
        self.save()
        with self.assertRaises(ValueError):
            self.bind_observation(self.observation())
        self.profile = self.destination_profile()
        saved = self.ledger.save_context(self.profile, expected_revision=1)
        tampered = self.observation()
        tampered["response_sha256"] = "b" * 64
        for record in (tampered, self.observation("github"), self.observation(source_revision="f" * 40)):
            with self.subTest(record=record), self.assertRaises(ValueError):
                self.bind_observation(record)
        changed = deepcopy(self.profile)
        changed["execution"]["detail"] = "New selected context."
        self.ledger.save_context(changed, expected_revision=2)
        with self.assertRaises(ValueError):
            self.bind_observation(self.observation(), saved["context_sha256"])

    def test_destination_observation_preserves_stale_status_and_rejects_future_time(self):
        self.profile = self.destination_profile()
        self.save()
        old = self.bind_observation(self.observation(observed_at="2026-10-20T00:00:00Z"))
        self.assertEqual(old["observation_status"], "unverified")
        with self.assertRaises(ValueError):
            self.bind_observation(self.observation(observed_at="2026-10-29T00:00:00Z"))

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
        self.assert_exports_blocked(updated["context_sha256"])
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
