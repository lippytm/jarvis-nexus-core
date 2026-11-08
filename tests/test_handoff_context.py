"""Synthetic local recovery fixtures; no provider call or hosted service."""
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

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

    def test_export_revision_rejects_restored_content_before_state_change(self):
        saved = self.approve()
        changed = deepcopy(self.profile)
        changed["execution"]["detail"] = "Synthetic intervening context."
        self.ledger.save_context(changed, expected_revision=1)
        restored = self.ledger.save_context(self.profile, expected_revision=2)
        self.assertEqual(restored["context_sha256"], saved["context_sha256"])
        self.ledger.review_context("mission-one", reviewer_id="local-evaluator",
            expected_sha256=saved["context_sha256"], expected_revision=3)
        before = tuple(self.ledger.db.iterdump())
        for revision in (1, 2, 4, 0, -1, True, 3.0, "3"):
            with self.subTest(revision=revision):
                with self.assertRaisesRegex(ValueError, "context export revision"):
                    self.export(saved["context_sha256"], expected_revision=revision)
                self.assertEqual(tuple(self.ledger.db.iterdump()), before)
                self.assertEqual(self.ledger._handoff("mission-one")[0]["state"], "reviewed")
        with self.assertRaisesRegex(ValueError, "public envelope"):
            self.export(saved["context_sha256"], expected_revision=3, audience="public_candidate")
        self.assertEqual(tuple(self.ledger.db.iterdump()), before)
        packet = self.export(saved["context_sha256"], expected_revision=3)
        self.assertEqual(packet["context_revision"], 3)
        self.assertEqual(packet["schema_version"], 1)
        self.assertEqual(packet["context"], self.profile)
        self.assertEqual(packet["external_actions"], 0)
        self.assertEqual(self.ledger._handoff("mission-one")[0]["state"], "export_prepared")
        self.assertEqual(self.export(saved["context_sha256"]), packet)
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        self.assertEqual(self.load()["profile"], self.profile)
        self.assertEqual(self.load()["revision"], 3)

    def test_unknown_stored_handoff_state_rejects_private_readers_after_restart(self):
        self.approve()
        # Simulate an invalid restored row; normal SQLite writes enforce CHECK.
        self.ledger.db.execute("PRAGMA ignore_check_constraints=ON")
        self.ledger.db.execute("UPDATE handoffs SET state='unrecognized' WHERE id='mission-one'")
        self.ledger.db.commit()
        self.ledger.close()
        before = self.path.read_bytes()
        self.ledger = HandoffLedger(self.path, read_only=True)
        for observe in (self.ledger.status,
                        lambda: self.ledger.queue_report(project_id="ai-jarvis"),
                        lambda: self.ledger.load_context("mission-one",
                            expected_source_revision=REVISION, expected_memory_revision=1)):
            with self.subTest(reader=observe):
                with self.assertRaisesRegex(ValueError, "stored handoff state"):
                    observe()
                self.assertFalse(self.ledger.db.in_transaction)
                self.assertEqual(self.path.read_bytes(), before)
    def test_duplicate_stored_json_keys_reject_after_restart_without_rewriting_records(self):
        self.approve()
        guards = dict(expected_source_revision=REVISION, expected_memory_revision=1)
        self.ledger.checkpoint_context("mission-one", expected_sha256=digest(self.profile), **guards)
        changed = deepcopy(self.profile)
        changed["execution"]["detail"] = "Synthetic second checkpoint."
        self.ledger.save_context(changed, expected_revision=1)
        self.ledger.checkpoint_context("mission-one", expected_sha256=digest(changed), **guards)
        returned = self.stage("returned-neighbor", target="gemini")
        self.ledger.review("returned-neighbor", reviewer_id="local-evaluator",
            expected_sha256=returned["handoff_sha256"])
        self.ledger.export("returned-neighbor", expected_sha256=returned["handoff_sha256"])
        self.ledger.import_return(dict(schema_version=1, kind="jarvis.return", return_id="result-one",
            handoff_id="returned-neighbor", handoff_sha256=returned["handoff_sha256"],
            source_provider="gemini", text="Synthetic unverified return.", evidence_urls=[]))
        checkpoint = lambda: self.ledger.load_checkpoint("mission-one", 2,
            expected_sha256=digest(changed), **guards)
        cases = [
            ("swarms", "id='memory-pilot'", self.ledger.status, False),
            ("handoffs", "id='mission-one'", self.ledger.status, False),
            ("returns", "id='result-one'", self.ledger.status, False),
            ("handoff_contexts", "handoff_id='mission-one'", lambda: self.load(), False),
            ("context_checkpoints", "revision=2", checkpoint, False),
            ("context_checkpoints", "revision=1", checkpoint, False),
            ("handoff_contexts", "handoff_id='mission-one'", lambda: self.load(), True),
        ]
        # Resolve bound status calls only after each fresh connection is opened.
        for table, where, observe, nested in cases:
            with self.subTest(table=table, where=where, nested=nested):
                self.ledger.close()
                with sqlite3.connect(self.path) as writer:
                    original = writer.execute(f"SELECT body FROM {table} WHERE {where}").fetchone()[0]
                    if nested:
                        ambiguous = original.replace('"execution":{', '"execution":{"attempts":999,', 1)
                    else:
                        ambiguous = '{"schema_version":999,' + original[1:]
                    self.assertNotEqual(ambiguous, original)
                    self.assertEqual(json.loads(ambiguous), json.loads(original))
                    writer.execute(f"UPDATE {table} SET body=? WHERE {where}", (ambiguous,))
                before = self.path.read_bytes()
                self.ledger = HandoffLedger(self.path, read_only=True)
                with self.assertRaisesRegex(ValueError, "stored"):
                    if table in {"swarms", "handoffs", "returns"}:
                        self.ledger.status()
                    else:
                        observe()
                self.assertFalse(self.ledger.db.in_transaction)
                self.assertEqual(self.path.read_bytes(), before)
                self.ledger.close()
                with sqlite3.connect(self.path) as writer:
                    writer.execute(f"UPDATE {table} SET body=? WHERE {where}", (original,))
                self.ledger = HandoffLedger(self.path, read_only=True)
                self.assertEqual(self.load()["profile"], changed)
                self.assertEqual(checkpoint()["profile"], changed)
                self.assertEqual(self.ledger.status()["return_count"], 1)

    def test_oversized_stored_context_rejects_after_restart_before_json_parsing(self):
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        self.approve()
        original = self.ledger.db.execute("SELECT body FROM handoff_contexts").fetchone()[0]
        ambiguous_size = original + " " * 65536
        self.ledger.db.execute("UPDATE handoff_contexts SET body=?", (ambiguous_size,))
        self.ledger.db.commit()
        self.ledger.close()
        before = self.path.read_bytes()
        self.ledger = HandoffLedger(self.path, read_only=True)
        with self.assertRaisesRegex(ValueError, "stored context"):
            self.load()
        self.assertFalse(self.ledger.db.in_transaction)
        self.assertEqual(self.path.read_bytes(), before)
        self.ledger.close()
        with sqlite3.connect(self.path) as writer:
            writer.execute("UPDATE handoff_contexts SET body=?", (original,))
        self.ledger = HandoffLedger(self.path, read_only=True)
        resumed = self.load()
        self.assertEqual(resumed["profile"], self.profile)
        self.assertEqual(resumed["review_state"], "locally_reviewed")

    def test_stored_json_bounds_utf8_before_parse_and_keeps_boundary_records(self):
        from unittest.mock import patch
        from control_tower.handoffs import _stored_json
        from control_tower.network_contract import MAX_PACKET_BYTES
        # Exact raw-byte boundary remains parseable, including noncanonical whitespace.
        boundary = '{}' + ' ' * (MAX_PACKET_BYTES - 2)
        self.assertEqual(_stored_json(boundary), {})
        self.assertEqual(_stored_json(boundary.encode()), {})
        for oversized in (boundary + ' ', (boundary + ' ').encode(),
                          json.dumps({"text": "é" * 40000}, ensure_ascii=False)):
            with self.subTest(kind=type(oversized).__name__):
                with patch("control_tower.handoffs.json.loads") as parser:
                    with self.assertRaisesRegex(ValueError, "stored JSON"):
                        _stored_json(oversized)
                    parser.assert_not_called()
        with self.assertRaises(ValueError):
            _stored_json('{"key":1,"key":2}')

    def test_export_revision_match_does_not_bypass_holds_or_reviews(self):
        for state in ("paused", "cancelled", "outcome_unknown", "unreviewed"):
            with self.subTest(state=state):
                swarm_id = "hold-" + state
                manifest = build_swarm("ai-jarvis", ["gemini"], swarm_id=swarm_id, source_revision=REVISION)
                staged = self.ledger.stage({"schema_version": 1, "kind": "jarvis.draft",
                    "project_id": "ai-jarvis", "target": "gemini", "text": "Synthetic held draft."},
                    manifest, assistant_id=swarm_id + ".builder", handoff_id=state)
                profile = self.context(state)
                profile["asset_id"] = swarm_id + ".builder"
                if state in ("paused", "cancelled"):
                    profile.update(schema_version=2, control={"state": state,
                        "actor_id": "local-controller", "reason": "Synthetic hold."})
                elif state == "outcome_unknown":
                    profile["execution"]["state"] = state
                saved = self.ledger.save_context(profile, expected_revision=0)
                self.ledger.review(state, reviewer_id="local-evaluator",
                    expected_sha256=staged["handoff_sha256"])
                if state != "unreviewed":
                    self.ledger.review_context(state, reviewer_id="local-evaluator",
                        expected_sha256=saved["context_sha256"])
                before = tuple(self.ledger.db.iterdump())
                with self.assertRaises(ValueError):
                    self.ledger.export_context(state, expected_sha256=saved["context_sha256"],
                        expected_source_revision=REVISION, expected_memory_revision=1, expected_revision=1)
                self.assertEqual(tuple(self.ledger.db.iterdump()), before)

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

    def test_load_context_optional_digest_rejects_same_memory_edit_after_restart(self):
        self.profile["execution"]["state"] = "outcome_unknown"
        first = self.approve()
        legacy = self.load()
        self.assertEqual(self.load(expected_sha256=first["context_sha256"]), legacy)
        self.stage("mission-two")
        other = self.ledger.save_context(self.context("mission-two"), expected_revision=0)
        self.assertEqual(self.load(expected_sha256=first["context_sha256"]), legacy)
        self.profile["execution"]["detail"] = "New private detail with the same source and memory revision."
        changed = self.ledger.save_context(self.profile, expected_revision=1)
        self.ledger.close()
        before = self.path.read_bytes()
        self.ledger = HandoffLedger(self.path, read_only=True)
        for value in (first["context_sha256"], other["context_sha256"], "0" * 64):
            with self.assertRaisesRegex(ValueError, "context digest mismatch"):
                self.load(expected_sha256=value)
        for value in (True, "bad", "A" * 64, ""):
            with self.assertRaises(ValueError):
                self.load(expected_sha256=value)
        current = self.load(expected_sha256=changed["context_sha256"])
        self.assertEqual(current, self.load())
        self.assertEqual(current["profile"], self.profile)
        self.assertEqual(current["review_state"], "proposed")
        self.assertEqual(current["profile"]["execution"]["state"], "outcome_unknown")
        with self.assertRaisesRegex(ValueError, "private context"):
            self.load(expected_sha256=changed["context_sha256"], audience="public_candidate")
        self.assertEqual(self.load("mission-two", expected_sha256=other["context_sha256"])["profile"],
                         self.context("mission-two"))
        self.assertFalse(self.ledger.db.in_transaction)
        self.assertEqual(self.path.read_bytes(), before)

    def test_load_context_revision_guard_rejects_restored_content_after_restart(self):
        self.profile = self.control_profile("paused")
        self.profile["execution"]["state"] = "outcome_unknown"
        first = self.approve()
        original = deepcopy(self.profile)
        self.profile["execution"]["detail"] = "Temporary edit before identical content is restored."
        self.ledger.save_context(self.profile, expected_revision=1)
        restored = self.ledger.save_context(original, expected_revision=2)
        self.assertEqual(restored["context_sha256"], first["context_sha256"])
        self.stage("mission-two", target="gemini")
        neighbor = self.context("mission-two")
        self.ledger.save_context(neighbor, expected_revision=0)
        self.ledger.close()
        before = self.path.read_bytes()
        self.ledger = HandoffLedger(self.path, read_only=True)
        for revision in (1, 2, 4):
            with self.subTest(stale=revision), self.assertRaisesRegex(ValueError, "context retrieval revision mismatch"):
                self.load(expected_sha256=first["context_sha256"], expected_revision=revision)
        for revision in (True, 0, -1, "3"):
            with self.subTest(invalid=revision), self.assertRaises(ValueError):
                self.load(expected_revision=revision)
        current = self.load(expected_sha256=restored["context_sha256"], expected_revision=3)
        self.assertEqual(current, self.load())
        self.assertEqual(current["profile"], original)
        self.assertEqual(current["review_state"], "proposed")
        with self.assertRaisesRegex(ValueError, "private context"):
            self.load(expected_revision=3, audience="public_candidate")
        self.assertEqual(self.load("mission-two", expected_revision=1)["profile"], neighbor)
        self.assertFalse(self.ledger.db.in_transaction)
        self.assert_exports_blocked(restored["context_sha256"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_context_review_revision_guard_rejects_restored_content_after_restart(self):
        self.profile = self.control_profile("paused")
        self.profile["execution"]["state"] = "outcome_unknown"
        first = self.approve()
        original = deepcopy(self.profile)
        self.profile["execution"]["detail"] = "Temporary private edit at the same memory revision."
        self.ledger.save_context(self.profile, expected_revision=1)
        restored = self.ledger.save_context(original, expected_revision=2)
        self.assertEqual(restored["context_sha256"], first["context_sha256"])
        self.assertEqual(restored["revision"], 3)
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        before = list(self.ledger.db.iterdump())
        args = dict(reviewer_id="local-evaluator", expected_sha256=first["context_sha256"])
        for revision in (1, 2, 4):
            with self.assertRaisesRegex(ValueError, "context review revision mismatch"):
                self.ledger.review_context("mission-one", **args, expected_revision=revision)
        for revision in (True, 0, -1, "3"):
            with self.assertRaises(ValueError):
                self.ledger.review_context("mission-one", **args, expected_revision=revision)
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.assertEqual(self.load()["review_state"], "proposed")
        with self.assertRaises(ValueError):
            self.ledger.review_context("mission-one", **{**args, "reviewer_id": original["asset_id"]}, expected_revision=3)
        with self.assertRaises(ValueError):
            self.ledger.review_context("mission-one", **{**args, "expected_sha256": "0" * 64}, expected_revision=3)
        self.ledger.review_context("mission-one", **args, expected_revision=3)
        self.assertEqual(self.load()["review_state"], "locally_reviewed")
        self.assertEqual(self.load()["profile"], original)
        self.assert_exports_blocked(first["context_sha256"])
        # Digest-only callers retain the prior contract, with no schema change.
        self.ledger.review_context("mission-one", **args)
        self.assertFalse(self.ledger.db.in_transaction)

    def test_context_review_receipt_retains_exact_provenance_without_profile_text(self):
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        args = dict(reviewer_id="local-evaluator", expected_sha256=saved["context_sha256"])
        before = list(self.ledger.db.iterdump())
        for value in (None, 0, "true", []):
            with self.assertRaises(ValueError):
                self.ledger.review_context("mission-one", **args, expected_revision=1, include_receipt=value)
        with self.assertRaisesRegex(ValueError, "exact context revision"):
            self.ledger.review_context("mission-one", **args, include_receipt=True)
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        receipt = self.ledger.review_context("mission-one", **args, expected_revision=1, include_receipt=True)
        self.assertEqual((receipt["schema_version"], receipt["kind"]), (1, "jarvis.context_review_receipt"))
        for key in ("handoff_id", "handoff_sha256", "project_id", "mission_id", "asset_id", "platform",
                    "source_revision", "memory_revision", "configuration_version", "destination_id"):
            self.assertEqual(receipt[key], self.profile[key])
        self.assertEqual((receipt["context_schema_version"], receipt["context_revision"]), (3, 1))
        self.assertEqual(receipt["context_sha256"], saved["context_sha256"])
        self.assertIsNotNone(datetime.fromisoformat(receipt["recorded_at"]).tzinfo)
        self.assertEqual(receipt["receipt_sha256"], digest({k: v for k, v in receipt.items() if k != "receipt_sha256"}))
        self.assertEqual((receipt["execution_state"], receipt["control_state"]), ("outcome_unknown", "paused"))
        self.assertEqual(receipt["visibility"], "owner_private")
        for flag in ("dispatch_authorized", "retry_authorized", "external_actions"):
            self.assertFalse(receipt[flag])
        self.assertNotIn("https://", json.dumps(receipt))
        self.assertNotIn("detail", receipt)
        self.assertIsNone(self.ledger.review_context("mission-one", **args))
        self.stage("mission-two")
        other = self.ledger.save_context(self.context("mission-two"), expected_revision=0)
        legacy = self.ledger.review_context("mission-two", reviewer_id="local-evaluator",
            expected_sha256=other["context_sha256"], expected_revision=1, include_receipt=True)
        self.assertIsNone(legacy["destination_id"])
        self.assertEqual(legacy["control_state"], "legacy_uncontrolled")
        receipt["mission_id"] = "changed-returned-copy"
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        self.assertEqual(self.load()["profile"], self.profile)
        self.assertEqual(self.load()["review_state"], "locally_reviewed")
        self.assertEqual(self.load("mission-two")["profile"], self.context("mission-two"))

    def test_saved_review_receipt_checks_after_restart_without_writes(self):
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        receipt = self.ledger.review_context("mission-one", reviewer_id="local-evaluator",
            expected_sha256=saved["context_sha256"], expected_revision=1, include_receipt=True)
        self.stage("mission-two")
        other = self.ledger.save_context(self.context("mission-two"), expected_revision=0)
        legacy = self.ledger.review_context("mission-two", reviewer_id="local-evaluator",
            expected_sha256=other["context_sha256"], expected_revision=1, include_receipt=True)
        self.ledger.close()
        before = self.path.read_bytes()
        self.ledger = HandoffLedger(self.path, read_only=True)
        for identifier, original in (("mission-one", receipt), ("mission-two", legacy)):
            retained = json.loads(json.dumps(original))
            checked = self.ledger.check_context_review_receipt(identifier, retained)
            self.assertTrue(checked["local_binding_matches"])
            self.assertEqual(checked["receipt_sha256"], original["receipt_sha256"])
            self.assertEqual(checked["authority"], "local_record_only_not_identity_authentication")
            self.assertFalse(checked["dispatch_authorized"])
            self.assertFalse(checked["retry_authorized"])
            self.assertNotIn("https://", json.dumps(checked))
            self.assertEqual(retained, original)
        self.assertEqual(self.load()["profile"], self.profile)
        self.assertEqual(self.path.read_bytes(), before)

    def test_duplicate_context_save_preserves_review_receipt_and_holds_after_restart(self):
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        receipt = self.ledger.review_context("mission-one", reviewer_id="local-evaluator",
            expected_sha256=saved["context_sha256"], expected_revision=1, include_receipt=True)
        self.stage("mission-two", target="gemini")
        neighbor = self.context("mission-two")
        self.ledger.save_context(neighbor, expected_revision=0)
        before = list(self.ledger.db.iterdump())
        for _ in range(2):
            duplicate = self.ledger.save_context(deepcopy(self.profile), expected_revision=1)
            self.assertEqual(duplicate, {**saved, "duplicate": True})
            self.assertTrue(self.ledger.check_context_review_receipt(
                "mission-one", json.loads(json.dumps(receipt)))["local_binding_matches"])
        with self.assertRaisesRegex(ValueError, "context revision mismatch"):
            self.ledger.save_context(deepcopy(self.profile), expected_revision=0)
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.assertFalse(self.ledger.db.in_transaction)
        self.ledger.close()
        database_bytes = self.path.read_bytes()
        self.ledger = HandoffLedger(self.path, read_only=True)
        checked = self.ledger.check_context_review_receipt("mission-one", receipt)
        self.assertEqual(checked["context_revision"], 1)
        for flag in ("dispatch_authorized", "retry_authorized", "external_actions"):
            self.assertFalse(checked[flag])
        self.assertEqual(self.load()["profile"], self.profile)
        self.assertEqual(self.load()["review_state"], "locally_reviewed")
        self.assertEqual(self.load("mission-two")["profile"], neighbor)
        with self.assertRaisesRegex(ValueError, "private context"):
            self.load(audience="public_candidate")
        self.assert_exports_blocked(saved["context_sha256"])
        self.assertEqual(self.path.read_bytes(), database_bytes)

    def test_saved_review_receipt_rejects_tampering_and_stale_bindings(self):
        saved = self.save()
        args = dict(reviewer_id="local-evaluator", expected_sha256=saved["context_sha256"],
                    expected_revision=1, include_receipt=True)
        receipt = self.ledger.review_context("mission-one", **args)
        before = list(self.ledger.db.iterdump())
        for key, value in (("mission_id", "other"), ("platform", "github"), ("context_revision", True),
                           ("visibility", "public_candidate"), ("dispatch_authorized", True),
                           ("source_revision", "0" * 40), ("reviewer_label", "other-reviewer"),
                           ("destination_id", "other"), ("schema_version", True),
                           ("extra", "unsupported"), ("recorded_at", "2026-11-06T00:00:00")):
            altered = {**receipt, key: value}
            altered["receipt_sha256"] = digest({k: v for k, v in altered.items() if k != "receipt_sha256"})
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.ledger.check_context_review_receipt("mission-one", altered)
        with self.assertRaises(ValueError):
            self.ledger.check_context_review_receipt("mission-one", {**receipt, "receipt_sha256": "0" * 64})
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.ledger.review_context("mission-one", **{**args, "reviewer_id": "other-evaluator"})
        with self.assertRaisesRegex(ValueError, "current binding"):
            self.ledger.check_context_review_receipt("mission-one", receipt)
        self.profile["execution"]["detail"] = "Changed then restored at same source/memory revision."
        self.ledger.save_context(self.profile, expected_revision=1)
        with self.assertRaisesRegex(ValueError, "no longer"):
            self.ledger.check_context_review_receipt("mission-one", receipt)
        self.profile = self.context("mission-one")
        restored = self.ledger.save_context(self.profile, expected_revision=2)
        self.assertEqual(restored["context_sha256"], saved["context_sha256"])
        self.ledger.review_context("mission-one", **{**args, "expected_revision": 3})
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        with self.assertRaisesRegex(ValueError, "current binding"):
            self.ledger.check_context_review_receipt("mission-one", receipt)

    def test_review_receipt_api_bounds_json_before_hashing_or_ledger_access(self):
        saved = self.save()
        receipt = self.ledger.review_context("mission-one", reviewer_id="local-evaluator",
            expected_sha256=saved["context_sha256"], expected_revision=1, include_receipt=True)
        cyclic = []
        cyclic.append(cyclic)
        deep = []
        for _ in range(20):
            deep = [deep]
        values = ({"unsupported"}, cyclic, deep, [0] * 2050, "x" * 70000,
                  float("nan"), "\ud800", {"password": "synthetic-not-a-secret"})
        before = list(self.ledger.db.iterdump())
        for index, value in enumerate(values):
            invalid = {**receipt, "extra": value}
            try:
                invalid["receipt_sha256"] = digest({k: v for k, v in invalid.items() if k != "receipt_sha256"})
            except (TypeError, ValueError, RecursionError, UnicodeError):
                pass
            with self.subTest(case=index), patch.object(self.ledger, "_transaction") as transaction, \
                    patch("control_tower.handoffs.digest") as hasher:
                with self.assertRaises(ValueError):
                    self.ledger.check_context_review_receipt("mission-one", invalid)
                hasher.assert_not_called()
                transaction.assert_not_called()
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.assertTrue(self.ledger.check_context_review_receipt("mission-one", receipt)["local_binding_matches"])

    def test_receipt_check_keeps_one_snapshot_during_concurrent_context_edit(self):
        self.assertEqual(self.ledger.db.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        first = self.save()
        receipt = self.ledger.review_context("mission-one", reviewer_id="local-evaluator",
            expected_sha256=first["context_sha256"], expected_revision=1, include_receipt=True)
        self.stage("mission-two")
        other = self.ledger.save_context(self.context("mission-two"), expected_revision=0)
        other_receipt = self.ledger.review_context("mission-two", reviewer_id="local-evaluator",
            expected_sha256=other["context_sha256"], expected_revision=1, include_receipt=True)
        edited = deepcopy(self.profile)
        edited["memory_revision"] = 2
        edited["execution"]["detail"] = "Concurrent writer retained the unknown outcome and pause."
        committed = []
        with HandoffLedger(self.path, read_only=True) as reader:
            expected = reader.check_context_review_receipt("mission-one", receipt)
            handoff = reader._handoff

            def edit_between_reads(identifier):
                selected = handoff(identifier)  # Establish the real SQLite read snapshot.
                if not committed:
                    committed.append(self.ledger.save_context(edited, expected_revision=1))
                return selected

            with patch.object(reader, "_handoff", side_effect=edit_between_reads):
                checked = reader.check_context_review_receipt("mission-one", receipt)
            self.assertEqual(len(committed), 1)
            self.assertEqual(checked, expected)
            self.assertFalse(reader.db.in_transaction)
            writer_rows = list(self.ledger.db.iterdump())
            with self.assertRaisesRegex(ValueError, "no longer has an exact local review"):
                reader.check_context_review_receipt("mission-one", receipt)
            self.assertFalse(reader.db.in_transaction)
            self.assertTrue(reader.check_context_review_receipt("mission-two", other_receipt)["local_binding_matches"])
            self.assertEqual(list(self.ledger.db.iterdump()), writer_rows)
        refreshed = self.ledger.review_context("mission-one", reviewer_id="local-evaluator",
            expected_sha256=committed[0]["context_sha256"], expected_revision=2, include_receipt=True)
        with HandoffLedger(self.path, read_only=True) as restarted:
            self.assertTrue(restarted.check_context_review_receipt("mission-one", refreshed)["local_binding_matches"])
            with self.assertRaisesRegex(ValueError, "current binding"):
                restarted.check_context_review_receipt("mission-one", receipt)
            self.assertEqual(restarted.load_context("mission-one", expected_source_revision=REVISION,
                expected_memory_revision=2)["profile"], edited)
            self.assertEqual(restarted.load_context("mission-two", expected_source_revision=REVISION,
                expected_memory_revision=1)["profile"], self.context("mission-two"))
        for flag in ("dispatch_authorized", "retry_authorized", "external_actions"):
            self.assertFalse(checked[flag])
        self.assert_exports_blocked(committed[0]["context_sha256"])

    def test_failed_review_commit_rolls_back_without_receipt_or_pending_writes(self):
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        self.stage("mission-two")
        self.ledger.save_context(self.context("mission-two"), expected_revision=0)
        before = list(self.ledger.db.iterdump())
        commits = []

        def deny_commit(action, name, *_):
            if action == sqlite3.SQLITE_TRANSACTION and name == "COMMIT":
                commits.append(name)
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        returned = []
        self.ledger.db.set_authorizer(deny_commit)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                returned.append(self.ledger.review_context("mission-one", reviewer_id="local-evaluator",
                    expected_sha256=saved["context_sha256"], expected_revision=1, include_receipt=True))
        finally:
            self.ledger.db.set_authorizer(None)
        self.assertEqual(commits, ["COMMIT"])
        self.assertEqual(returned, [])
        self.assertFalse(self.ledger.db.in_transaction)
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        # A later commit must not publish writes from the rejected review.
        self.ledger.db.commit()
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.assertEqual(self.load()["review_state"], "proposed")
        self.assertEqual(self.load()["profile"], self.profile)
        self.assertEqual(self.load("mission-two")["profile"], self.context("mission-two"))

    def test_failed_initialization_closes_connection_and_rolls_back_schema(self):
        from contextlib import closing
        connect = sqlite3.connect
        seed_rows = tuple(self.ledger.db.iterdump())
        triggers = ("PRAGMA foreign_keys=ON", "PRAGMA user_version",
                    "CREATE TABLE IF NOT EXISTS handoff_contexts")
        for phase, trigger in enumerate(triggers):
            for error_type in (KeyboardInterrupt, SystemExit, sqlite3.OperationalError):
                with self.subTest(phase=phase, error=error_type.__name__):
                    failure = error_type("Synthetic interrupted ledger initialization")
                    connections, returned = [], []

                    class InterruptedConnection(sqlite3.Connection):
                        close_calls = 0

                        def execute(connection, sql, *args, **kwargs):
                            result = super().execute(sql, *args, **kwargs)
                            if sql.startswith(trigger):
                                raise failure
                            return result

                        def close(connection):
                            connection.close_calls += 1
                            return super().close()

                    def capture(*args, **kwargs):
                        connection = connect(*args, **kwargs, factory=InterruptedConnection)
                        connections.append(connection)
                        return connection

                    path = self.path.parent / f"initialization-{phase}-{error_type.__name__}.sqlite3"
                    try:
                        with patch("control_tower.handoffs.sqlite3.connect", side_effect=capture):
                            with self.assertRaises(error_type) as raised:
                                returned.append(HandoffLedger(path))
                        self.assertIs(raised.exception, failure)
                        self.assertEqual(returned, [])
                        self.assertEqual(len(connections), 1)
                        self.assertEqual(connections[0].close_calls, 1)
                        with self.assertRaises(sqlite3.ProgrammingError):
                            connections[0].execute("SELECT 1")
                        with closing(connect(path)) as inspected:
                            self.assertEqual(inspected.execute("PRAGMA user_version").fetchone()[0], 0)
                            self.assertEqual(inspected.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [])
                        with HandoffLedger(path) as restarted:
                            self.assertEqual(restarted.db.execute("PRAGMA user_version").fetchone()[0], 2)
                            self.assertEqual(restarted.status()["handoffs"], [])
                        self.assertEqual(tuple(self.ledger.db.iterdump()), seed_rows)
                    finally:
                        for connection in connections:
                            if not connection.close_calls:
                                connection.close()

    def test_failed_read_only_open_preserves_existing_recovery_records(self):
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        historical = deepcopy(self.profile)
        first = self.save()
        checkpoint_args = dict(expected_sha256=first["context_sha256"],
            expected_source_revision=REVISION, expected_memory_revision=1)
        self.ledger.checkpoint_context("mission-one", expected_revision=1, **checkpoint_args)
        self.profile["memory_revision"] = 2
        self.profile["execution"]["detail"] = "Synthetic retained reconciliation checkpoint."
        current = self.ledger.save_context(self.profile, expected_revision=1)
        review = self.ledger.review_context("mission-one", reviewer_id="local-evaluator",
            expected_sha256=current["context_sha256"], expected_revision=2, include_receipt=True)
        self.stage("mission-two", target="gemini")
        neighbor = self.context("mission-two")
        self.ledger.save_context(neighbor, expected_revision=0)
        rows = tuple(self.ledger.db.iterdump())
        self.ledger.close()
        before = self.path.read_bytes()
        self.ledger = HandoffLedger(self.path, read_only=True)
        connect = sqlite3.connect

        for trigger in ("PRAGMA foreign_keys=ON", "PRAGMA user_version"):
            for error_type in (KeyboardInterrupt, SystemExit, sqlite3.OperationalError):
                with self.subTest(phase=trigger, error=error_type.__name__):
                    failure = error_type("Synthetic interrupted read-only recovery open")
                    connections, returned = [], []

                    class InterruptedConnection(sqlite3.Connection):
                        close_calls = 0

                        def execute(connection, sql, *args, **kwargs):
                            result = super().execute(sql, *args, **kwargs)
                            if sql == trigger:
                                raise failure
                            return result

                        def close(connection):
                            connection.close_calls += 1
                            return super().close()

                    def capture(*args, **kwargs):
                        self.assertTrue(kwargs["uri"])
                        self.assertTrue(args[0].endswith("?mode=ro"))
                        connection = connect(*args, **kwargs, factory=InterruptedConnection)
                        connections.append(connection)
                        return connection

                    try:
                        with patch("control_tower.handoffs.sqlite3.connect", side_effect=capture):
                            with self.assertRaises(error_type) as raised:
                                returned.append(HandoffLedger(self.path, read_only=True))
                        self.assertIs(raised.exception, failure)
                        self.assertEqual(returned, [])
                        self.assertEqual(len(connections), 1)
                        self.assertEqual(connections[0].close_calls, 1)
                        with self.assertRaises(sqlite3.ProgrammingError):
                            connections[0].execute("SELECT 1")
                        self.assertEqual(self.path.read_bytes(), before)
                        # A fresh reader, not just the pre-existing handle, must recover.
                        with HandoffLedger(self.path, read_only=True) as restarted:
                            self.assertEqual(restarted.db.execute("PRAGMA user_version").fetchone()[0], 3)
                            self.assertEqual(tuple(restarted.db.iterdump()), rows)
                            selected = restarted.load_context("mission-one", expected_source_revision=REVISION,
                                expected_memory_revision=2, expected_revision=2)
                            self.assertEqual(selected["profile"], self.profile)
                            self.assertTrue(restarted.check_context_review_receipt(
                                "mission-one", review)["local_binding_matches"])
                            self.assertEqual(restarted.load_checkpoint(
                                "mission-one", 1, **checkpoint_args)["profile"], historical)
                            self.assertEqual(restarted.load_context("mission-two",
                                expected_source_revision=REVISION, expected_memory_revision=1)["profile"], neighbor)
                            with self.assertRaisesRegex(ValueError, "unknown outcome"):
                                restarted.export_context("mission-one", expected_sha256=current["context_sha256"],
                                    expected_source_revision=REVISION, expected_memory_revision=2, expected_revision=2)
                        self.assertEqual(self.path.read_bytes(), before)
                    finally:
                        for connection in connections:
                            if not connection.close_calls:
                                connection.close()

    def test_interrupted_review_rolls_back_without_receipt_or_pending_writes(self):
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        self.stage("mission-two")
        self.ledger.save_context(self.context("mission-two"), expected_revision=0)
        before = list(self.ledger.db.iterdump())
        interruption = KeyboardInterrupt("Synthetic interrupted receipt preparation")
        returned, statements = [], []
        self.ledger.db.set_trace_callback(statements.append)
        try:
            # _now is called after the real review UPDATE, before receipt/commit.
            with patch("control_tower.handoffs._now", side_effect=interruption):
                with self.assertRaises(KeyboardInterrupt) as error:
                    returned.append(self.ledger.review_context("mission-one", reviewer_id="local-evaluator",
                        expected_sha256=saved["context_sha256"], expected_revision=1, include_receipt=True))
        finally:
            self.ledger.db.set_trace_callback(None)
        self.assertIs(error.exception, interruption)
        self.assertEqual(returned, [])
        self.assertFalse(self.ledger.db.in_transaction)
        self.assertTrue(any(s.startswith("UPDATE handoff_contexts") for s in statements))
        self.assertEqual([s for s in statements if s in ("BEGIN IMMEDIATE", "COMMIT", "ROLLBACK")],
                         ["BEGIN IMMEDIATE", "ROLLBACK"])
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        # Reusing the connection must not publish the interrupted review.
        self.ledger.db.commit()
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.assertEqual(self.load()["review_state"], "proposed")
        self.assertEqual(self.load()["profile"], self.profile)
        self.assertEqual(self.load("mission-two")["profile"], self.context("mission-two"))

    def test_interrupt_after_completed_commit_retains_review_without_receipt(self):
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        self.stage("mission-two")
        self.ledger.save_context(self.context("mission-two"), expected_revision=0)
        other = self.load("mission-two")
        connection = self.ledger.db
        interruption = KeyboardInterrupt("Synthetic lost commit acknowledgement")
        calls, returned = [], []

        class CommitThenInterrupt:
            def __getattr__(self, name):
                return getattr(connection, name)

            def commit(self):
                calls.append("commit")
                connection.commit()  # Real durable commit before the injected signal.
                raise interruption

            def rollback(self):
                calls.append("rollback")
                connection.rollback()  # Cannot undo the completed commit.

        with patch.object(self.ledger, "db", CommitThenInterrupt()):
            with self.assertRaises(KeyboardInterrupt) as error:
                returned.append(self.ledger.review_context("mission-one", reviewer_id="local-evaluator",
                    expected_sha256=saved["context_sha256"], expected_revision=1, include_receipt=True))
        self.assertIs(error.exception, interruption)
        self.assertEqual(calls, ["commit", "rollback"])
        self.assertEqual(returned, [])
        self.assertFalse(connection.in_transaction)
        committed_rows = list(connection.iterdump())
        self.ledger.close()
        before = self.path.read_bytes()
        self.ledger = HandoffLedger(self.path, read_only=True)
        self.assertEqual(list(self.ledger.db.iterdump()), committed_rows)
        self.assertEqual(self.load()["review_state"], "locally_reviewed")
        self.assertEqual(self.load()["profile"], self.profile)
        self.assertEqual(self.load("mission-two"), other)
        self.assert_exports_blocked(saved["context_sha256"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_reader_lock_blocks_review_commit_without_leaking_pending_writes(self):
        self.assertEqual(self.ledger.db.execute("PRAGMA journal_mode=DELETE").fetchone()[0], "delete")
        self.ledger.db.execute("PRAGMA busy_timeout=0")
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        self.stage("mission-two")
        self.ledger.save_context(self.context("mission-two"), expected_revision=0)
        before = list(self.ledger.db.iterdump())
        args = dict(reviewer_id="local-evaluator", expected_sha256=saved["context_sha256"],
                    expected_revision=1, include_receipt=True)
        statements, returned = [], []
        with HandoffLedger(self.path, read_only=True) as reader:
            reader.db.execute("BEGIN")
            reader.db.execute("SELECT * FROM handoff_contexts").fetchall()
            self.ledger.db.set_trace_callback(statements.append)
            try:
                with self.assertRaises(sqlite3.OperationalError) as error:
                    returned.append(self.ledger.review_context("mission-one", **args))
            finally:
                self.ledger.db.set_trace_callback(None)
            self.assertEqual(error.exception.sqlite_errorcode, sqlite3.SQLITE_BUSY)
            self.assertEqual(returned, [])
            self.assertFalse(self.ledger.db.in_transaction)
            self.assertEqual([s for s in statements if s in ("BEGIN IMMEDIATE", "COMMIT", "ROLLBACK")],
                             ["BEGIN IMMEDIATE", "COMMIT", "ROLLBACK"])
            self.assertTrue(any(s.startswith("UPDATE handoff_contexts") for s in statements))
            self.assertEqual(list(self.ledger.db.iterdump()), before)
            reader.db.rollback()
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.assertEqual(self.load()["review_state"], "proposed")
        # Explicit operator retry after lock release; no automatic retry loop.
        receipt = self.ledger.review_context("mission-one", **args)
        self.assertEqual(receipt["context_sha256"], saved["context_sha256"])
        self.assertFalse(receipt["dispatch_authorized"])
        self.assertFalse(receipt["retry_authorized"])
        self.assertEqual(self.load()["profile"], self.profile)
        self.assertEqual(self.load("mission-two")["profile"], self.context("mission-two"))
        self.assert_exports_blocked(saved["context_sha256"])

    def test_read_only_inspection_preserves_checkpoint_and_database_bytes(self):
        self.save()
        expected = self.load()
        self.ledger.close()
        before = self.path.read_bytes()
        try:
            with HandoffLedger(self.path, read_only=True) as inspected:
                self.assertEqual(inspected.load_context("mission-one", expected_source_revision=REVISION,
                    expected_memory_revision=1), expected)
                with self.assertRaises(sqlite3.OperationalError):
                    inspected.db.execute("DELETE FROM handoff_contexts")
            self.assertEqual(self.path.read_bytes(), before)
        finally:
            self.ledger = HandoffLedger(self.path)

    def test_read_only_requires_current_existing_schema_without_migrating(self):
        absent = Path(self.directory.name) / "absent" / "ledger.sqlite3"
        with self.assertRaises(sqlite3.OperationalError):
            HandoffLedger(absent, read_only=True)
        self.assertFalse(absent.parent.exists())
        self.ledger.db.execute("DROP TABLE handoff_contexts")
        self.ledger.db.execute("PRAGMA user_version=1")
        self.ledger.close()
        before = self.path.read_bytes()
        try:
            with self.assertRaisesRegex(ValueError, "read-only.*version-2"):
                HandoffLedger(self.path, read_only=True)
            self.assertEqual(self.path.read_bytes(), before)
        finally:
            self.ledger = HandoffLedger(self.path)
        self.assertEqual(self.ledger.db.execute("PRAGMA user_version").fetchone()[0], 2)

    def test_read_only_reads_committed_wal_checkpoint_and_unknown_hold(self):
        self.ledger.db.execute("PRAGMA journal_mode=WAL")
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        self.assertTrue(Path(str(self.path) + "-wal").is_file())
        with HandoffLedger(self.path, read_only=True) as inspected:
            loaded = inspected.load_context("mission-one", expected_source_revision=REVISION,
                                            expected_memory_revision=1)
            self.assertEqual(loaded["profile"], self.profile)
            snapshot = inspected.inspect_recovery("mission-one", expected_sha256=saved["context_sha256"],
                expected_source_revision=REVISION, expected_memory_revision=1)
            self.assertIn("outcome_unknown", snapshot["lineage"][0]["holds"])
            self.assertFalse(snapshot["retry_authorized"])

    def test_status_snapshot_does_not_mix_late_return_with_old_handoff_state(self):
        self.ledger.db.execute("PRAGMA journal_mode=WAL")
        self.ledger.review("mission-one", reviewer_id="local-evaluator",
                           expected_sha256=self.receipt["handoff_sha256"])
        self.ledger.export("mission-one", expected_sha256=self.receipt["handoff_sha256"])
        packet = dict(schema_version=1, kind="jarvis.return", return_id="late-return",
            handoff_id="mission-one", handoff_sha256=self.receipt["handoff_sha256"],
            source_provider="codex", text="Synthetic concurrent return.", evidence_urls=[])
        with HandoffLedger(self.path, read_only=True) as inspected:
            summarize = inspected._summary
            def commit_return(row, **kwargs):
                self.ledger.import_return(packet)
                return summarize(row, **kwargs)
            with patch.object(inspected, "_summary", side_effect=commit_return):
                snapshot = inspected.status()
            self.assertEqual(snapshot["handoffs"][0]["state"], "export_prepared")
            self.assertEqual(snapshot["return_count"], 0)
            current = inspected.status()
            self.assertEqual(current["handoffs"][0]["state"], "returned_unverified")
            self.assertEqual(current["return_count"], 1)

    def test_status_validation_failure_closes_snapshot_transaction(self):
        self.ledger.db.execute("UPDATE handoffs SET body='{}'")
        with self.assertRaises(ValueError):
            self.ledger.status()
        self.assertFalse(self.ledger.db.in_transaction)

    def test_checkpoint_index_digest_preserves_legacy_scope_and_rejects_new_history(self):
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                    expected_memory_revision=1)
        legacy = self.ledger.list_checkpoints("mission-one")
        self.assertEqual(self.ledger.list_checkpoints("mission-one", include_digest=False), legacy)
        self.assertNotIn("report_sha256", legacy)
        empty = self.ledger.list_checkpoints("mission-one", include_digest=True)
        self.assertEqual(empty["schema_version"], 2)
        self.ledger.checkpoint_context("mission-one", **args)
        with self.assertRaisesRegex(ValueError, "checkpoint index is stale"):
            self.ledger.list_checkpoints("mission-one", expected_sha256=empty["report_sha256"])
        first = self.ledger.list_checkpoints("mission-one", include_digest=True)
        self.assertEqual(first["report_sha256"], digest({k: v for k, v in first.items() if k != "report_sha256"}))
        self.ledger.checkpoint_context("mission-one", **args)
        self.stage("mission-two")
        second = self.ledger.save_context(self.context("mission-two"), expected_revision=0)
        self.ledger.checkpoint_context("mission-two", **{**args, "expected_sha256": second["context_sha256"]})
        self.assertEqual(self.ledger.list_checkpoints("mission-one", expected_sha256=first["report_sha256"]), first)
        self.profile["memory_revision"] = 2
        changed = self.ledger.save_context(self.profile, expected_revision=1)
        self.assertEqual(self.ledger.list_checkpoints("mission-one", include_digest=True), first)
        self.ledger.checkpoint_context("mission-one", **{**args, "expected_sha256": changed["context_sha256"],
                                                       "expected_memory_revision": 2})
        self.ledger.close()
        before = self.path.read_bytes()
        self.ledger = HandoffLedger(self.path, read_only=True)
        with self.assertRaisesRegex(ValueError, "checkpoint index is stale"):
            self.ledger.list_checkpoints("mission-one", expected_sha256=first["report_sha256"])
        for value in (None, 1, "true", []):
            with self.assertRaises(ValueError):
                self.ledger.list_checkpoints("mission-one", include_digest=value)
        for value in (True, "bad", "A" * 64):
            with self.assertRaises(ValueError):
                self.ledger.list_checkpoints("mission-one", expected_sha256=value)
        current = self.ledger.list_checkpoints("mission-one", include_digest=True)
        self.assertEqual(len(current["checkpoints"]), 2)
        self.assertNotIn("https://", json.dumps(current))
        self.assertFalse(current["retry_authorized"])
        self.assertEqual(self.ledger.load_context("mission-one", expected_source_revision=REVISION,
            expected_memory_revision=2)["profile"], self.profile)
        self.assertFalse(self.ledger.db.in_transaction)
        self.assertEqual(self.path.read_bytes(), before)

    def test_checkpoint_revision_guard_rejects_restored_selection_before_upgrade(self):
        self.profile = self.control_profile("paused")
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        original = deepcopy(self.profile)
        self.profile["execution"]["detail"] = "Temporary edit before checkpoint selection."
        self.ledger.save_context(self.profile, expected_revision=1)
        self.ledger.save_context(original, expected_revision=2)
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                    expected_memory_revision=1)
        before = tuple(self.ledger.db.iterdump())
        for revision in (1, 2, 4, True, 0, -1, "3"):
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                self.ledger.checkpoint_context("mission-one", **args, expected_revision=revision)
            self.assertEqual(self.ledger.db.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(tuple(self.ledger.db.iterdump()), before)
        captured = self.ledger.checkpoint_context("mission-one", **args, expected_revision=3)
        self.assertEqual(captured["checkpoint_revision"], 3)
        self.assertFalse(captured["duplicate"])
        before = tuple(self.ledger.db.iterdump())
        self.assertTrue(self.ledger.checkpoint_context("mission-one", **args)["duplicate"])
        self.assertEqual(tuple(self.ledger.db.iterdump()), before)
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        self.assertEqual(self.ledger.load_checkpoint("mission-one", 3, **args)["profile"], original)
        self.assertEqual(self.load()["review_state"], "proposed")
        self.assert_exports_blocked(saved["context_sha256"])

    def test_opt_in_checkpoint_retains_old_context_without_rewinding_current_holds(self):
        saved = self.approve()
        original = deepcopy(self.profile)
        tables = ("swarms", "handoffs", "returns", "handoff_contexts")
        rows = {t: [tuple(r) for r in self.ledger.db.execute("SELECT * FROM " + t)] for t in tables}
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION, expected_memory_revision=1)
        captured = self.ledger.checkpoint_context("mission-one", **args)
        self.assertFalse(captured["duplicate"])
        self.assertEqual(self.ledger.db.execute("PRAGMA user_version").fetchone()[0], 3)
        self.assertEqual(rows, {t: [tuple(r) for r in self.ledger.db.execute("SELECT * FROM " + t)] for t in tables})
        self.assertTrue(self.ledger.checkpoint_context("mission-one", **args)["duplicate"])
        self.profile = self.control_profile("cancelled")
        self.profile["memory_revision"] = 2
        self.profile["execution"]["state"] = "outcome_unknown"
        current = self.ledger.save_context(self.profile, expected_revision=1)
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        before = list(self.ledger.db.iterdump())
        history = self.ledger.load_checkpoint("mission-one", 1, **args)
        self.assertEqual(history["profile"], original)
        self.assertEqual(history["visibility"], "owner_private")
        self.assertFalse(history["retry_authorized"])
        history["profile"]["execution"]["detail"] = "Changed returned copy."
        self.assertEqual(self.ledger.load_checkpoint("mission-one", 1, **args)["profile"], original)
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.assertEqual(self.load(expected_memory_revision=2)["profile"], self.profile)
        self.assertEqual(self.load(expected_memory_revision=2)["review_state"], "proposed")
        self.assert_exports_blocked(current["context_sha256"])
        with self.assertRaisesRegex(ValueError, "unknown outcome"):
            self.ledger.export_context("mission-one", expected_sha256=current["context_sha256"],
                expected_source_revision=REVISION, expected_memory_revision=2)
        with self.assertRaises(ValueError):
            self.ledger.save_context(original, expected_revision=2)

    def test_overlapping_open_preserves_first_checkpoint_upgrade(self):
        saved = self.approve()
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                    expected_memory_revision=1)
        tables = ("swarms", "handoffs", "returns", "handoff_contexts")
        before = {t: [tuple(r) for r in self.ledger.db.execute("SELECT * FROM " + t)] for t in tables}
        transaction = HandoffLedger._transaction
        captures = []

        @contextmanager
        def capture_before_open_lock(opening):
            # A real second connection upgrades immediately before the opener's
            # transaction begins, after any unsafe pre-lock schema observations.
            if opening is not self.ledger:
                captures.append(self.ledger.checkpoint_context("mission-one", **args))
            with transaction(opening):
                yield

        with patch.object(HandoffLedger, "_transaction", capture_before_open_lock):
            opened = HandoffLedger(self.path)
        try:
            self.assertEqual(len(captures), 1)
            self.assertFalse(captures[0]["duplicate"])
            self.assertEqual(opened.db.execute("PRAGMA user_version").fetchone()[0], 3)
            self.assertFalse(opened.db.in_transaction)
        finally:
            opened.close()
        with HandoffLedger(self.path, read_only=True) as restarted:
            self.assertEqual(restarted.load_checkpoint("mission-one", 1, **args)["profile"], self.profile)
            self.assertEqual(before, {t: [tuple(r) for r in restarted.db.execute("SELECT * FROM " + t)] for t in tables})

    @unittest.skipIf(sys.platform == "win32", "pipe readiness barrier requires POSIX")
    def test_separate_process_open_waits_for_uncommitted_checkpoint_upgrade(self):
        import select

        self.profile = self.control_profile("paused")
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                    expected_memory_revision=1)
        tables = ("swarms", "handoffs", "returns", "handoff_contexts")
        before = {t: [tuple(r) for r in self.ledger.db.execute("SELECT * FROM " + t)] for t in tables}
        db, children = self.ledger.db, []
        owner = self
        worker = '''
import json, sqlite3, sys
from control_tower.handoffs import HandoffLedger
connect = sqlite3.connect
announced = False
def trace(sql):
    global announced
    if sql == "BEGIN IMMEDIATE" and not announced:
        announced = True
        print("lock-request", flush=True)
def instrumented_connect(*args, **kwargs):
    connection = connect(*args, **kwargs)
    connection.set_trace_callback(trace)
    return connection
sqlite3.connect = instrumented_connect
with HandoffLedger(sys.argv[1]) as ledger:
    history = ledger.load_checkpoint("mission-one", 1, **json.loads(sys.argv[2]))
    print(json.dumps({"version": ledger.db.execute("PRAGMA user_version").fetchone()[0],
        "profile": history["profile"], "retry_authorized": history["retry_authorized"]}))
'''

        class CommitBarrier:
            def __getattr__(self, name):
                return getattr(db, name)

            def commit(self):
                # Capture's real transaction has changed schema to 3 but has
                # not committed. The separate opener must wait on SQLite.
                child = subprocess.Popen([sys.executable, "-u", "-c", worker,
                    str(owner.path), json.dumps(args)], cwd=Path(__file__).resolve().parents[1],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                children.append(child)
                ready, _, _ = select.select([child.stdout], [], [], 5)
                owner.assertTrue(ready, "opener did not reach its bounded lock barrier")
                owner.assertEqual(child.stdout.readline().strip(), "lock-request")
                owner.assertIsNone(child.poll())
                return db.commit()

        try:
            with patch.object(self.ledger, "db", CommitBarrier()):
                captured = self.ledger.checkpoint_context("mission-one", **args)
            self.assertFalse(captured["duplicate"])
            output, errors = children[0].communicate(timeout=10)
            self.assertEqual(children[0].returncode, 0, errors)
            observed = json.loads(output)
            self.assertEqual(observed, dict(version=3, profile=self.profile, retry_authorized=False))
            with HandoffLedger(self.path, read_only=True) as restarted:
                self.assertEqual(restarted.load_checkpoint("mission-one", 1, **args)["profile"], self.profile)
                self.assertEqual(before, {t: [tuple(r) for r in restarted.db.execute("SELECT * FROM " + t)] for t in tables})
                self.assertEqual(restarted.load_context("mission-one", expected_source_revision=REVISION,
                    expected_memory_revision=1)["profile"], self.profile)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=5)

    def test_read_only_open_uses_one_schema_snapshot_during_upgrade(self):
        self.ledger.db.execute("PRAGMA journal_mode=WAL")
        saved = self.save()
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                    expected_memory_revision=1)
        writer = self.ledger
        captures = []

        class UpgradeBetweenSchemaReads(sqlite3.Connection):
            def execute(connection, sql, *parameters):
                if sql.startswith("SELECT name FROM sqlite_master"):
                    captures.append(writer.checkpoint_context("mission-one", **args))
                return super().execute(sql, *parameters)

        connect = sqlite3.connect
        def instrumented_connect(*args, **kwargs):
            return connect(*args, factory=UpgradeBetweenSchemaReads, **kwargs)

        with patch("control_tower.handoffs.sqlite3.connect", instrumented_connect):
            opened = HandoffLedger(self.path, read_only=True)
        try:
            self.assertEqual(len(captures), 1)
            self.assertFalse(captures[0]["duplicate"])
            self.assertFalse(opened.db.in_transaction)
            self.assertEqual(opened.db.execute("PRAGMA user_version").fetchone()[0], 3)
            self.assertEqual(opened.load_checkpoint("mission-one", 1, **args)["profile"], self.profile)
        finally:
            opened.close()

    def test_checkpoint_index_is_selective_validated_and_retained_after_restart(self):
        self.assertEqual(self.ledger.list_checkpoints("mission-one")["checkpoints"], [])
        saved = self.save()
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION, expected_memory_revision=1)
        self.ledger.checkpoint_context("mission-one", **args)
        self.stage("separate-task")
        other = self.context("separate-task")
        second = self.ledger.save_context(other, expected_revision=0)
        self.ledger.checkpoint_context("separate-task", **{**args, "expected_sha256": second["context_sha256"]})
        self.profile["memory_revision"] = 2
        current = self.ledger.save_context(self.profile, expected_revision=1)
        self.ledger.checkpoint_context("mission-one", **{**args, "expected_sha256": current["context_sha256"], "expected_memory_revision": 2})
        first = self.ledger.list_checkpoints("mission-one")
        self.assertEqual([r["checkpoint_revision"] for r in first["checkpoints"]], [1, 2])
        self.assertEqual([r["memory_revision"] for r in first["checkpoints"]], [1, 2])
        self.assertEqual(first["checkpoints"][0]["context_sha256"], saved["context_sha256"])
        self.assertNotIn("separate-task", json.dumps(first))
        self.assertNotIn("https://", json.dumps(first))
        self.assertNotIn("detail", json.dumps(first))
        self.assertFalse(first["retry_authorized"])
        self.assertEqual(first["visibility"], "owner_private")
        with HandoffLedger(self.path, read_only=True) as restarted:
            self.assertEqual(restarted.list_checkpoints("mission-one"), first)
            first["checkpoints"].clear()
            self.assertEqual(len(restarted.list_checkpoints("mission-one")["checkpoints"]), 2)
            with self.assertRaises(ValueError):
                restarted.list_checkpoints("unknown-task")
        self.ledger.db.execute("UPDATE context_checkpoints SET digest=? WHERE handoff_id=? AND revision=1", ("0" * 64, "mission-one"))
        with self.assertRaises(ValueError):
            self.ledger.list_checkpoints("mission-one")
        self.assertFalse(self.ledger.db.in_transaction)

    def assert_damaged_hold_history_rejects(self, damaged, current, suffix):
        from scripts.jarvis_network import _backup
        self.ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=?",
            (json.dumps(damaged), digest(damaged), "mission-one"))
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        before = self.path.read_bytes()
        output = self.path.parent / (suffix + "-backup.sqlite3")
        operations = {
            "index": lambda: self.ledger.list_checkpoints("mission-one"),
            "load": lambda: self.ledger.load_checkpoint("mission-one", 1,
                expected_sha256=digest(damaged), expected_source_revision=REVISION,
                expected_memory_revision=1),
            "backup": lambda: _backup(self.ledger.db, output),
        }
        for name, operation in operations.items():
            with self.subTest(case=suffix, operation=name), self.assertRaisesRegex(ValueError, "checkpoint integrity"):
                operation()
        with self.subTest(case=suffix, operation="no-published-backup"):
            self.assertFalse(output.exists())
        self.assertFalse(list(output.parent.glob(".jarvis-backup-*")))
        self.assertEqual(self.load(expected_memory_revision=2)["profile"], current)
        self.assertEqual(self.load("independent-task")["profile"], self.context("independent-task"))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.ledger.db.in_transaction)
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)

    def hold_history_fixture(self, unknown=False):
        self.profile = self.control_profile("paused")
        saved = self.save()
        self.ledger.checkpoint_context("mission-one", expected_sha256=saved["context_sha256"],
            expected_source_revision=REVISION, expected_memory_revision=1)
        current = deepcopy(self.profile)
        current["memory_revision"] = 2
        current["control"]["state"] = "active"
        if unknown:
            current["execution"]["state"] = "outcome_unknown"
        self.ledger.save_context(current, expected_revision=1)
        self.stage("independent-task")
        self.ledger.save_context(self.context("independent-task"), expected_revision=0)
        return current

    def test_historical_terminal_holds_cannot_disappear_after_restart(self):
        current = self.hold_history_fixture()
        cancelled = deepcopy(self.profile)
        cancelled["control"]["state"] = "cancelled"
        self.assert_damaged_hold_history_rejects(cancelled, current, "cancelled")
        unknown = deepcopy(self.profile)
        unknown["execution"]["state"] = "outcome_unknown"
        self.assert_damaged_hold_history_rejects(unknown, current, "unknown")

    def test_historical_unknown_execution_binding_cannot_change_after_restart(self):
        current = self.hold_history_fixture(unknown=True)
        for field, value in (("attempts", 0), ("context_id", "different-context")):
            damaged = deepcopy(self.profile)
            damaged["execution"].update(state="outcome_unknown", **{field: value})
            self.assert_damaged_hold_history_rejects(damaged, current, field)

    def test_paused_history_can_precede_active_unknown_hold_without_releasing_it(self):
        current = self.hold_history_fixture(unknown=True)
        with HandoffLedger(self.path, read_only=True) as restarted:
            before = self.path.read_bytes()
            history = restarted.load_checkpoint("mission-one", 1, expected_sha256=digest(self.profile),
                expected_source_revision=REVISION, expected_memory_revision=1)
            self.assertEqual(history["profile"], self.profile)
            self.assertFalse(history["retry_authorized"])
            self.assertEqual(len(restarted.list_checkpoints("mission-one")["checkpoints"]), 1)
            self.assertEqual(restarted.load_context("mission-one", expected_source_revision=REVISION,
                expected_memory_revision=2)["profile"], current)
            self.assertEqual(self.path.read_bytes(), before)

    def test_new_capture_rejects_invalid_adjacent_history_without_persisting(self):
        self.profile = self.control_profile("paused")
        first = self.save()
        args = dict(expected_source_revision=REVISION, expected_memory_revision=1)
        self.ledger.checkpoint_context("mission-one", expected_sha256=first["context_sha256"], **args)
        current = deepcopy(self.profile)
        current["memory_revision"] = 2
        saved = self.ledger.save_context(current, expected_revision=1)
        self.stage("independent-task")
        independent = self.context("independent-task")
        self.ledger.save_context(independent, expected_revision=0)
        tables = ("swarms", "handoffs", "returns", "handoff_contexts", "context_checkpoints")
        for case in ("memory-order", "attempt-order", "digest"):
            self.ledger.db.execute("DELETE FROM context_checkpoints WHERE revision=2")
            damaged = deepcopy(self.profile)
            if case == "memory-order":
                damaged["memory_revision"] = 3
            elif case == "attempt-order":
                damaged["execution"]["attempts"] = 2
            checksum = "0" * 64 if case == "digest" else digest(damaged)
            self.ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=?",
                (json.dumps(damaged), checksum, "mission-one"))
            self.ledger.close()
            self.ledger = HandoffLedger(self.path)
            before = {t: [tuple(r) for r in self.ledger.db.execute("SELECT * FROM " + t)] for t in tables}
            with self.subTest(case=case, check="capture"), self.assertRaisesRegex(ValueError, "checkpoint integrity"):
                self.ledger.checkpoint_context("mission-one", expected_sha256=saved["context_sha256"],
                    expected_source_revision=REVISION, expected_memory_revision=2)
            with self.subTest(case=case, check="rollback"):
                self.assertEqual(before, {t: [tuple(r) for r in self.ledger.db.execute("SELECT * FROM " + t)] for t in tables})
            self.assertFalse(self.ledger.db.in_transaction)
            self.assertEqual(self.load(expected_memory_revision=2)["profile"], current)
            self.assertEqual(self.load("independent-task")["profile"], independent)
        # Restoring the original valid history permits one new capture, then a
        # duplicate receipt; a restart retains both without changing current state.
        self.ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=? AND revision=1",
            (json.dumps(self.profile), first["context_sha256"], "mission-one"))
        args.update(expected_sha256=saved["context_sha256"], expected_memory_revision=2)
        self.assertFalse(self.ledger.checkpoint_context("mission-one", **args)["duplicate"])
        self.assertTrue(self.ledger.checkpoint_context("mission-one", **args)["duplicate"])
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        self.assertEqual(len(self.ledger.list_checkpoints("mission-one")["checkpoints"]), 2)
        self.assertEqual(self.load(expected_memory_revision=2)["profile"], current)
        self.assertEqual(self.load("independent-task")["profile"], independent)

    def test_retained_transition_cannot_temporarily_clear_irreversible_history(self):
        from scripts.jarvis_network import _backup
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["attempts"] = 2
        first = self.save()
        args = dict(expected_source_revision=REVISION, expected_memory_revision=1)
        self.ledger.checkpoint_context("mission-one", expected_sha256=first["context_sha256"], **args)
        later = deepcopy(self.profile)
        later["memory_revision"] = 2
        saved = self.ledger.save_context(later, expected_revision=1)
        self.ledger.checkpoint_context("mission-one", expected_sha256=saved["context_sha256"],
            **{**args, "expected_memory_revision": 2})
        current = deepcopy(later)
        current["memory_revision"] = 3
        current["control"]["state"] = "cancelled"
        current["execution"]["state"] = "outcome_unknown"
        self.ledger.save_context(current, expected_revision=2)
        self.stage("independent-task")
        independent = self.context("independent-task")
        self.ledger.save_context(independent, expected_revision=0)
        for case in ("attempts", "schema-3-to-2", "schema-2-to-1", "cancelled", "unknown"):
            older, newer = deepcopy(self.profile), deepcopy(later)
            if case == "attempts":
                newer["execution"]["attempts"] = 1
            elif case == "schema-3-to-2":
                newer["schema_version"] = 2
                del newer["destination_id"]
            elif case == "schema-2-to-1":
                older["schema_version"], newer["schema_version"] = 2, 1
                del older["destination_id"], newer["destination_id"], newer["control"]
            elif case == "cancelled":
                older["control"]["state"] = "cancelled"
                newer["control"]["state"] = "active"
            else:
                older["execution"]["state"] = "outcome_unknown"
            for revision, profile in ((1, older), (2, newer)):
                self.ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=? AND revision=?",
                    (json.dumps(profile), digest(profile), "mission-one", revision))
            self.ledger.close()
            self.ledger = HandoffLedger(self.path, read_only=True)
            before = self.path.read_bytes()
            output = self.path.parent / (case + "-backup.sqlite3")
            operations = {"index": lambda: self.ledger.list_checkpoints("mission-one"),
                "older-load": lambda: self.ledger.load_checkpoint("mission-one", 1,
                    expected_sha256=digest(older), **args),
                "newer-load": lambda: self.ledger.load_checkpoint("mission-one", 2,
                    expected_sha256=digest(newer), **{**args, "expected_memory_revision": 2}),
                "backup": lambda: _backup(self.ledger.db, output)}
            for name, operation in operations.items():
                with self.subTest(case=case, operation=name), self.assertRaisesRegex(ValueError, "checkpoint integrity"):
                    operation()
            with self.subTest(case=case, operation="no-published-backup"):
                self.assertFalse(output.exists())
            self.assertFalse(list(output.parent.glob(".jarvis-backup-*")))
            self.assertEqual(self.load(expected_memory_revision=3)["profile"], current)
            self.assertEqual(self.load("independent-task")["profile"], independent)
            self.assertEqual(self.path.read_bytes(), before)
            self.assertFalse(self.ledger.db.in_transaction)
            self.ledger.close()
            self.ledger = HandoffLedger(self.path)

    def test_retained_transition_accepts_legacy_upgrades_and_terminal_hold(self):
        from scripts.jarvis_network import _backup
        original = deepcopy(self.profile)
        original["execution"]["attempts"] = 0
        profiles = [original]
        controlled = {**deepcopy(original), "schema_version": 2, "memory_revision": 2,
            "control": dict(state="paused", actor_id="local-owner", reason="Synthetic legacy upgrade.")}
        controlled["execution"]["attempts"] = 1
        profiles.append(controlled)
        bound = {**deepcopy(controlled), "schema_version": 3, "memory_revision": 3,
            "destination_id": "repository-one"}
        bound["control"]["state"] = "active"
        bound["execution"]["attempts"] = 2
        profiles.append(bound)
        for revision, profile in enumerate(profiles, 1):
            saved = self.ledger.save_context(profile, expected_revision=revision - 1)
            self.ledger.checkpoint_context("mission-one", expected_sha256=saved["context_sha256"],
                expected_source_revision=REVISION, expected_memory_revision=revision)
        current = deepcopy(bound)
        current["memory_revision"] = 4
        current["control"]["state"] = "cancelled"
        current["execution"]["state"] = "outcome_unknown"
        self.ledger.save_context(current, expected_revision=3)
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        before = self.path.read_bytes()
        output = self.path.parent / "valid-transition-backup.sqlite3"
        _backup(self.ledger.db, output)
        with HandoffLedger(output, read_only=True) as restored:
            for ledger in (self.ledger, restored):
                self.assertEqual(len(ledger.list_checkpoints("mission-one")["checkpoints"]), 3)
                for revision, profile in enumerate(profiles, 1):
                    loaded = ledger.load_checkpoint("mission-one", revision, expected_sha256=digest(profile),
                        expected_source_revision=REVISION, expected_memory_revision=revision)
                    self.assertEqual(loaded["profile"], profile)
                    self.assertFalse(loaded["retry_authorized"])
                self.assertEqual(ledger.load_context("mission-one", expected_source_revision=REVISION,
                    expected_memory_revision=4)["profile"], current)
        self.assertEqual(self.path.read_bytes(), before)

    def test_retained_memory_revisions_cannot_regress_between_checkpoints(self):
        from scripts.jarvis_network import _backup
        self.profile = self.control_profile("paused")
        first = self.save()
        args = dict(expected_source_revision=REVISION, expected_memory_revision=1)
        self.ledger.checkpoint_context("mission-one", expected_sha256=first["context_sha256"], **args)
        later = deepcopy(self.profile)
        later["memory_revision"] = 2
        second = self.ledger.save_context(later, expected_revision=1)
        self.ledger.checkpoint_context("mission-one", expected_sha256=second["context_sha256"],
            **{**args, "expected_memory_revision": 2})
        current = deepcopy(later)
        current["memory_revision"] = 3
        current["execution"]["state"] = "outcome_unknown"
        self.ledger.save_context(current, expected_revision=2)
        self.stage("independent-task")
        self.ledger.save_context(self.context("independent-task"), expected_revision=0)
        damaged = {**self.profile, "memory_revision": 3}
        self.ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=? AND revision=1",
            (json.dumps(damaged), digest(damaged), "mission-one"))
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        before = self.path.read_bytes()
        output = self.path.parent / "out-of-order-backup.sqlite3"
        operations = {
            "index": lambda: self.ledger.list_checkpoints("mission-one"),
            "older-load": lambda: self.ledger.load_checkpoint("mission-one", 1,
                expected_sha256=digest(damaged), expected_source_revision=REVISION, expected_memory_revision=3),
            "newer-load": lambda: self.ledger.load_checkpoint("mission-one", 2,
                expected_sha256=second["context_sha256"], expected_source_revision=REVISION, expected_memory_revision=2),
            "backup": lambda: _backup(self.ledger.db, output),
        }
        for name, operation in operations.items():
            with self.subTest(operation=name), self.assertRaisesRegex(ValueError, "checkpoint integrity"):
                operation()
        self.assertFalse(output.exists())
        self.assertFalse(list(output.parent.glob(".jarvis-backup-*")))
        self.assertEqual(self.load(expected_memory_revision=3)["profile"], current)
        self.assertEqual(self.load("independent-task")["profile"], self.context("independent-task"))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.ledger.db.in_transaction)

    def test_equal_retained_memory_revisions_remain_valid_after_restart(self):
        from scripts.jarvis_network import _backup
        self.profile = self.control_profile("paused")
        saved = self.save()
        args = dict(expected_source_revision=REVISION, expected_memory_revision=1)
        self.ledger.checkpoint_context("mission-one", expected_sha256=saved["context_sha256"], **args)
        edited = deepcopy(self.profile)
        edited["execution"]["detail"] = "Synthetic detail edit with unchanged memory revision."
        second = self.ledger.save_context(edited, expected_revision=1)
        self.ledger.checkpoint_context("mission-one", expected_sha256=second["context_sha256"], **args)
        current = deepcopy(edited)
        current["memory_revision"] = 2
        current["execution"]["state"] = "outcome_unknown"
        self.ledger.save_context(current, expected_revision=2)
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        before = self.path.read_bytes()
        self.assertEqual(len(self.ledger.list_checkpoints("mission-one")["checkpoints"]), 2)
        for revision, checksum, profile in ((1, saved["context_sha256"], self.profile),
                                            (2, second["context_sha256"], edited)):
            loaded = self.ledger.load_checkpoint("mission-one", revision, expected_sha256=checksum, **args)
            self.assertEqual(loaded["profile"], profile)
            self.assertFalse(loaded["retry_authorized"])
        self.assertEqual(self.load(expected_memory_revision=2)["profile"], current)
        self.assertEqual(self.path.read_bytes(), before)
        backup = self.path.parent / "equal-memory-backup.sqlite3"
        _backup(self.ledger.db, backup)
        with HandoffLedger(backup, read_only=True) as restored:
            self.assertEqual(len(restored.list_checkpoints("mission-one")["checkpoints"]), 2)
            self.assertEqual(restored.load_context("mission-one", expected_source_revision=REVISION,
                expected_memory_revision=2)["profile"], current)
        self.assertEqual(self.path.read_bytes(), before)

    def test_historical_control_schema_cannot_exceed_current_after_restart(self):
        from scripts.jarvis_network import _backup
        saved = self.save()
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                    expected_memory_revision=1)
        self.ledger.checkpoint_context("mission-one", **args)
        current = deepcopy(self.profile)
        current["memory_revision"] = 2
        self.ledger.save_context(current, expected_revision=1)
        self.stage("independent-task")
        independent = self.context("independent-task")
        self.ledger.save_context(independent, expected_revision=0)
        for state in ("paused", "cancelled"):
            damaged = self.control_profile(state)
            self.ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=?",
                (json.dumps(damaged), digest(damaged), "mission-one"))
            self.ledger.close()
            self.ledger = HandoffLedger(self.path, read_only=True)
            before = self.path.read_bytes()
            output = self.path.parent / (state + "-backup.sqlite3")
            operations = {
                "index": lambda: self.ledger.list_checkpoints("mission-one"),
                "load": lambda: self.ledger.load_checkpoint("mission-one", 1,
                    **{**args, "expected_sha256": digest(damaged)}),
                "backup": lambda: _backup(self.ledger.db, output),
            }
            for name, operation in operations.items():
                with self.subTest(state=state, operation=name), self.assertRaisesRegex(ValueError, "checkpoint integrity"):
                    operation()
            self.assertFalse(output.exists())
            self.assertFalse(list(output.parent.glob(".jarvis-backup-*")))
            self.assertEqual(self.load(expected_memory_revision=2)["profile"], current)
            self.assertEqual(self.load("independent-task")["profile"], independent)
            self.assertEqual(self.path.read_bytes(), before)
            self.assertFalse(self.ledger.db.in_transaction)
            self.ledger.close()
            self.ledger = HandoffLedger(self.path)

    def test_legacy_checkpoint_survives_control_upgrade_with_unknown_cancelled_hold(self):
        saved = self.save()
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                    expected_memory_revision=1)
        self.ledger.checkpoint_context("mission-one", **args)
        current = self.control_profile("cancelled")
        current["memory_revision"] = 2
        current["execution"]["state"] = "outcome_unknown"
        self.ledger.save_context(current, expected_revision=1)
        with HandoffLedger(self.path, read_only=True) as restarted:
            before = self.path.read_bytes()
            history = restarted.load_checkpoint("mission-one", 1, **args)
            self.assertEqual(history["profile"], self.profile)
            self.assertFalse(history["retry_authorized"])
            self.assertEqual(len(restarted.list_checkpoints("mission-one")["checkpoints"]), 1)
            self.assertEqual(restarted.load_context("mission-one", expected_source_revision=REVISION,
                expected_memory_revision=2)["profile"], current)
            self.assertEqual(self.path.read_bytes(), before)

    def test_historical_attempt_count_cannot_exceed_current_after_restart(self):
        saved = self.save()
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                    expected_memory_revision=1)
        self.ledger.checkpoint_context("mission-one", **args)
        current = self.control_profile("paused")
        current["memory_revision"] = 2
        current["execution"]["state"] = "outcome_unknown"
        self.ledger.save_context(current, expected_revision=1)
        damaged = deepcopy(self.profile)
        damaged["execution"]["attempts"] = 2
        self.ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=?",
            (json.dumps(damaged), digest(damaged), "mission-one"))
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        before = self.path.read_bytes()
        for operation in (lambda: self.ledger.list_checkpoints("mission-one"),
                lambda: self.ledger.load_checkpoint("mission-one", 1,
                    **{**args, "expected_sha256": digest(damaged)})):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                operation()
        self.assertEqual(self.load(expected_memory_revision=2)["profile"], current)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.ledger.db.in_transaction)

    def test_lower_historical_attempt_count_survives_later_unknown_hold(self):
        saved = self.save()
        original = deepcopy(self.profile)
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                    expected_memory_revision=1)
        self.ledger.checkpoint_context("mission-one", **args)
        current = self.control_profile("paused")
        current["memory_revision"] = 2
        current["execution"].update(state="outcome_unknown", attempts=2)
        self.ledger.save_context(current, expected_revision=1)
        with HandoffLedger(self.path, read_only=True) as restarted:
            before = self.path.read_bytes()
            history = restarted.load_checkpoint("mission-one", 1, **args)
            self.assertEqual(history["profile"], original)
            self.assertFalse(history["retry_authorized"])
            self.assertEqual(len(restarted.list_checkpoints("mission-one")["checkpoints"]), 1)
            retained = restarted.load_context("mission-one", expected_source_revision=REVISION,
                expected_memory_revision=2)["profile"]
            self.assertEqual(retained, current)
            self.assertEqual(self.path.read_bytes(), before)

    def test_historical_checkpoint_cannot_change_immutable_mission_after_restart(self):
        saved = self.save()
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                    expected_memory_revision=1)
        self.ledger.checkpoint_context("mission-one", **args)
        current = deepcopy(self.profile)
        current["memory_revision"] = 2
        current["execution"]["detail"] = "Later blocked checkpoint; retain hold."
        self.ledger.save_context(current, expected_revision=1)
        # Simulate damaged retained history with a self-consistent new digest.
        damaged = {**self.profile, "mission_id": "different-mission"}
        self.ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=?",
            (json.dumps(damaged), digest(damaged), "mission-one"))
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        before = self.path.read_bytes()
        for operation in (lambda: self.ledger.list_checkpoints("mission-one"),
                lambda: self.ledger.load_checkpoint("mission-one", 1,
                    **{**args, "expected_sha256": digest(damaged)})):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                operation()
        self.assertEqual(self.load(expected_memory_revision=2)["profile"], current)
        self.assertEqual(self.path.read_bytes(), before)

    def test_neighbor_checkpoint_current_bounds_reject_after_restart(self):
        self.stage("independent-task")
        independent = self.context("independent-task")
        self.ledger.save_context(independent, expected_revision=0)
        for case in ("memory", "attempts", "cancelled", "unknown-context", "schema"):
            identifier = "mission-one"
            if self.ledger.db.execute("PRAGMA user_version").fetchone()[0] == 3:
                self.ledger.db.execute("DELETE FROM context_checkpoints WHERE handoff_id=?", (identifier,))
            self.ledger.db.execute("DELETE FROM handoff_contexts WHERE handoff_id=?", (identifier,))
            original = self.context(identifier)
            if case != "schema":
                original.update(schema_version=3, destination_id="repository-one",
                    control=dict(state="active", actor_id="local-owner", reason="Synthetic scope."))
            saved = self.ledger.save_context(original, expected_revision=0)
            args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                        expected_memory_revision=1)
            self.ledger.checkpoint_context(identifier, **args)
            middle = deepcopy(original)
            middle["memory_revision"] = 2
            self.ledger.save_context(middle, expected_revision=1)
            current = deepcopy(middle)
            current["memory_revision"] = 3
            if case != "schema":
                current["control"]["state"] = "paused"
                current["execution"]["state"] = "outcome_unknown"
            self.ledger.save_context(current, expected_revision=2)
            damaged = deepcopy(middle)
            if case == "memory":
                damaged["memory_revision"] = 4
            elif case == "attempts":
                damaged["execution"]["attempts"] = 2
            elif case == "cancelled":
                damaged["control"]["state"] = "cancelled"
            elif case == "unknown-context":
                damaged["execution"].update(state="outcome_unknown", context_id="other-synthetic-context")
            else:
                damaged.update(schema_version=2,
                    control=dict(state="active", actor_id="local-owner", reason="Synthetic upgrade."))
            self.ledger.db.execute("INSERT INTO context_checkpoints VALUES (?,?,?,?)",
                (identifier, 2, digest(damaged), json.dumps(damaged)))
            self.ledger.close()
            self.ledger = HandoffLedger(self.path, read_only=True)
            before = self.path.read_bytes()
            with self.subTest(case=case), self.assertRaisesRegex(ValueError, "checkpoint integrity"):
                self.ledger.load_checkpoint(identifier, 1, **args)
            self.assertEqual(self.path.read_bytes(), before)
            self.assertFalse(self.ledger.db.in_transaction)
            self.assertEqual(self.load(identifier, expected_memory_revision=3)["profile"], current)
            self.assertEqual(self.load("independent-task")["profile"], independent)
            self.ledger.close()
            self.ledger = HandoffLedger(self.path)
            # A valid, lower/equal-count historical neighbor remains readable.
            self.ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=? AND revision=2",
                (json.dumps(middle), digest(middle), identifier))
            with HandoffLedger(self.path, read_only=True) as restarted:
                self.assertEqual(restarted.load_checkpoint(identifier, 1, **args)["profile"], original)
                self.assertEqual(len(restarted.list_checkpoints(identifier)["checkpoints"]), 2)

    def test_neighbor_checkpoint_revision_bounds_reject_after_restart_without_mutation(self):
        self.profile = self.destination_profile()
        first = self.save()
        args = dict(expected_sha256=first["context_sha256"], expected_source_revision=REVISION,
                    expected_memory_revision=1)
        self.ledger.checkpoint_context("mission-one", **args)
        current = deepcopy(self.profile)
        current["memory_revision"] = 2
        current["control"]["state"] = "paused"
        current["execution"]["state"] = "outcome_unknown"
        saved = self.ledger.save_context(current, expected_revision=1)
        self.stage("independent-task")
        independent = self.context("independent-task")
        self.ledger.save_context(independent, expected_revision=0)
        tables = ("swarms", "handoffs", "returns", "handoff_contexts", "context_checkpoints")
        for case in ("future-revision", "current-revision-different-body"):
            self.ledger.db.execute("DELETE FROM context_checkpoints WHERE handoff_id=? AND revision>1",
                                   ("mission-one",))
            adjacent = deepcopy(current)
            revision = 3 if case == "future-revision" else 2
            if revision == 2:
                adjacent["execution"]["detail"] = "Different synthetic current checkpoint body."
            self.ledger.db.execute("INSERT INTO context_checkpoints VALUES (?,?,?,?)",
                ("mission-one", revision, digest(adjacent), json.dumps(adjacent)))
            self.ledger.close()
            self.ledger = HandoffLedger(self.path, read_only=True)
            before_bytes = self.path.read_bytes()
            with self.subTest(case=case, check="selective-read"), self.assertRaisesRegex(ValueError, "checkpoint integrity"):
                self.ledger.load_checkpoint("mission-one", 1, **args)
            self.assertEqual(self.path.read_bytes(), before_bytes)
            self.assertFalse(self.ledger.db.in_transaction)
            self.ledger.close()
            self.ledger = HandoffLedger(self.path)
            before = {t: [tuple(r) for r in self.ledger.db.execute("SELECT * FROM " + t)] for t in tables}
            if case == "future-revision":
                with self.subTest(case=case, check="capture"), self.assertRaisesRegex(ValueError, "checkpoint integrity"):
                    self.ledger.checkpoint_context("mission-one", expected_sha256=saved["context_sha256"],
                        expected_source_revision=REVISION, expected_memory_revision=2)
                with self.subTest(case=case, check="rollback"):
                    self.assertEqual(before, {t: [tuple(r) for r in self.ledger.db.execute("SELECT * FROM " + t)] for t in tables})
            self.assertFalse(self.ledger.db.in_transaction)
            self.assertEqual(self.load(expected_memory_revision=2)["profile"], current)
            self.assertEqual(self.load("independent-task")["profile"], independent)
        # Restoring a valid neighbor restores selective reads and duplicate capture.
        self.ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=? AND revision=2",
            (json.dumps(current), digest(current), "mission-one"))
        with HandoffLedger(self.path, read_only=True) as restarted:
            self.assertEqual(restarted.load_checkpoint("mission-one", 1, **args)["profile"], self.profile)
            self.assertEqual(len(restarted.list_checkpoints("mission-one")["checkpoints"]), 2)
        self.assertTrue(self.ledger.checkpoint_context("mission-one", expected_sha256=saved["context_sha256"],
            expected_source_revision=REVISION, expected_memory_revision=2)["duplicate"])

    def test_adjacent_checkpoint_identity_drift_blocks_selective_load_and_capture(self):
        self.profile = self.destination_profile()
        first = self.save()
        self.ledger.checkpoint_context("mission-one", expected_sha256=first["context_sha256"],
            expected_source_revision=REVISION, expected_memory_revision=1)
        newer = deepcopy(self.profile)
        newer["memory_revision"] = 2
        second = self.ledger.save_context(newer, expected_revision=1)
        self.ledger.checkpoint_context("mission-one", expected_sha256=second["context_sha256"],
            expected_source_revision=REVISION, expected_memory_revision=2)
        current = deepcopy(newer)
        current["memory_revision"] = 3
        saved = self.ledger.save_context(current, expected_revision=2)
        self.stage("independent-task")
        independent = self.context("independent-task")
        self.ledger.save_context(independent, expected_revision=0)
        tables = ("swarms", "handoffs", "returns", "handoff_contexts", "context_checkpoints")
        for field in ("mission_id", "destination_id"):
            for damaged_revision in (1, 2):
                self.ledger.db.execute("DELETE FROM context_checkpoints WHERE revision=3")
                for revision, profile in ((1, self.profile), (2, newer)):
                    body = deepcopy(profile)
                    if revision == damaged_revision:
                        body[field] = "different-identity"
                    self.ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=? AND revision=?",
                        (json.dumps(body), digest(body), "mission-one", revision))
                self.ledger.close()
                self.ledger = HandoffLedger(self.path)
                before = {t: [tuple(r) for r in self.ledger.db.execute("SELECT * FROM " + t)] for t in tables}
                selected_revision = 3 - damaged_revision
                selected = self.profile if selected_revision == 1 else newer
                with self.subTest(field=field, neighbor=damaged_revision, check="selective-load"), self.assertRaisesRegex(ValueError, "checkpoint integrity"):
                    self.ledger.load_checkpoint("mission-one", selected_revision, expected_sha256=digest(selected),
                        expected_source_revision=REVISION, expected_memory_revision=selected_revision)
                # New capture sees revision 2 as its nearest retained neighbor.
                if damaged_revision == 2:
                    with self.subTest(field=field, check="new-capture"), self.assertRaisesRegex(ValueError, "checkpoint integrity"):
                        self.ledger.checkpoint_context("mission-one", expected_sha256=saved["context_sha256"],
                            expected_source_revision=REVISION, expected_memory_revision=3)
                with self.subTest(field=field, neighbor=damaged_revision, check="unchanged"):
                    self.assertEqual(before, {t: [tuple(r) for r in self.ledger.db.execute("SELECT * FROM " + t)] for t in tables})
                self.assertFalse(self.ledger.db.in_transaction)
                self.assertEqual(self.load(expected_memory_revision=3)["profile"], current)
                self.assertEqual(self.load("independent-task")["profile"], independent)

    def test_historical_bound_destination_drift_rejects_after_restart(self):
        self.profile = self.destination_profile()
        saved = self.save()
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                    expected_memory_revision=1)
        self.ledger.checkpoint_context("mission-one", **args)
        current = deepcopy(self.profile)
        current["memory_revision"] = 2
        current["control"]["state"] = "paused"
        self.ledger.save_context(current, expected_revision=1)
        damaged = {**self.profile, "destination_id": "different-destination"}
        self.ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=?",
            (json.dumps(damaged), digest(damaged), "mission-one"))
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        before = self.path.read_bytes()
        for operation in (lambda: self.ledger.list_checkpoints("mission-one"),
                lambda: self.ledger.load_checkpoint("mission-one", 1,
                    **{**args, "expected_sha256": digest(damaged)})):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                operation()
        self.assertEqual(self.load(expected_memory_revision=2)["profile"], current)
        self.assertEqual(self.path.read_bytes(), before)

    def test_pre_destination_history_survives_binding_and_later_hold(self):
        for version in (1, 2):
            identifier = "mission-one" if version == 1 else "legacy-history-2"
            if version == 2:
                self.stage(identifier)
            old = self.context(identifier)
            if version == 2:
                old.update(schema_version=2, control=dict(state="active", actor_id="local-owner",
                    reason="Synthetic pre-binding history."))
            saved = self.ledger.save_context(old, expected_revision=0)
            args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                        expected_memory_revision=1)
            self.ledger.checkpoint_context(identifier, **args)
            bound = {**old, "schema_version": 3, "memory_revision": 2,
                "destination_id": "destination-" + str(version),
                "control": dict(state="active", actor_id="local-owner", reason="Synthetic binding.")}
            saved_bound = self.ledger.save_context(bound, expected_revision=1)
            bound_args = {**args, "expected_sha256": saved_bound["context_sha256"], "expected_memory_revision": 2}
            self.ledger.checkpoint_context(identifier, **bound_args)
            held = deepcopy(bound)
            held.update(memory_revision=3, control=dict(state="paused", actor_id="local-owner",
                reason="Synthetic later hold."))
            self.ledger.save_context(held, expected_revision=2)
            with HandoffLedger(self.path, read_only=True) as restarted:
                self.assertEqual(restarted.load_checkpoint(identifier, 1, **args)["profile"], old)
                self.assertEqual(restarted.load_checkpoint(identifier, 2, **bound_args)["profile"], bound)
                self.assertEqual(len(restarted.list_checkpoints(identifier)["checkpoints"]), 2)
                current = restarted.load_context(identifier, expected_source_revision=REVISION,
                    expected_memory_revision=3, audience="owner_private")["profile"]
                self.assertEqual(current, held)

    def test_failed_checkpoint_commit_rolls_back_table_upgrade_and_keeps_review(self):
        self.profile = self.control_profile("paused")
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        review = self.ledger.review_context("mission-one", reviewer_id="local-evaluator",
            expected_sha256=saved["context_sha256"], expected_revision=1, include_receipt=True)
        self.stage("mission-two", target="gemini")
        neighbor = self.context("mission-two")
        self.ledger.save_context(neighbor, expected_revision=0)
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                    expected_memory_revision=1, expected_revision=1)
        before = tuple(self.ledger.db.iterdump())
        commits, returned = [], []

        def deny_commit(action, name, *_):
            if action == sqlite3.SQLITE_TRANSACTION and name == "COMMIT":
                commits.append(name)
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        self.ledger.db.set_authorizer(deny_commit)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                returned.append(self.ledger.checkpoint_context("mission-one", **args))
        finally:
            self.ledger.db.set_authorizer(None)
        self.assertEqual(commits, ["COMMIT"])
        self.assertEqual(returned, [])
        self.assertFalse(self.ledger.db.in_transaction)
        self.assertEqual(self.ledger.db.execute("PRAGMA user_version").fetchone()[0], 2)
        self.assertIsNone(self.ledger.db.execute(
            "SELECT name FROM sqlite_master WHERE name='context_checkpoints'").fetchone())
        self.assertEqual(tuple(self.ledger.db.iterdump()), before)
        self.ledger.db.commit()  # Must not publish any rejected upgrade later.
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        self.assertEqual(tuple(self.ledger.db.iterdump()), before)
        self.assertEqual(self.ledger.db.execute("PRAGMA user_version").fetchone()[0], 2)
        self.assertEqual(self.load()["profile"], self.profile)
        self.assertEqual(self.load("mission-two")["profile"], neighbor)
        self.assertTrue(self.ledger.check_context_review_receipt("mission-one", review)["local_binding_matches"])
        self.assert_exports_blocked(saved["context_sha256"])
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        captured = self.ledger.checkpoint_context("mission-one", **args)
        self.assertFalse(captured["duplicate"])
        self.assertEqual(captured["checkpoint_revision"], 1)
        self.assertTrue(self.ledger.checkpoint_context("mission-one", **args)["duplicate"])
        self.assertTrue(self.ledger.check_context_review_receipt("mission-one", review)["local_binding_matches"])
        self.assertEqual(self.load()["profile"], self.profile)
        self.assertEqual(self.load("mission-two")["profile"], neighbor)

    def test_checkpoint_rejections_do_not_upgrade_or_change_existing_records(self):
        saved = self.save()
        args = dict(expected_sha256=saved["context_sha256"], expected_source_revision=REVISION, expected_memory_revision=1)
        before = list(self.ledger.db.iterdump())
        for change in (dict(expected_sha256="0" * 64), dict(expected_source_revision="0" * 40),
                       dict(expected_memory_revision=True)):
            with self.assertRaises(ValueError):
                self.ledger.checkpoint_context("mission-one", **{**args, **change})
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.assertEqual(self.ledger.db.execute("PRAGMA user_version").fetchone()[0], 2)
        with patch("control_tower.handoffs.MAX_CONTEXT_CHECKPOINTS", 0), self.assertRaises(ValueError):
            self.ledger.checkpoint_context("mission-one", **args)
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.assertEqual(self.ledger.db.execute("PRAGMA user_version").fetchone()[0], 2)
        self.ledger.checkpoint_context("mission-one", **args)
        self.stage("independent-task")
        independent = self.context("independent-task")
        second = self.ledger.save_context(independent, expected_revision=0)
        second_args = {**args, "expected_sha256": second["context_sha256"]}
        self.ledger.checkpoint_context("independent-task", **second_args)
        self.assertEqual(self.ledger.load_checkpoint("independent-task", 1, **second_args)["profile"], independent)
        self.assertEqual(self.ledger.load_checkpoint("mission-one", 1, **args)["profile"], self.profile)
        with HandoffLedger(self.path, read_only=True) as inspected:
            self.assertEqual(inspected.load_checkpoint("mission-one", 1, **args)["profile"], self.profile)
            with self.assertRaises(ValueError):
                inspected.checkpoint_context("mission-one", **args)
            with self.assertRaises(ValueError):
                inspected.load_checkpoint("mission-one", 1, **{**args, "expected_memory_revision": 2})
        self.ledger.db.execute("UPDATE context_checkpoints SET body='{}'")
        with self.assertRaises(ValueError):
            self.ledger.load_checkpoint("mission-one", 1, **args)

    def test_platform_queue_selection_retains_holds_guards_and_legacy_reports(self):
        args = dict(project_id="ai-jarvis")
        unconfigured = self.ledger.queue_report(**args, platform="codex")
        self.assertEqual(unconfigured["execution_states"]["without_context"], 1)
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        self.save()
        self.stage("mission-two", target="gemini")
        neighbor = self.context("mission-two")
        self.ledger.save_context(neighbor, expected_revision=0)
        legacy = self.ledger.queue_report(**args)
        self.assertEqual(legacy["schema_version"], 1)
        self.assertEqual(self.ledger.queue_report(**args, platform=None), legacy)
        self.assertEqual(legacy["handoff_count"], 2)
        damaged = {**neighbor, "memory_revision": True}
        self.ledger.db.execute("UPDATE handoff_contexts SET body=?,digest=? WHERE handoff_id=?",
            (json.dumps(damaged), digest(damaged), "mission-two"))
        try:
            with self.assertRaisesRegex(ValueError, "stored context"):
                self.ledger.queue_report(**args, platform="codex")
        finally:
            self.ledger.db.execute("UPDATE handoff_contexts SET body=?,digest=? WHERE handoff_id=?",
                (json.dumps(neighbor), digest(neighbor), "mission-two"))
        for target in sorted(TARGETS):
            selected = self.ledger.queue_report(**args, platform=target)
            self.assertEqual(selected["schema_version"], 4)
            self.assertEqual(selected["platform"], target)
            self.assertEqual(selected["handoff_count"], int(target in {"codex", "gemini"}))
            self.assertTrue(all(b["platform"] == target for b in selected["bindings"]))
            self.assertFalse(selected["dispatch_authorized"])
            self.assertEqual(selected["completion_verification"], "not_established")
        selected_args = {**args, "platform": "codex", "mission_id": "mission-one", "include_review_state": True}
        first = self.ledger.queue_report(**selected_args)
        self.assertEqual(first["recorded_attempts"], 1)
        self.assertEqual(first["execution_states"]["outcome_unknown"], 1)
        self.assertEqual(first["control_states"]["paused"], 1)
        self.assertEqual(first["bindings"][0]["context_review_current"], False)
        with self.assertRaisesRegex(ValueError, "queue report is stale"):
            self.ledger.queue_report(**{**selected_args, "platform": "gemini"},
                expected_sha256=first["report_sha256"])
        before = tuple(self.ledger.db.iterdump())
        for invalid in ("unknown", "", True, 1, []):
            with self.assertRaises(ValueError):
                self.ledger.queue_report(**args, platform=invalid)
        self.assertEqual(tuple(self.ledger.db.iterdump()), before)
        self.profile["memory_revision"] = 2
        self.profile["execution"]["detail"] = "Synthetic retained reconciliation note."
        self.ledger.save_context(self.profile, expected_revision=1)
        with self.assertRaisesRegex(ValueError, "queue report is stale"):
            self.ledger.queue_report(**selected_args, expected_sha256=first["report_sha256"])
        current = self.ledger.queue_report(**selected_args)
        self.ledger.close()
        database_bytes = self.path.read_bytes()
        self.ledger = HandoffLedger(self.path, read_only=True)
        self.assertEqual(self.ledger.queue_report(**selected_args,
            expected_sha256=current["report_sha256"]), current)
        self.assertEqual(self.load(expected_memory_revision=2)["profile"], self.profile)
        self.assertEqual(self.load("mission-two")["profile"], neighbor)
        self.assertEqual(self.path.read_bytes(), database_bytes)

    def test_platform_queue_snapshot_is_independent_of_other_platform_edits(self):
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        review = self.ledger.review_context("mission-one", reviewer_id="local-evaluator",
            expected_sha256=saved["context_sha256"], expected_revision=1, include_receipt=True)
        self.stage("mission-two", target="gemini")
        neighbor = self.context("mission-two")
        other_saved = self.ledger.save_context(neighbor, expected_revision=0)
        self.ledger.review_context("mission-two", reviewer_id="local-evaluator",
            expected_sha256=other_saved["context_sha256"], expected_revision=1)
        args = dict(project_id="ai-jarvis", include_review_state=True)
        codex = self.ledger.queue_report(**args, platform="codex")
        gemini = self.ledger.queue_report(**args, platform="gemini")
        aggregate = self.ledger.queue_report(**args)
        neighbor["memory_revision"] = 2
        neighbor["execution"]["attempts"] = 2
        neighbor["execution"]["detail"] = "Synthetic independent Gemini private note."
        self.ledger.save_context(neighbor, expected_revision=1)
        self.assertEqual(self.ledger.queue_report(**args, platform="codex",
            expected_sha256=codex["report_sha256"]), codex)
        with self.assertRaisesRegex(ValueError, "queue report is stale"):
            self.ledger.queue_report(**args, platform="gemini", expected_sha256=gemini["report_sha256"])
        changed = self.ledger.queue_report(**args, platform="gemini")
        self.assertFalse(changed["bindings"][0]["context_review_current"])
        self.assertEqual(changed["recorded_attempts"], 2)
        self.assertEqual(changed["bindings"][0]["context_revision"], 2)
        self.assertTrue(codex["bindings"][0]["context_review_current"])
        self.assertEqual(codex["recorded_attempts"], 1)
        self.assertEqual(codex["control_states"]["paused"], 1)
        self.assertEqual(codex["execution_states"]["outcome_unknown"], 1)
        self.assertNotEqual(self.ledger.queue_report(**args)["report_sha256"], aggregate["report_sha256"])
        self.assertNotIn("Gemini private note", json.dumps(changed))
        self.ledger.close()
        before = self.path.read_bytes()
        self.ledger = HandoffLedger(self.path, read_only=True)
        self.assertEqual(self.ledger.queue_report(**args, platform="codex",
            expected_sha256=codex["report_sha256"]), codex)
        self.assertEqual(self.ledger.queue_report(**args, platform="gemini",
            expected_sha256=changed["report_sha256"]), changed)
        self.assertTrue(self.ledger.check_context_review_receipt("mission-one", review)["local_binding_matches"])
        self.assertEqual(self.load()["profile"], self.profile)
        self.assertEqual(self.load("mission-two", expected_memory_revision=2)["profile"], neighbor)
        self.assertEqual(self.path.read_bytes(), before)

    def test_mission_queue_report_selects_all_portable_targets_after_restart(self):
        for index, target in enumerate(sorted(TARGETS)):
            identifier = "selected-" + target
            manifest = build_swarm("ai-jarvis", [target], swarm_id="queue-" + target,
                                   source_revision=REVISION)
            self.ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
                target=target, text="Synthetic selective queue fixture."), manifest,
                assistant_id=manifest["swarm_id"] + ".builder", handoff_id=identifier)
            profile = self.context(identifier)
            profile.update(asset_id=manifest["swarm_id"] + ".builder",
                schema_version=3, mission_id="shared-mission", destination_id="destination-" + target,
                control={"state": ("active", "paused", "cancelled")[index % 3],
                         "actor_id": "local-controller", "reason": "Private control detail."})
            profile["execution"]["state"] = "outcome_unknown" if index % 2 else "execution_blocked"
            self.ledger.save_context(profile, expected_revision=0)
        self.save()  # Another mission; the original contextless case is separate.
        self.stage("contextless-task")
        first = self.ledger.queue_report(project_id="ai-jarvis", mission_id="shared-mission")
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        before = self.path.read_bytes()
        self.assertEqual(self.ledger.queue_report(project_id="ai-jarvis", mission_id="shared-mission"), first)
        self.assertEqual(first["schema_version"], 2)
        self.assertEqual(first["mission_id"], "shared-mission")
        self.assertEqual(first["handoff_count"], len(TARGETS))
        self.assertEqual({r["platform"] for r in first["bindings"]}, set(TARGETS))
        self.assertEqual({r["mission_id"] for r in first["bindings"]}, {"shared-mission"})
        self.assertEqual(first["recorded_attempts"], len(TARGETS))
        self.assertEqual(sum(first["execution_states"].values()), len(TARGETS))
        self.assertEqual(sum(first["control_states"].values()), len(TARGETS))
        self.assertEqual(first["execution_states"]["without_context"], 0)
        for omitted in ("mission-one", "contextless-task", "Private control detail", "Synthetic", "https://"):
            self.assertNotIn(omitted, json.dumps(first))
        self.assertEqual(first["visibility"], "owner_private")
        self.assertEqual(first["completion_verification"], "not_established")
        self.assertFalse(first["dispatch_authorized"])
        self.assertEqual(first["report_sha256"], digest({k: v for k, v in first.items() if k != "report_sha256"}))
        first["bindings"].clear()
        self.assertEqual(self.ledger.queue_report(project_id="ai-jarvis", mission_id="shared-mission")["handoff_count"], len(TARGETS))
        self.assertEqual(self.path.read_bytes(), before)

    def test_queue_review_state_binds_exact_local_review_after_restart(self):
        self.profile = self.control_profile("paused")
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        self.ledger.review("mission-one", reviewer_id="local-evaluator", expected_sha256=self.receipt["handoff_sha256"])
        args = dict(project_id="ai-jarvis", mission_id="mission-one")
        legacy = self.ledger.queue_report(**args)
        first = self.ledger.queue_report(**args, include_review_state=True)
        self.assertEqual(first["schema_version"], 3)
        self.assertTrue(first["bindings"][0]["handoff_review_current"])
        self.assertFalse(first["bindings"][0]["context_review_current"])
        self.ledger.review_context("mission-one", reviewer_id="local-evaluator", expected_sha256=saved["context_sha256"])
        self.assertEqual(self.ledger.queue_report(**args), legacy)
        with self.assertRaisesRegex(ValueError, "queue report is stale"):
            self.ledger.queue_report(**args, include_review_state=True, expected_sha256=first["report_sha256"])
        reviewed = self.ledger.queue_report(**args, include_review_state=True)
        self.assertTrue(reviewed["bindings"][0]["context_review_current"])
        self.assertEqual(reviewed["review_authority"], "local_record_only_not_identity_authentication")
        self.assertFalse(reviewed["dispatch_authorized"])
        self.assertNotIn("local-evaluator", json.dumps(reviewed))
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        before = self.path.read_bytes()
        self.assertEqual(self.ledger.queue_report(**args, include_review_state=True,
            expected_sha256=reviewed["report_sha256"]), reviewed)
        self.assertEqual(self.load()["profile"], self.profile)
        self.assertEqual(self.path.read_bytes(), before)
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        changed = deepcopy(self.profile)
        changed["execution"]["detail"] = "Edited private evidence; review again."
        self.ledger.save_context(changed, expected_revision=1)
        edited = self.ledger.queue_report(**args, include_review_state=True)
        self.assertFalse(edited["bindings"][0]["context_review_current"])
        self.assertTrue(edited["bindings"][0]["handoff_review_current"])
        self.assertEqual(edited["control_states"]["paused"], 1)
        self.assertEqual(edited["execution_states"]["outcome_unknown"], 1)

    def test_queue_review_state_is_opt_in_and_contextless_is_unknown(self):
        self.save()
        self.stage("contextless-task")
        original = self.ledger.queue_report(project_id="ai-jarvis")
        selected = self.ledger.queue_report(project_id="ai-jarvis", mission_id="mission-one")
        before = list(self.ledger.db.iterdump())
        result = self.ledger.queue_report(project_id="ai-jarvis", include_review_state=True)
        self.assertEqual(result["schema_version"], 3)
        row = next(x for x in result["bindings"] if x["handoff_id"] == "contextless-task")
        self.assertIsNone(row["context_review_current"])
        self.assertFalse(row["handoff_review_current"])
        for old in (original, selected):
            self.assertNotIn("review_authority", old)
            self.assertNotIn("context_review_current", json.dumps(old))
        self.assertEqual((original["schema_version"], selected["schema_version"]), (1, 2))
        for invalid in (None, 0, 1, "true", []):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.ledger.queue_report(project_id="ai-jarvis", include_review_state=invalid)
        result["bindings"][0]["handoff_review_current"] = True
        self.assertEqual(self.ledger.queue_report(project_id="ai-jarvis"), original)
        self.assertEqual(list(self.ledger.db.iterdump()), before)

    def test_queue_snapshot_guard_detects_selected_changes_after_restart(self):
        self.profile = self.control_profile("paused")
        self.profile["execution"]["state"] = "outcome_unknown"
        self.save()
        selected = self.ledger.queue_report(project_id="ai-jarvis", mission_id="mission-one")
        whole = self.ledger.queue_report(project_id="ai-jarvis")
        self.stage("unrelated-task")
        self.ledger.save_context(self.context("unrelated-task"), expected_revision=0)
        self.assertEqual(self.ledger.queue_report(project_id="ai-jarvis", mission_id="mission-one",
            expected_sha256=selected["report_sha256"]), selected)
        with self.assertRaisesRegex(ValueError, "queue report is stale"):
            self.ledger.queue_report(project_id="ai-jarvis", expected_sha256=whole["report_sha256"])
        changed = deepcopy(self.profile)
        changed["memory_revision"] = 2
        changed["execution"]["detail"] = "Updated private evidence; retain unknown hold."
        self.ledger.save_context(changed, expected_revision=1)
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "queue report is stale"):
            self.ledger.queue_report(project_id="ai-jarvis", mission_id="mission-one",
                expected_sha256=selected["report_sha256"])
        current = self.ledger.queue_report(project_id="ai-jarvis", mission_id="mission-one")
        self.assertEqual(self.ledger.queue_report(project_id="ai-jarvis", mission_id="mission-one",
            expected_sha256=current["report_sha256"]), current)
        self.assertEqual(self.load(expected_memory_revision=2)["profile"], changed)
        self.assertEqual(current["execution_states"]["outcome_unknown"], 1)
        self.assertEqual(current["control_states"]["paused"], 1)
        self.assertFalse(current["dispatch_authorized"])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.ledger.db.in_transaction)

    def test_queue_report_keeps_snapshot_during_concurrent_mission_membership(self):
        self.assertEqual(self.ledger.db.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        self.profile = self.control_profile("paused")
        self.profile["execution"]["state"] = "outcome_unknown"
        self.save()
        self.stage("z-member")  # Already staged, but not yet assigned context/mission.
        member = self.context("z-member")
        member["mission_id"] = "mission-one"
        args = dict(project_id="ai-jarvis", mission_id="mission-one", include_review_state=True)
        original = self.load()
        committed = []
        with HandoffLedger(self.path, read_only=True) as reader:
            expected = reader.queue_report(**args)
            handoff = reader._handoff

            def assign_between_reads(identifier):
                selected = handoff(identifier)
                if not committed:
                    committed.append(self.ledger.save_context(member, expected_revision=0))
                return selected

            with patch.object(reader, "_handoff", side_effect=assign_between_reads):
                in_flight = reader.queue_report(**args, expected_sha256=expected["report_sha256"])
            self.assertEqual(len(committed), 1)
            self.assertEqual(in_flight, expected)
            self.assertEqual(in_flight["handoff_count"], 1)
            self.assertFalse(reader.db.in_transaction)
            written_rows = list(self.ledger.db.iterdump())
            with self.assertRaisesRegex(ValueError, "queue report is stale"):
                reader.queue_report(**args, expected_sha256=expected["report_sha256"])
            current = reader.queue_report(**args)
            self.assertEqual(current["handoff_count"], 2)
            self.assertEqual({r["handoff_id"] for r in current["bindings"]}, {"mission-one", "z-member"})
            self.assertEqual(current["control_states"]["paused"], 1)
            self.assertEqual(current["execution_states"]["outcome_unknown"], 1)
            self.assertFalse(current["dispatch_authorized"])
            self.assertEqual(current["external_actions"], 0)
            self.assertNotIn("https://", json.dumps(current))
            self.assertEqual(reader.queue_report(**args, expected_sha256=current["report_sha256"]), current)
            self.assertEqual(list(self.ledger.db.iterdump()), written_rows)
        with HandoffLedger(self.path, read_only=True) as restarted:
            self.assertEqual(restarted.queue_report(**args), current)
        self.assertEqual(self.load(), original)
        self.assertEqual(self.load("z-member")["profile"], member)

    def test_queue_snapshot_guard_binds_scope_and_new_mission_membership(self):
        self.save()
        selected = self.ledger.queue_report(project_id="ai-jarvis", mission_id="mission-one")
        for scope in ({}, {"mission_id": "other-mission"}, {"project_id": "publishing-studio"}):
            with self.subTest(scope=scope), self.assertRaisesRegex(ValueError, "queue report is stale"):
                self.ledger.queue_report(**{**{"project_id": "ai-jarvis"}, **scope},
                    expected_sha256=selected["report_sha256"])
        for invalid in ("", "bad", True, [], "A" * 64):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.ledger.queue_report(project_id="ai-jarvis", expected_sha256=invalid)
        self.stage("new-member")
        member = self.context("new-member")
        member["mission_id"] = "mission-one"
        self.ledger.save_context(member, expected_revision=0)
        with self.assertRaisesRegex(ValueError, "queue report is stale"):
            self.ledger.queue_report(project_id="ai-jarvis", mission_id="mission-one",
                expected_sha256=selected["report_sha256"])
        self.assertEqual(self.ledger.queue_report(project_id="ai-jarvis", mission_id="mission-one")["handoff_count"], 2)

    def test_mission_queue_report_empty_scope_and_legacy_contract(self):
        self.save()
        legacy = self.ledger.queue_report(project_id="ai-jarvis")
        self.assertEqual(legacy["schema_version"], 1)
        self.assertNotIn("mission_id", legacy)
        before = list(self.ledger.db.iterdump())
        empty = self.ledger.queue_report(project_id="ai-jarvis", mission_id="absent-mission")
        self.assertEqual(empty["schema_version"], 2)
        self.assertEqual(empty["bindings"], [])
        self.assertEqual(empty["handoff_count"], 0)
        self.assertEqual(empty["recorded_attempts"], 0)
        for invalid in ("", "../mission", True, [], 1):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.ledger.queue_report(project_id="ai-jarvis", mission_id=invalid)
        self.assertEqual(self.ledger.queue_report(project_id="ai-jarvis"), legacy)
        self.assertEqual(list(self.ledger.db.iterdump()), before)

    def test_queue_report_retains_recorded_blocks_after_restart_without_private_text(self):
        self.profile = self.control_profile("paused")
        self.profile["execution"]["state"] = "outcome_unknown"
        self.save()
        self.stage("contextless-task")
        before = list(self.ledger.db.iterdump())
        first = self.ledger.queue_report(project_id="ai-jarvis")
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        self.assertEqual(self.ledger.queue_report(project_id="ai-jarvis"), first)
        self.assertEqual(first["handoff_count"], 2)
        self.assertEqual(first["execution_states"]["outcome_unknown"], 1)
        self.assertEqual(first["execution_states"]["without_context"], 1)
        self.assertEqual(first["control_states"]["paused"], 1)
        self.assertEqual(first["recorded_attempts"], 1)
        self.assertEqual(first["completion_verification"], "not_established")
        self.assertEqual(first["duplicate_attempts"], "not_recorded")
        self.assertFalse(first["dispatch_authorized"])
        self.assertNotIn("Synthetic", json.dumps(first))
        self.assertNotIn("https://", json.dumps(first))
        checksum = first.pop("report_sha256")
        self.assertEqual(digest(first), checksum)
        first["execution_states"]["outcome_unknown"] = 99
        self.assertEqual(self.ledger.queue_report(project_id="ai-jarvis")["execution_states"]["outcome_unknown"], 1)
        self.assertEqual(list(self.ledger.db.iterdump()), before)

    def test_queue_report_is_project_scoped_and_tracks_context_revision_changes(self):
        self.save()
        manifest = build_swarm("publishing-studio", ["github"], swarm_id="other-project", source_revision=REVISION)
        self.ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="publishing-studio",
            target="github", text="Unrelated private publishing draft."), manifest,
            assistant_id="other-project.builder", handoff_id="other-project-task")
        first = self.ledger.queue_report(project_id="ai-jarvis")
        other = self.ledger.queue_report(project_id="publishing-studio")
        self.assertEqual(other["handoff_count"], 1)
        self.assertEqual([r["handoff_id"] for r in first["bindings"]], ["mission-one"])
        self.assertEqual([r["handoff_id"] for r in other["bindings"]], ["other-project-task"])
        self.assertEqual(first["bindings"][0]["source_revision"], REVISION)
        self.assertEqual(first["bindings"][0]["memory_revision"], 1)
        self.profile["execution"]["detail"] = "Updated private checkpoint."
        self.ledger.save_context(self.profile, expected_revision=1)
        changed = self.ledger.queue_report(project_id="ai-jarvis")
        self.assertNotEqual(changed["report_sha256"], first["report_sha256"])
        self.assertEqual(changed["bindings"][0]["context_revision"], 2)
        with self.assertRaises(ValueError):
            self.ledger.queue_report(project_id="unknown")

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

    def test_context_export_rejects_damaged_context_reviewer_after_restart(self):
        saved = self.approve()
        for reviewer in (None, "memory-pilot.builder", "../reviewer"):
            with self.subTest(reviewer=reviewer):
                self.ledger.db.execute("UPDATE handoff_contexts SET reviewer_id=? WHERE handoff_id='mission-one'", (reviewer,))
                self.ledger.close()
                self.ledger = HandoffLedger(self.path)
                before = tuple(self.ledger.db.iterdump())
                with self.assertRaisesRegex(ValueError, "review"):
                    self.export(saved["context_sha256"])
                self.assertEqual(tuple(self.ledger.db.iterdump()), before)

    def test_context_export_rejects_damaged_original_reviewer_after_restart(self):
        saved = self.approve()
        for reviewer in (None, "memory-pilot.builder", "../reviewer"):
            with self.subTest(reviewer=reviewer):
                self.ledger.db.execute("UPDATE handoffs SET reviewer_id=? WHERE id='mission-one'", (reviewer,))
                self.ledger.close()
                self.ledger = HandoffLedger(self.path)
                before = tuple(self.ledger.db.iterdump())
                with self.assertRaisesRegex(ValueError, "review"):
                    self.export(saved["context_sha256"])
                self.assertEqual(tuple(self.ledger.db.iterdump()), before)

    def test_cyclic_stored_ancestry_fails_closed(self):
        self.ledger.review("mission-one", reviewer_id="local-evaluator",
                           expected_sha256=self.receipt["handoff_sha256"])
        _, body = self.ledger._handoff("mission-one")
        body["parent_id"] = "mission-one"
        checksum = digest(body)
        self.ledger.db.execute("UPDATE handoffs SET body=?,digest=?,reviewed_digest=?,state='reviewed' WHERE id=?",
                              (json.dumps(body), checksum, checksum, "mission-one"))
        with self.assertRaisesRegex(ValueError, "ancestry"):
            self.ledger.export("mission-one", expected_sha256=checksum)

    def test_rehashed_child_depth_cannot_reopen_the_dependency_budget(self):
        self.returned_parent()
        child = self.stage_followup()
        self.ledger.review("followup-one", reviewer_id="local-evaluator",
                           expected_sha256=child["handoff_sha256"])
        self.ledger.export("followup-one", expected_sha256=child["handoff_sha256"])
        _, body = self.ledger._handoff("followup-one")
        body["depth"] = 0
        checksum = digest(body)
        self.ledger.db.execute("UPDATE handoffs SET body=?,digest=?,reviewed_digest=? WHERE id=?",
                              (json.dumps(body), checksum, checksum, "followup-one"))
        self.ledger.import_return(dict(schema_version=1, kind="jarvis.return", return_id="child-return",
            handoff_id="followup-one", handoff_sha256=checksum, source_provider="codex",
            text="Synthetic unverified child result.", evidence_urls=[]))
        before = tuple(self.ledger.db.iterdump())
        with self.assertRaisesRegex(ValueError, "depth"):
            self.ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
                target="codex", text="Must not exceed the original depth-one budget."), self.manifest,
                assistant_id="memory-pilot.evaluator", handoff_id="excess-child", parent_id="followup-one")
        self.assertEqual(tuple(self.ledger.db.iterdump()), before)

    def test_valid_depth_two_chain_survives_restart_and_keeps_its_budget(self):
        manifest = build_swarm("ai-jarvis", ["codex"], swarm_id="depth-pilot",
                               source_revision=REVISION, max_depth=2, max_handoffs_per_assistant=5)
        parent = None
        for index in range(3):
            identifier = f"depth-task-{index}"
            saved = self.ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
                target="codex", text="Synthetic bounded depth task."), manifest,
                assistant_id="depth-pilot.builder", handoff_id=identifier, parent_id=parent)
            self.ledger.review(identifier, reviewer_id="local-evaluator", expected_sha256=saved["handoff_sha256"])
            self.ledger.export(identifier, expected_sha256=saved["handoff_sha256"])
            self.ledger.import_return(dict(schema_version=1, kind="jarvis.return", return_id=f"depth-return-{index}",
                handoff_id=identifier, handoff_sha256=saved["handoff_sha256"], source_provider="codex",
                text="Synthetic unverified depth result.", evidence_urls=[]))
            parent = identifier
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        self.assertEqual([body["depth"] for _, body in self.ledger._lineage(parent)], [2, 1, 0])
        before = tuple(self.ledger.db.iterdump())
        with self.assertRaisesRegex(ValueError, "depth budget"):
            self.ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
                target="codex", text="Must not exceed depth two."), manifest,
                assistant_id="depth-pilot.builder", handoff_id="depth-task-3", parent_id=parent)
        self.assertEqual(tuple(self.ledger.db.iterdump()), before)

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

    def test_inspection_revision_guard_rejects_restored_context_after_restart(self):
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        first = self.save()
        original = deepcopy(self.profile)
        self.stage("mission-two")
        self.ledger.save_context(self.context("mission-two"), expected_revision=0)
        self.profile["execution"]["detail"] = "Temporary private edit."
        self.ledger.save_context(self.profile, expected_revision=1)
        restored = self.ledger.save_context(original, expected_revision=2)
        self.assertEqual(first["context_sha256"], restored["context_sha256"])
        self.ledger.close()
        before = self.path.read_bytes()
        self.ledger = HandoffLedger(self.path, read_only=True)
        default = self.inspect()
        self.assertEqual(default["lineage"][0]["context"]["revision"], 3)
        for revision in (1, 2, 4, 0, -1, True, "3"):
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                self.inspect(expected_revision=revision)
        self.assertEqual(self.inspect(expected_revision=3), default)
        self.assertIn("outcome_unknown", default["lineage"][0]["holds"])
        self.assertIn("paused", default["lineage"][0]["holds"])
        self.assertFalse(default["retry_authorized"])
        self.assertEqual(self.load("mission-two")["profile"], self.context("mission-two"))
        self.assertEqual(self.path.read_bytes(), before)

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
        self.assertEqual(first["schema_version"], 1)
        self.assertNotIn("destination_id", first)
        self.assertFalse(first["retry_authorized"])
        self.assertNotIn("context_refs", first)
        checksum = first.pop("proposal_sha256")
        self.assertEqual(digest(first), checksum)
        first["evidence_refs"].clear()
        self.assertEqual(len(self.proposal()["evidence_refs"]), 1)
        self.assert_exports_blocked(saved["context_sha256"])

    def test_destination_reconciliation_preserves_exact_destination_after_restart(self):
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "cancelled"
        saved = self.proposal_fixture()
        before = list(self.ledger.db.iterdump())
        first = self.proposal()
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        self.assertEqual(self.proposal(), first)
        self.assertEqual(first["schema_version"], 2)
        self.assertEqual(first["destination_id"], "repository-one")
        self.assertEqual(first["platform"], "codex")
        self.assertEqual(first["context_sha256"], saved["context_sha256"])
        self.assertEqual(first["control_state"], "cancelled")
        self.assertEqual(first["execution"]["state"], "outcome_unknown")
        self.assertEqual(first["visibility"], "owner_private")
        self.assertFalse(first["retry_authorized"])
        checksum = first.pop("proposal_sha256")
        self.assertEqual(digest(first), checksum)
        first["destination_id"] = "repository-two"
        self.assertNotEqual(digest(first), checksum)
        self.assertEqual(self.proposal()["destination_id"], "repository-one")
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.assert_exports_blocked(saved["context_sha256"])

    def test_controlled_legacy_reconciliation_preserves_version_one_shape(self):
        self.profile = self.control_profile("paused")
        self.proposal_fixture()
        proposal = self.proposal()
        self.assertEqual(proposal["schema_version"], 1)
        self.assertNotIn("destination_id", proposal)
        self.assertEqual(set(proposal), {"project_id", "mission_id", "asset_id", "platform",
            "source_revision", "memory_revision", "configuration_version", "allowed_actions",
            "budget", "execution", "evidence_refs", "schema_version", "kind", "handoff_id",
            "handoff_sha256", "context_sha256", "context_revision", "inspection_sha256",
            "visibility", "control_state", "review_state", "proposed_resolution",
            "evidence_verification", "retry_authorized", "external_actions", "proposal_sha256"})

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

    def test_destination_review_snapshot_is_atomic_during_concurrent_reviews(self):
        self.assertEqual(self.ledger.db.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        first = self.save()
        self.stage("mission-two")
        second_profile = {**deepcopy(self.profile), "handoff_id": "mission-two",
            "mission_id": "mission-two", "handoff_sha256": self.context("mission-two")["handoff_sha256"]}
        second = self.ledger.save_context(second_profile, expected_revision=0)
        args = dict(project_id="ai-jarvis", platform="codex", destination_id="repository-one",
                    include_review_state=True)
        with HandoffLedger(self.path, read_only=True) as inspected:
            before = inspected.destination_status(**args)
            context = inspected._context
            committed = []
            writer_rows = []

            def review_between_reads(identifier):
                selected = context(identifier)  # Real read establishes the snapshot.
                if not committed:
                    for mission, saved in (("mission-one", first), ("mission-two", second)):
                        self.ledger.review(mission, reviewer_id="local-evaluator",
                            expected_sha256=self.context(mission)["handoff_sha256"])
                        self.ledger.review_context(mission, reviewer_id="local-evaluator",
                            expected_sha256=saved["context_sha256"])
                    committed.append(True)
                    writer_rows.extend(self.ledger.db.iterdump())
                return selected

            with patch.object(inspected, "_context", side_effect=review_between_reads):
                snapshot = inspected.destination_status(**args)
            self.assertEqual(committed, [True])
            self.assertEqual(snapshot, before)
            self.assertFalse(inspected.db.in_transaction)
            current = inspected.destination_status(**args)
            self.assertEqual(len(current["records"]), 2)
            for record in current["records"]:
                self.assertTrue(record["handoff_review_current"])
                self.assertTrue(record["context_review_current"])
                self.assertEqual((record["control_state"], record["execution_state"]),
                                 ("paused", "outcome_unknown"))
            self.assertNotEqual(current["report_sha256"], before["report_sha256"])
            self.assertEqual(current["report_sha256"], digest({k: v for k, v in current.items()
                                                               if k != "report_sha256"}))
            with self.assertRaisesRegex(ValueError, "destination report is stale"):
                inspected.destination_status(**args, expected_sha256=before["report_sha256"])
            self.assertFalse(inspected.db.in_transaction)
            self.assertEqual(list(self.ledger.db.iterdump()), writer_rows)
        with HandoffLedger(self.path, read_only=True) as restarted:
            self.assertEqual(restarted.destination_status(**args), current)
            self.assertEqual(restarted.load_context("mission-one", expected_source_revision=REVISION,
                expected_memory_revision=1)["profile"], self.profile)
            self.assertEqual(restarted.load_context("mission-two", expected_source_revision=REVISION,
                expected_memory_revision=1)["profile"], second_profile)
        for private in ("Synthetic", "https://", "reviewer_id", "local-evaluator"):
            self.assertNotIn(private, json.dumps(current))
        self.assertFalse(current["dispatch_authorized"])
        self.assertEqual(current["external_actions"], 0)
        self.assert_exports_blocked(first["context_sha256"])

    def test_destination_review_snapshot_distinguishes_both_reviews_after_restart(self):
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        args = dict(project_id="ai-jarvis", platform="codex", destination_id="repository-one",
                    mission_id="mission-one", include_review_state=True)
        first = self.ledger.destination_status(**args)
        self.assertEqual(first["schema_version"], 4)
        self.assertEqual(first["review_authority"], "local_record_only_not_identity_authentication")
        self.ledger.review_context("mission-one", reviewer_id="local-evaluator", expected_sha256=saved["context_sha256"])
        second = self.ledger.destination_status(**args)
        self.assertEqual((second["records"][0]["handoff_review_current"], second["records"][0]["context_review_current"]), (False, True))
        with self.assertRaisesRegex(ValueError, "destination report is stale"):
            self.ledger.destination_status(**args, expected_sha256=first["report_sha256"])
        self.ledger.review("mission-one", reviewer_id="local-evaluator", expected_sha256=self.receipt["handoff_sha256"])
        both = self.ledger.destination_status(**args)
        changed = deepcopy(self.profile)
        changed["execution"]["detail"] = "Changed private evidence; keep unknown hold."
        self.ledger.save_context(changed, expected_revision=1)
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        before = self.path.read_bytes()
        report = self.ledger.destination_status(**args)
        self.assertEqual((report["records"][0]["handoff_review_current"], report["records"][0]["context_review_current"]), (True, False))
        self.assertEqual((report["records"][0]["control_state"], report["records"][0]["execution_state"]), ("paused", "outcome_unknown"))
        self.assertFalse(report["dispatch_authorized"])
        self.assertNotIn("Changed private evidence", json.dumps(report))
        self.assertNotIn("https://", json.dumps(report))
        self.assertEqual(report["report_sha256"], digest({k: v for k, v in report.items() if k != "report_sha256"}))
        with self.assertRaisesRegex(ValueError, "destination report is stale"):
            self.ledger.destination_status(**args, expected_sha256=both["report_sha256"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_destination_review_opt_in_preserves_legacy_and_selective_snapshot(self):
        self.profile = self.destination_profile()
        self.save()
        args = dict(project_id="ai-jarvis", platform="codex", destination_id="repository-one")
        for extra in ({}, {"include_digest": True}, {"mission_id": "mission-one"}):
            old = self.ledger.destination_status(**args, **extra)
            self.assertEqual(self.ledger.destination_status(**args, **extra, include_review_state=False), old)
            self.assertNotIn("handoff_review_current", old["records"][0])
            self.assertNotIn("review_authority", old)
        selected = self.ledger.destination_status(**args, mission_id="mission-one", include_review_state=True)
        self.stage("other-task")
        other = {**self.context("other-task"), "schema_version": 3, "destination_id": "repository-one",
                 "control": deepcopy(self.profile["control"])}
        saved = self.ledger.save_context(other, expected_revision=0)
        self.ledger.review_context("other-task", reviewer_id="local-evaluator", expected_sha256=saved["context_sha256"])
        self.assertEqual(self.ledger.destination_status(**args, mission_id="mission-one", include_review_state=True,
            expected_sha256=selected["report_sha256"]), selected)
        for extra in ({}, {"mission_id": "mission-one"}, {"mission_id": "absent", "include_review_state": True}):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, "destination report is stale"):
                self.ledger.destination_status(**args, **extra, expected_sha256=selected["report_sha256"])
        for invalid in (1, None, "", []):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.ledger.destination_status(**args, include_review_state=invalid)
        empty = self.ledger.destination_status(**args, mission_id="absent", include_review_state=True)
        self.assertEqual((empty["schema_version"], empty["records"]), (4, []))
        self.assertFalse(empty["dispatch_authorized"])

    def test_destination_mission_selection_retains_all_target_holds_after_restart(self):
        for target in sorted(TARGETS):
            identifier = "selected-" + target
            manifest = build_swarm("ai-jarvis", [target], swarm_id="destination-" + target, source_revision=REVISION)
            self.ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
                target=target, text="Synthetic selective destination fixture."), manifest,
                assistant_id=manifest["swarm_id"] + ".builder", handoff_id=identifier)
            profile = self.context(identifier)
            profile.update(asset_id=manifest["swarm_id"] + ".builder",
                schema_version=3, mission_id="shared-mission", destination_id="shared-destination",
                control=dict(state="paused", actor_id="local-owner", reason="Synthetic private hold."))
            profile["execution"]["state"] = "outcome_unknown"
            self.ledger.save_context(profile, expected_revision=0)
        self.profile = self.destination_profile("shared-destination")
        self.save()  # Different mission at the same Codex destination.
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        before = self.path.read_bytes()
        for target in sorted(TARGETS):
            args = dict(project_id="ai-jarvis", platform=target, destination_id="shared-destination",
                        mission_id="shared-mission")
            report = self.ledger.destination_status(**args)
            self.assertEqual(report["schema_version"], 3)
            self.assertEqual(report["mission_id"], "shared-mission")
            self.assertEqual(len(report["records"]), 1)
            self.assertEqual(report["platform"], target)
            self.assertEqual(report["records"][0]["handoff_id"], "selected-" + target)
            self.assertEqual(report["records"][0]["control_state"], "paused")
            self.assertEqual(report["records"][0]["execution_state"], "outcome_unknown")
            self.assertFalse(report["dispatch_authorized"])
            self.assertEqual(report["report_sha256"], digest({k: v for k, v in report.items() if k != "report_sha256"}))
            self.assertEqual(self.ledger.destination_status(**args, expected_sha256=report["report_sha256"]), report)
            self.assertNotIn("https://", json.dumps(report))
            self.assertNotIn("Synthetic", json.dumps(report))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.ledger.db.in_transaction)

    def test_destination_mission_snapshot_isolates_unrelated_edits_and_binds_membership(self):
        self.profile = self.destination_profile()
        self.save()
        args = dict(project_id="ai-jarvis", platform="codex", destination_id="repository-one")
        legacy = self.ledger.destination_status(**args)
        unfiltered = self.ledger.destination_status(**args, include_digest=True)
        selected = self.ledger.destination_status(**args, mission_id="mission-one")
        self.assertEqual((legacy["schema_version"], unfiltered["schema_version"]), (1, 2))
        self.assertNotIn("mission_id", legacy)
        self.assertNotIn("mission_id", unfiltered)
        for invalid in ("", "../mission", True, [], 1):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.ledger.destination_status(**args, mission_id=invalid)
        empty = self.ledger.destination_status(**args, mission_id="absent-mission")
        self.assertEqual(empty["records"], [])
        with self.assertRaisesRegex(ValueError, "destination report is stale"):
            self.ledger.destination_status(**args, mission_id="absent-mission", expected_sha256=selected["report_sha256"])
        self.stage("new-member")
        other = {**self.context("new-member"), "schema_version": 3, "destination_id": "repository-one",
            "control": deepcopy(self.profile["control"])}
        self.ledger.save_context(other, expected_revision=0)
        self.assertEqual(self.ledger.destination_status(**args, mission_id="mission-one",
            expected_sha256=selected["report_sha256"]), selected)
        with self.assertRaisesRegex(ValueError, "destination report is stale"):
            self.ledger.destination_status(**args, expected_sha256=unfiltered["report_sha256"])
        # Mission identity cannot change: stage a distinct matching member.
        manifest = build_swarm("ai-jarvis", ["codex"], swarm_id="second-pilot", source_revision=REVISION)
        self.ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
            target="codex", text="Synthetic matching member."), manifest,
            assistant_id="second-pilot.builder", handoff_id="matching-member")
        member = {**self.context("matching-member"), "asset_id": "second-pilot.builder",
            "schema_version": 3, "mission_id": "mission-one",
            "destination_id": "repository-one", "control": deepcopy(self.profile["control"])}
        self.ledger.save_context(member, expected_revision=0)
        with self.assertRaisesRegex(ValueError, "destination report is stale"):
            self.ledger.destination_status(**args, mission_id="mission-one", expected_sha256=selected["report_sha256"])

    def test_destination_snapshot_rejects_changed_evidence_after_restart(self):
        self.profile = self.destination_profile()
        self.profile["control"]["state"] = "paused"
        self.profile["execution"]["state"] = "outcome_unknown"
        saved = self.save()
        args = dict(project_id="ai-jarvis", platform="codex", destination_id="repository-one")
        legacy = self.ledger.destination_status(**args)
        first = self.ledger.destination_status(**args, include_digest=True)
        self.assertEqual(legacy["schema_version"], 1)
        self.assertNotIn("report_sha256", legacy)
        self.assertEqual(first["schema_version"], 2)
        self.assertEqual(first["report_sha256"], digest({k: v for k, v in first.items() if k != "report_sha256"}))
        self.stage("unrelated-task")
        other = {**self.context("unrelated-task"), "schema_version": 3,
            "destination_id": "repository-two", "control": deepcopy(self.profile["control"])}
        self.ledger.save_context(other, expected_revision=0)
        self.assertEqual(self.ledger.destination_status(**args, expected_sha256=first["report_sha256"]), first)
        self.ledger.review_context("mission-one", reviewer_id="local-evaluator", expected_sha256=saved["context_sha256"])
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "destination report is stale"):
            self.ledger.destination_status(**args, expected_sha256=first["report_sha256"])
        fresh = self.ledger.destination_status(**args, include_digest=True)
        self.assertEqual(self.ledger.destination_status(**args, expected_sha256=fresh["report_sha256"]), fresh)
        self.assertEqual(fresh["records"][0]["review_state"], "locally_reviewed")
        self.assertEqual(fresh["records"][0]["control_state"], "paused")
        self.assertEqual(fresh["records"][0]["execution_state"], "outcome_unknown")
        self.assertFalse(fresh["dispatch_authorized"])
        for omitted in ("https://", "Synthetic", "local-evaluator", "unrelated-task"):
            self.assertNotIn(omitted, json.dumps(fresh))
        self.assertEqual(self.load()["profile"], self.profile)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.ledger.db.in_transaction)

    def test_destination_snapshot_binds_scope_membership_and_validates_options(self):
        self.profile = self.destination_profile()
        self.save()
        args = dict(project_id="ai-jarvis", platform="codex", destination_id="repository-one")
        first = self.ledger.destination_status(**args, include_digest=True)
        before = list(self.ledger.db.iterdump())
        for change in (dict(project_id="publishing-studio"), dict(platform="github"),
                       dict(destination_id="repository-two")):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "destination report is stale"):
                self.ledger.destination_status(**{**args, **change}, expected_sha256=first["report_sha256"])
        for invalid in (None, 0, 1, "true", []):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.ledger.destination_status(**args, include_digest=invalid)
        for invalid in ("", "bad", True, [], "A" * 64):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.ledger.destination_status(**args, expected_sha256=invalid)
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        first["records"].clear()
        self.assertEqual(len(self.ledger.destination_status(**args, include_digest=True)["records"]), 1)
        self.stage("new-member")
        member = {**self.context("new-member"), "schema_version": 3,
            "destination_id": "repository-one", "control": deepcopy(self.profile["control"])}
        self.ledger.save_context(member, expected_revision=0)
        with self.assertRaisesRegex(ValueError, "destination report is stale"):
            self.ledger.destination_status(**args, expected_sha256=first["report_sha256"])
        self.assertEqual(len(self.ledger.destination_status(**args)["records"]), 2)

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

    def test_shared_reads_reject_rehashed_handoff_contract_changes(self):
        _, original = self.ledger._handoff("mission-one")
        for field, value in (("schema_version", 2), ("schema_version", True),
                             ("kind", "jarvis.return"), ("mode", "automatic_dispatch"),
                             ("external_actions", 1), ("external_actions", False)):
            with self.subTest(field=field, value=value):
                body = {**original, field: value}
                checksum = digest(body)
                self.ledger.db.execute("UPDATE handoffs SET body=?,digest=?,reviewed_digest=?,reviewer_id='local-evaluator',state='reviewed' WHERE id=?",
                    (json.dumps(body), checksum, checksum, "mission-one"))
                before = list(self.ledger.db.iterdump())
                for read in (self.ledger.status,
                             lambda: self.ledger.export("mission-one", expected_sha256=checksum)):
                    with self.assertRaisesRegex(ValueError, "stored handoff contract"):
                        read()
                self.assertEqual(list(self.ledger.db.iterdump()), before)


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

    def configured_read(self):
        self.stage("github-read", target="github")
        profile = {**self.context("github-read"), "schema_version": 3, "destination_id": "repository-one",
            "control": {"state": "paused", "actor_id": "local-owner", "reason": "Keep the failed task paused."}}
        profile["execution"]["state"] = "outcome_unknown"
        saved = self.ledger.save_context(profile, expected_revision=0)
        url = f"https://api.github.com/repos/owner/repository/git/commits/{REVISION}"
        raw = json.dumps(dict(sha=REVISION, url=url)).encode()
        from hashlib import sha256
        observation = read_observation("github", observed_at="2026-10-28T00:00:00Z", evidence_url=url,
            response_sha256=sha256(raw).hexdigest(), scope="Synthetic commit read", source_revision=REVISION)
        registry = {"schema_version": 1, "kind": "jarvis.destination_registry", "registry_id": "local-test",
            "revision": 2, "source_revision": "a" * 40, "configuration_version": "read-config.v1",
            "visibility": "owner_private", "entries": [{"project_id": "ai-jarvis", "platform": "github",
                "destination_id": "repository-one", "resource_id": "owner/repository", "allowed_actions": ["read"]},
                {"project_id": "ai-jarvis", "platform": "github", "destination_id": "repository-two",
                 "resource_id": "other/private-repository", "allowed_actions": ["read"]}]}
        args = dict(expected_registry_sha256=digest(registry), expected_registry_revision=2,
            expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
            expected_memory_revision=1, now=datetime(2026, 10, 28, 1, tzinfo=timezone.utc))
        return raw, observation, registry, args

    def test_configured_observation_keeps_snapshot_during_concurrent_context_edit(self):
        self.assertEqual(self.ledger.db.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        self.save()  # Independent Codex context must remain intact.
        raw, observation, registry, args = self.configured_read()
        self.ledger.review_context("github-read", reviewer_id="local-evaluator",
            expected_sha256=args["expected_sha256"], expected_revision=1)
        original = self.ledger.load_context("github-read", expected_source_revision=REVISION,
            expected_memory_revision=1)["profile"]
        changed = deepcopy(original)
        changed["memory_revision"] = 2
        changed["execution"]["detail"] = "Concurrent writer preserves paused unknown outcome."
        committed = []
        with HandoffLedger(self.path, read_only=True) as reader:
            expected = reader.bind_configured_github_observation("github-read", observation, raw, registry,
                **args, expected_revision=1)
            handoff = reader._handoff

            def edit_between_reads(identifier):
                selected = handoff(identifier)  # Establish the real read snapshot.
                if identifier == "github-read" and not committed:
                    committed.append(self.ledger.save_context(changed, expected_revision=1))
                return selected

            with patch.object(reader, "_handoff", side_effect=edit_between_reads):
                observed = reader.bind_configured_github_observation("github-read", observation, raw, registry,
                    **args, expected_revision=1)
            self.assertEqual(len(committed), 1)
            self.assertEqual(observed, expected)
            self.assertEqual(observed["destination_observation"]["review_state"], "locally_reviewed")
            self.assertFalse(reader.db.in_transaction)
            writer_rows = tuple(self.ledger.db.iterdump())
            with self.assertRaisesRegex(ValueError, "context retrieval revision mismatch"):
                reader.bind_configured_github_observation("github-read", observation, raw, registry,
                    **args, expected_revision=1)
            self.assertFalse(reader.db.in_transaction)
            refreshed = reader.bind_configured_github_observation("github-read", observation, raw, registry,
                **{**args, "expected_sha256": committed[0]["context_sha256"], "expected_memory_revision": 2},
                expected_revision=2)
            self.assertEqual(refreshed["destination_observation"]["context_revision"], 2)
            self.assertEqual(refreshed["destination_observation"]["review_state"], "proposed")
            self.assertFalse(refreshed["dispatch_authorized"])
            self.assertEqual(reader.load_context("github-read", expected_source_revision=REVISION,
                expected_memory_revision=2)["profile"], changed)
            self.assertEqual(reader.load_context("mission-one", expected_source_revision=REVISION,
                expected_memory_revision=1)["profile"], self.profile)
            self.assertEqual(tuple(self.ledger.db.iterdump()), writer_rows)

    def test_observation_revision_rejects_restored_context_for_both_bindings(self):
        raw, observation, registry, args = self.configured_read()
        loaded = self.ledger.load_context("github-read", expected_source_revision=REVISION,
                                          expected_memory_revision=1)
        original = loaded["profile"]
        changed = deepcopy(original)
        changed["execution"]["detail"] = "Synthetic intervening context."
        self.ledger.save_context(changed, expected_revision=1)
        self.ledger.save_context(original, expected_revision=2)
        self.ledger.close()
        self.ledger = HandoffLedger(self.path, read_only=True)
        before = self.path.read_bytes()
        plain = {k: v for k, v in args.items() if not k.startswith("expected_registry")}
        for bind in (lambda **kw: self.ledger.bind_destination_observation("github-read", observation, **plain, **kw),
                     lambda **kw: self.ledger.bind_configured_github_observation("github-read", observation, raw, registry, **args, **kw)):
            for revision in (1, 2, 4, 0, True):
                with self.subTest(revision=revision), self.assertRaisesRegex(ValueError, "context retrieval revision"):
                    bind(expected_revision=revision)
                self.assertEqual(self.path.read_bytes(), before)
            current = bind(expected_revision=3)
            self.assertEqual(current, bind())
            result = current.get("destination_observation", current)
            self.assertEqual(result["context_revision"], 3)
            self.assertFalse(result["dispatch_authorized"])
            self.assertEqual(self.ledger.load_context("github-read", expected_source_revision=REVISION,
                expected_memory_revision=1)["profile"], original)
            self.assertEqual(self.path.read_bytes(), before)

    def test_configured_read_preserves_legacy_receipt_and_holds_across_read_only_restart(self):
        raw, observation, registry, args = self.configured_read()
        before = list(self.ledger.db.iterdump())
        envelope = self.ledger.bind_configured_github_observation("github-read", observation, raw, registry, **args)
        legacy = self.ledger.bind_destination_observation("github-read", observation,
            **{k: v for k, v in args.items() if not k.startswith("expected_registry")})
        self.assertEqual(envelope["destination_observation"], legacy)
        self.assertEqual(envelope["registry_binding"]["entry"], registry["entries"][0])
        self.assertNotIn("private-repository", json.dumps(envelope))
        self.assertNotIn("context_refs", json.dumps(envelope))
        self.assertFalse(envelope["dispatch_authorized"])
        self.assertEqual(envelope["sender_authentication"], "not_established")
        self.assertEqual(envelope["mapping_verification"], "supplied_configuration_only")
        self.assertEqual(digest({k: v for k, v in envelope.items() if k != "receipt_sha256"}), envelope["receipt_sha256"])
        self.assertEqual(list(self.ledger.db.iterdump()), before)
        self.ledger.close()
        original_bytes = self.path.read_bytes()
        try:
            with HandoffLedger(self.path, read_only=True) as ledger:
                self.assertEqual(ledger.bind_configured_github_observation("github-read", observation, raw, registry, **args), envelope)
                context = ledger.load_context("github-read", expected_source_revision=REVISION, expected_memory_revision=1)
                self.assertEqual(context["profile"]["execution"]["state"], "outcome_unknown")
                self.assertEqual(context["profile"]["control"]["state"], "paused")
                self.assertEqual(context["review_state"], "proposed")
            self.assertEqual(self.path.read_bytes(), original_bytes)
        finally:
            self.ledger = HandoffLedger(self.path)
        envelope["registry_binding"]["entry"]["resource_id"] = "changed/repository"
        self.assertEqual(registry["entries"][0]["resource_id"], "owner/repository")

    def test_configured_read_rejects_stale_registry_and_wrong_resource_or_destination(self):
        raw, observation, registry, args = self.configured_read()
        before = list(self.ledger.db.iterdump())
        for changes in ({"expected_registry_sha256": "0" * 64}, {"expected_registry_revision": 1},
                        {"expected_registry_revision": True}, {"expected_sha256": "0" * 64},
                        {"expected_source_revision": "b" * 40}, {"expected_memory_revision": 2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.ledger.bind_configured_github_observation("github-read", observation, raw, registry, **{**args, **changes})
        for field, value in (("project_id", "ai-evolutionary-evolutions"), ("platform", "codex"),
                             ("destination_id", "repository-other"), ("resource_id", "other/repository")):
            changed = deepcopy(registry)
            changed["entries"][0][field] = value
            if field == "platform":
                changed["entries"][0]["resource_id"] = "opaque-repository"
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.ledger.bind_configured_github_observation("github-read", observation, raw, changed,
                    **{**args, "expected_registry_sha256": digest(changed)})
        with self.assertRaises(ValueError):
            self.ledger.bind_configured_github_observation("github-read", observation, raw + b" ", registry, **args)
        self.assertEqual(list(self.ledger.db.iterdump()), before)

    def test_configured_read_requires_current_context_after_review_invalidation(self):
        raw, observation, registry, args = self.configured_read()
        self.ledger.review_context("github-read", reviewer_id="local-evaluator", expected_sha256=args["expected_sha256"])
        self.assertEqual(self.ledger.bind_configured_github_observation("github-read", observation, raw, registry,
            **args)["destination_observation"]["review_state"], "locally_reviewed")
        loaded = self.ledger.load_context("github-read", expected_source_revision=REVISION, expected_memory_revision=1)
        changed = loaded["profile"]
        changed["memory_revision"] = 2
        changed["execution"]["detail"] = "Retain uncertain outcome after a context revision."
        saved = self.ledger.save_context(changed, expected_revision=loaded["revision"])
        with self.assertRaises(ValueError):
            self.ledger.bind_configured_github_observation("github-read", observation, raw, registry, **args)
        result = self.ledger.bind_configured_github_observation("github-read", observation, raw, registry,
            **{**args, "expected_sha256": saved["context_sha256"], "expected_memory_revision": 2})
        self.assertEqual(result["destination_observation"]["review_state"], "proposed")
        self.assertFalse(result["dispatch_authorized"])

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
