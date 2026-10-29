"""Actual CLI subprocesses against synthetic private checkpoint fixtures."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from control_tower.handoffs import HandoffLedger
from control_tower.swarm_factory import build_swarm
from control_tower.network_contract import digest
from control_tower.connections import read_observation
from scripts.jarvis_network import _backup

ROOT = Path(__file__).resolve().parents[1]
REVISION = "b5fd40ff22814feae3b60a8761821856f0976d75"


class ContextCLITests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.db = self.root / "ledger.sqlite3"
        with HandoffLedger(self.db) as ledger:
            manifest = build_swarm("ai-jarvis", ["codex"], swarm_id="cli-pilot", source_revision=REVISION)
            staged = ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
                target="codex", text="Synthetic CLI checkpoint task."), manifest,
                assistant_id="cli-pilot.builder", handoff_id="cli-task")
        self.profile = dict(schema_version=1, kind="jarvis.handoff_context",
            handoff_id="cli-task", handoff_sha256=staged["handoff_sha256"], project_id="ai-jarvis",
            mission_id="cli-task", source_revision=REVISION, asset_id="cli-pilot.builder",
            platform="codex", configuration_version="cli-context.v1", memory_revision=1,
            visibility="owner_private", allowed_actions=["prepare_draft"], context_refs=[], evidence_refs=[],
            budget=dict(max_attempts=2, time_limit_seconds=120, paid_execution_authorized=False),
            execution=dict(state="execution_blocked", context_id="synthetic-cli", attempts=1,
                checkpoint_ref="https://example.invalid/checkpoint", detail="Synthetic blocked attempt."))
        self.write(self.profile)

    def tearDown(self):
        self.directory.cleanup()

    def write(self, profile):
        (self.root / "context.json").write_text(json.dumps(profile), encoding="utf-8")

    def cli(self, *args, database="ledger.sqlite3"):
        return subprocess.run([sys.executable, str(ROOT / "scripts/jarvis_network.py"),
            "--root", str(self.root), "--database", database, *args],
            capture_output=True, text=True, timeout=15, cwd=ROOT)

    def save(self, revision=0):
        return self.cli("save-context", "--file", "context.json", "--expected-revision", str(revision))

    def load(self, out="resumed.json", revision=REVISION, memory=1):
        return self.cli("load-context", "--handoff", "cli-task", "--source-revision", revision,
                        "--memory-revision", str(memory), "--out", out)

    def test_distinct_cli_processes_save_reload_and_duplicate(self):
        first = self.save()
        self.assertEqual(first.returncode, 0, first.stderr)
        saved = json.loads(first.stdout)
        self.assertEqual(saved["revision"], 1)
        loaded = self.load()
        self.assertEqual(loaded.returncode, 0, loaded.stderr)
        packet = json.loads((self.root / "resumed.json").read_text())
        self.assertEqual(packet["profile"], self.profile)
        self.assertEqual(packet["context_sha256"], saved["context_sha256"])
        self.assertEqual(packet["review_state"], "proposed")
        self.assertEqual(packet["sender_authentication"], "not_established")
        self.assertTrue(json.loads(self.save(1).stdout)["duplicate"])
        self.assertEqual(self.save(0).returncode, 1)

    def test_status_missing_ledger_fails_without_reporting_empty_queue(self):
        result = self.cli("status", database="mistyped.sqlite3")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(result.stdout, "")
        self.assertIn("existing ledger", json.loads(result.stderr)["error"])
        self.assertFalse((self.root / "mistyped.sqlite3").exists())
        with HandoffLedger(self.root / "empty.sqlite3"):
            pass
        existing = self.cli("status", database="empty.sqlite3")
        self.assertEqual(existing.returncode, 0, existing.stderr)
        self.assertEqual(json.loads(existing.stdout)["handoffs"], [])

    def test_cli_read_only_status_and_context_leave_database_unchanged(self):
        self.assertEqual(self.save().returncode, 0)
        before = self.db.read_bytes()
        base = [sys.executable, str(ROOT / "scripts/jarvis_network.py"), "--root", str(self.root),
                "--database", "ledger.sqlite3", "--read-only"]
        for args in (("status",), ("load-context", "--handoff", "cli-task", "--source-revision", REVISION,
                      "--memory-revision", "1", "--out", "read-only-context.json")):
            result = subprocess.run(base + list(args), capture_output=True, text=True, timeout=15, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(json.loads((self.root / "read-only-context.json").read_text())["profile"], self.profile)
        refused = subprocess.run(base + ["init-ledger"], capture_output=True, text=True, timeout=15, cwd=ROOT)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("read-only", json.loads(refused.stderr)["error"])
        self.assertEqual(self.db.read_bytes(), before)

    def test_cli_queue_report_is_read_only_and_rejects_missing_database(self):
        self.assertEqual(self.save().returncode, 0)
        before = self.db.read_bytes()
        result = self.cli("--read-only", "queue-report", "--project", "ai-jarvis")
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["execution_states"]["execution_blocked"], 1)
        self.assertEqual(packet["recorded_attempts"], 1)
        self.assertEqual(packet["visibility"], "owner_private")
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(self.cli("queue-report", "--project", "ai-jarvis", database="absent.sqlite3").returncode, 1)
        self.assertFalse((self.root / "absent.sqlite3").exists())

    def test_cli_checkpoint_capture_and_historical_read_preserve_current_holds(self):
        checksum = self.prepare_reviews()
        self.assertEqual(self.review_context(checksum).returncode, 0)
        args = ("--handoff", "cli-task", "--digest", checksum, "--source-revision", REVISION,
                "--memory-revision", "1")
        first = self.cli("capture-checkpoint", "--allow-schema-upgrade", *args)
        self.assertEqual(first.returncode, 0, first.stderr)
        receipt = json.loads(first.stdout)
        self.assertEqual(receipt["checkpoint_revision"], 1)
        self.assertFalse(receipt["duplicate"])
        self.assertTrue(json.loads(self.cli("capture-checkpoint", "--allow-schema-upgrade", *args).stdout)["duplicate"])
        original = deepcopy(self.profile)
        self.profile.update(schema_version=2, memory_revision=2,
            control=dict(state="cancelled", actor_id="local-owner", reason="Synthetic hold."))
        self.profile["execution"]["state"] = "outcome_unknown"
        self.write(self.profile)
        self.assertEqual(self.save(1).returncode, 0)
        before = self.db.read_bytes()
        loaded = self.cli("load-checkpoint", *args, "--checkpoint-revision", "1", "--out", "history.json")
        self.assertEqual(loaded.returncode, 0, loaded.stderr)
        packet = json.loads((self.root / "history.json").read_text())
        self.assertEqual(packet["profile"], original)
        self.assertEqual(packet["authority"], "historical_context_only_not_approval")
        self.assertEqual(packet["visibility"], "owner_private")
        self.assertFalse(packet["retry_authorized"])
        self.assertEqual(self.db.read_bytes(), before)
        with HandoffLedger(self.db, read_only=True) as ledger:
            self.assertEqual(ledger.db.execute("PRAGMA user_version").fetchone()[0], 3)
            current = ledger.load_context("cli-task", expected_source_revision=REVISION, expected_memory_revision=2)
            self.assertEqual(current["profile"], self.profile)
            self.assertEqual(current["review_state"], "proposed")
            with self.assertRaises(ValueError):
                ledger.export_context("cli-task", expected_sha256=current["context_sha256"],
                    expected_source_revision=REVISION, expected_memory_revision=2)

    def test_cli_checkpoint_capture_requires_opt_in_and_exact_existing_context(self):
        checksum = json.loads(self.save().stdout)["context_sha256"]
        args = ("--handoff", "cli-task", "--digest", checksum, "--source-revision", REVISION,
                "--memory-revision", "1")
        before = self.db.read_bytes()
        missing_flag = self.cli("capture-checkpoint", *args)
        self.assertNotEqual(missing_flag.returncode, 0)
        self.assertEqual(self.db.read_bytes(), before)
        readonly = self.cli("--read-only", "capture-checkpoint", "--allow-schema-upgrade", *args)
        self.assertEqual(readonly.returncode, 1)
        self.assertIn("read-only", json.loads(readonly.stderr)["error"])
        self.assertEqual(self.db.read_bytes(), before)
        for changed in (("--digest", "0" * 64), ("--source-revision", "0" * 40), ("--memory-revision", "2")):
            values = list(args)
            values[values.index(changed[0]) + 1] = changed[1]
            self.assertEqual(self.cli("capture-checkpoint", "--allow-schema-upgrade", *values).returncode, 1)
        with HandoffLedger(self.db, read_only=True) as ledger:
            self.assertEqual(ledger.db.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(ledger.load_context("cli-task", expected_source_revision=REVISION,
                expected_memory_revision=1)["profile"], self.profile)
        absent = self.cli("capture-checkpoint", "--allow-schema-upgrade", *args, database="missing/ledger.sqlite3")
        self.assertEqual(absent.returncode, 1)
        self.assertFalse((self.root / "missing").exists())

    def test_cli_historical_read_rejects_stale_revision_escape_and_overwrite(self):
        checksum = json.loads(self.save().stdout)["context_sha256"]
        args = ("--handoff", "cli-task", "--digest", checksum, "--source-revision", REVISION,
                "--memory-revision", "1", "--checkpoint-revision", "1")
        self.assertEqual(self.cli("capture-checkpoint", "--allow-schema-upgrade", *args[:-2]).returncode, 0)
        before = self.db.read_bytes()
        for flag, value in (("--digest", "0" * 64), ("--source-revision", "0" * 40),
                            ("--memory-revision", "2"), ("--checkpoint-revision", "2"), ("--checkpoint-revision", "0")):
            values = list(args)
            values[values.index(flag) + 1] = value
            result = self.cli("load-checkpoint", *values, "--out", "rejected-history.json")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertFalse((self.root / "rejected-history.json").exists())
        self.assertEqual(self.cli("load-checkpoint", *args, "--out", "../outside-history.json").returncode, 1)
        self.assertEqual(self.cli("--read-only", "load-checkpoint", *args, "--out", "private/history.json").returncode, 0)
        content = (self.root / "private/history.json").read_bytes()
        self.assertEqual(self.cli("load-checkpoint", *args, "--out", "private/history.json").returncode, 1)
        self.assertEqual((self.root / "private/history.json").read_bytes(), content)
        self.assertEqual(self.cli("load-checkpoint", *args, "--out", "absent-history.json",
            database="absent/ledger.sqlite3").returncode, 1)
        self.assertFalse((self.root / "absent").exists())
        self.assertFalse((self.root / "absent-history.json").exists())
        self.assertEqual(self.db.read_bytes(), before)

    def test_cli_checkpoint_index_does_not_upgrade_or_mutate_ledger(self):
        before = self.db.read_bytes()
        empty = self.cli("list-checkpoints", "--handoff", "cli-task")
        self.assertEqual(empty.returncode, 0, empty.stderr)
        self.assertEqual(json.loads(empty.stdout)["checkpoints"], [])
        self.assertEqual(self.db.read_bytes(), before)
        checksum = json.loads(self.save().stdout)["context_sha256"]
        self.assertEqual(self.cli("capture-checkpoint", "--allow-schema-upgrade", "--handoff", "cli-task",
            "--digest", checksum, "--source-revision", REVISION, "--memory-revision", "1").returncode, 0)
        before = self.db.read_bytes()
        result = self.cli("--read-only", "list-checkpoints", "--handoff", "cli-task")
        self.assertEqual(result.returncode, 0, result.stderr)
        index = json.loads(result.stdout)
        self.assertEqual(index["kind"], "jarvis.checkpoint_index")
        self.assertEqual(index["checkpoints"][0]["context_sha256"], checksum)
        self.assertNotIn("Synthetic", result.stdout)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(self.cli("list-checkpoints", "--handoff", "unknown-task").returncode, 1)
        self.assertEqual(self.cli("list-checkpoints", "--handoff", "cli-task", database="absent/ledger.sqlite3").returncode, 1)
        self.assertFalse((self.root / "absent").exists())

    def test_backup_preserves_opt_in_history_and_rejects_corrupt_checkpoint(self):
        checksum = json.loads(self.save().stdout)["context_sha256"]
        args = dict(expected_sha256=checksum, expected_source_revision=REVISION, expected_memory_revision=1)
        with HandoffLedger(self.db) as ledger:
            ledger.checkpoint_context("cli-task", **args)
        self.assertEqual(self.cli("backup-ledger", "--out", "history.sqlite3").returncode, 0)
        with HandoffLedger(self.root / "history.sqlite3", read_only=True) as restored:
            self.assertEqual(restored.db.execute("PRAGMA user_version").fetchone()[0], 3)
            self.assertEqual(restored.load_checkpoint("cli-task", 1, **args)["profile"], self.profile)
        with HandoffLedger(self.db) as ledger:
            ledger.db.execute("UPDATE context_checkpoints SET digest=?", ("0" * 64,))
            before = list(ledger.db.iterdump())
        rejected = self.cli("backup-ledger", "--out", "bad-history.sqlite3")
        self.assertEqual(rejected.returncode, 1)
        self.assertFalse((self.root / "bad-history.sqlite3").exists())
        with HandoffLedger(self.db) as ledger:
            self.assertEqual(list(ledger.db.iterdump()), before)

    def test_explicit_init_creates_empty_ledger_and_refuses_existing_state(self):
        result = self.cli("init-ledger", database="fresh/ledger.sqlite3")
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.root / "fresh/ledger.sqlite3"
        content = path.read_bytes()
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["mode"], "initialized_empty_ledger")
        self.assertEqual(receipt["ledger_sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(receipt["external_actions"], 0)
        status = self.cli("status", database="fresh/ledger.sqlite3")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["handoffs"], [])
        # Opening an existing ledger can update SQLite's header during schema setup.
        content = path.read_bytes()
        self.assertEqual(self.cli("init-ledger", database="fresh/ledger.sqlite3").returncode, 1)
        self.assertEqual(path.read_bytes(), content)
        before = self.db.read_bytes()
        self.assertEqual(self.cli("init-ledger").returncode, 1)
        self.assertEqual(self.db.read_bytes(), before)

    def test_explicit_init_refuses_escape_and_preserves_unrelated_files(self):
        self.assertEqual(self.cli("init-ledger", database="../outside.sqlite3").returncode, 1)
        path = self.root / "unrelated.sqlite3"
        path.write_bytes(b"unrelated content")
        result = self.cli("init-ledger", database="unrelated.sqlite3")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(path.read_bytes(), b"unrelated content")

    def test_context_and_review_commands_do_not_create_missing_recovery_ledger(self):
        for args in (("load-context", "--handoff", "cli-task", "--source-revision", REVISION,
                      "--memory-revision", "1", "--out", "absent-context.json"),
                     ("review", "--handoff", "cli-task", "--reviewer", "local-owner", "--digest", "0" * 64),
                     ("save-context", "--file", "context.json", "--expected-revision", "0")):
            with self.subTest(command=args[0]):
                result = self.cli(*args, database="missing/recovery.sqlite3")
                self.assertEqual(result.returncode, 1)
                self.assertIn("existing ledger", json.loads(result.stderr)["error"])
                self.assertFalse((self.root / "missing").exists())
                self.assertFalse((self.root / "absent-context.json").exists())

    def test_stage_still_creates_a_new_ledger_from_valid_packets(self):
        with HandoffLedger(self.db) as ledger:
            _, handoff = ledger._handoff("cli-task")
            manifest = ledger._swarm(handoff["swarm_id"])
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (self.root / "draft.json").write_text(json.dumps(handoff["draft"]), encoding="utf-8")
        result = self.cli("stage", "--manifest", "manifest.json", "--draft", "draft.json",
            "--assistant", handoff["assistant_id"], "--handoff", "new-task", database="new/ledger.sqlite3")
        self.assertEqual(result.returncode, 0, result.stderr)
        status = self.cli("status", database="new/ledger.sqlite3")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["handoffs"][0]["handoff_id"], "new-task")

    def test_revision_failures_leave_no_export_or_overwrite(self):
        self.assertEqual(self.save().returncode, 0)
        for revision, memory in (("f" * 40, 1), (REVISION, 2)):
            failed = self.load(revision=revision, memory=memory)
            self.assertEqual(failed.returncode, 1)
            self.assertFalse((self.root / "resumed.json").exists())
        self.assertEqual(self.load().returncode, 0)
        previous = (self.root / "resumed.json").read_bytes()
        self.assertEqual(self.load().returncode, 1)
        self.assertEqual((self.root / "resumed.json").read_bytes(), previous)

    def test_invalid_import_is_parsed_before_database_creation(self):
        for contents in ('{"kind":1,"kind":2}', '{broken', 'x' * 65537):
            (self.root / "context.json").write_text(contents)
            failed = self.cli("save-context", "--file", "context.json", "--expected-revision", "0",
                              database="must-not-exist.sqlite3")
            self.assertEqual(failed.returncode, 1)
            self.assertFalse((self.root / "must-not-exist.sqlite3").exists())

    def test_paths_cannot_escape_root(self):
        escaped = self.cli("save-context", "--file", "../outside.json", "--expected-revision", "0")
        self.assertEqual(escaped.returncode, 1)
        self.assertEqual(self.save().returncode, 0)
        self.assertEqual(self.load(out="../outside.json").returncode, 1)

    def test_stale_update_keeps_prior_checkpoint(self):
        self.assertEqual(self.save().returncode, 0)
        changed = deepcopy(self.profile)
        changed["execution"]["detail"] = "New synthetic checkpoint."
        self.write(changed)
        self.assertEqual(self.save(0).returncode, 1)
        self.assertEqual(self.load().returncode, 0)
        self.assertEqual(json.loads((self.root / "resumed.json").read_text())["profile"], self.profile)

    def test_unknown_outcome_and_private_visibility_survive_reload(self):
        self.profile["execution"]["state"] = "outcome_unknown"
        self.write(self.profile)
        self.assertEqual(self.save().returncode, 0)
        self.assertEqual(self.load().returncode, 0)
        stored = json.loads((self.root / "resumed.json").read_text())["profile"]
        self.assertEqual(stored["execution"], self.profile["execution"])
        self.assertEqual(stored["visibility"], "owner_private")


    def prepare_reviews(self):
        saved = self.save()
        self.assertEqual(saved.returncode, 0, saved.stderr)
        checksum = json.loads(saved.stdout)["context_sha256"]
        reviewed = self.cli("review", "--handoff", "cli-task", "--reviewer", "local-reviewer",
                            "--digest", self.profile["handoff_sha256"])
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        return checksum

    def review_context(self, checksum, reviewer="local-reviewer"):
        return self.cli("review-context", "--handoff", "cli-task", "--reviewer", reviewer,
                        "--digest", checksum)

    def export_context(self, checksum, out="envelope.json", revision=REVISION, memory=1):
        return self.cli("export-context", "--handoff", "cli-task", "--digest", checksum,
                        "--source-revision", revision, "--memory-revision", str(memory), "--out", out)

    def test_reviewed_envelope_keeps_original_binding_and_checkpoint(self):
        checksum = self.prepare_reviews()
        self.assertEqual(self.export_context(checksum).returncode, 1)
        reviewed = self.review_context(checksum)
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        self.assertEqual(json.loads(reviewed.stdout)["authority"], "local_record_only_not_identity_authentication")
        exported = self.export_context(checksum)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        packet = json.loads((self.root / "envelope.json").read_text())
        self.assertEqual(packet["handoff_sha256"], self.profile["handoff_sha256"])
        self.assertEqual(packet["context"], self.profile)
        self.assertEqual(packet["handoff"]["draft"]["target"], "codex")
        self.assertEqual(packet["external_actions"], 0)

    def test_context_review_cannot_replace_original_handoff_review(self):
        saved = self.save()
        checksum = json.loads(saved.stdout)["context_sha256"]
        self.assertEqual(self.review_context(checksum).returncode, 0)
        self.assertEqual(self.export_context(checksum).returncode, 1)
        self.assertFalse((self.root / "envelope.json").exists())

    def test_self_or_wrong_digest_review_cannot_open_export_gate(self):
        checksum = self.prepare_reviews()
        for value, reviewer in (("0" * 64, "local-reviewer"), (checksum, "cli-pilot.builder")):
            with self.subTest(reviewer=reviewer):
                self.assertEqual(self.review_context(value, reviewer).returncode, 1)
        self.assertEqual(self.export_context(checksum).returncode, 1)
        self.assertFalse((self.root / "envelope.json").exists())

    def test_edit_invalidates_context_review_across_cli_processes(self):
        checksum = self.prepare_reviews()
        self.assertEqual(self.review_context(checksum).returncode, 0)
        self.profile["execution"]["detail"] = "A new checkpoint needs review."
        self.write(self.profile)
        changed = self.save(1)
        new_digest = json.loads(changed.stdout)["context_sha256"]
        for value in (checksum, new_digest):
            self.assertEqual(self.export_context(value).returncode, 1)
        self.assertFalse((self.root / "envelope.json").exists())
        self.assertEqual(self.review_context(new_digest).returncode, 0)
        self.assertEqual(self.export_context(new_digest).returncode, 0)

    def test_envelope_revision_path_and_overwrite_checks(self):
        checksum = self.prepare_reviews()
        self.assertEqual(self.review_context(checksum).returncode, 0)
        for revision, memory in (("f" * 40, 1), (REVISION, 2)):
            self.assertEqual(self.export_context(checksum, revision=revision, memory=memory).returncode, 1)
            self.assertFalse((self.root / "envelope.json").exists())
        self.assertEqual(self.export_context(checksum, out="../outside-envelope.json").returncode, 1)
        self.assertEqual(self.export_context(checksum).returncode, 0)
        previous = (self.root / "envelope.json").read_bytes()
        self.assertEqual(self.export_context(checksum).returncode, 1)
        self.assertEqual((self.root / "envelope.json").read_bytes(), previous)

    def inspect(self, checksum, out="inspection.json", revision=REVISION, memory=1):
        return self.cli("inspect-recovery", "--handoff", "cli-task", "--digest", checksum,
                        "--source-revision", revision, "--memory-revision", str(memory), "--out", out)

    def test_recovery_inspection_in_new_process_preserves_hold_and_omits_private_text(self):
        self.profile["execution"]["state"] = "outcome_unknown"
        self.write(self.profile)
        checksum = json.loads(self.save().stdout)["context_sha256"]
        inspected = self.inspect(checksum)
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        packet = json.loads((self.root / "inspection.json").read_text())
        self.assertEqual(packet["kind"], "jarvis.recovery_inspection")
        self.assertEqual(packet["lineage"][0]["holds"], ["outcome_unknown"])
        self.assertFalse(packet["retry_authorized"])
        self.assertNotIn("https://", json.dumps(packet))
        self.assertEqual(self.load().returncode, 0)
        self.assertEqual(json.loads((self.root / "resumed.json").read_text())["profile"], self.profile)
        self.assertEqual(self.export_context(checksum).returncode, 1)

    def test_recovery_inspection_rejects_stale_inputs_escape_and_overwrite(self):
        checksum = json.loads(self.save().stdout)["context_sha256"]
        for value, revision, memory in (("0" * 64, REVISION, 1), (checksum, "f" * 40, 1), (checksum, REVISION, 2)):
            self.assertEqual(self.inspect(value, revision=revision, memory=memory).returncode, 1)
            self.assertFalse((self.root / "inspection.json").exists())
        self.assertEqual(self.inspect(checksum, out="../outside.json").returncode, 1)
        self.assertEqual(self.inspect(checksum).returncode, 0)
        original = (self.root / "inspection.json").read_bytes()
        self.assertEqual(self.inspect(checksum).returncode, 1)
        self.assertEqual((self.root / "inspection.json").read_bytes(), original)


    def test_check_recovery_accepts_current_snapshot_and_rejects_changed_review(self):
        checksum = json.loads(self.save().stdout)["context_sha256"]
        self.assertEqual(self.inspect(checksum).returncode, 0)
        packet = json.loads((self.root / "inspection.json").read_text())
        args = ("check-recovery", "--handoff", "cli-task", "--inspection-digest", packet["inspection_sha256"],
                "--digest", checksum, "--source-revision", REVISION, "--memory-revision", "1")
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["retry_authorized"])
        self.assertNotIn("lineage", json.loads(result.stdout))
        self.assertEqual(self.review_context(checksum).returncode, 0)
        stale = self.cli(*args)
        self.assertEqual(stale.returncode, 1)
        self.assertIn("inspection is stale", stale.stderr)


    def test_backup_restores_checkpoint_reviews_and_return_without_releasing_hold(self):
        checksum = self.prepare_reviews()
        self.assertEqual(self.review_context(checksum).returncode, 0)
        self.assertEqual(self.export_context(checksum).returncode, 0)
        self.profile["execution"]["state"] = "outcome_unknown"
        self.profile.update(schema_version=2, control=dict(state="cancelled", actor_id="local-owner", reason="Synthetic hold."))
        self.write(self.profile)
        checksum = json.loads(self.save(1).stdout)["context_sha256"]
        self.assertEqual(self.review_context(checksum).returncode, 0)
        with HandoffLedger(self.db) as ledger:
            ledger.import_return(dict(schema_version=1, kind="jarvis.return", return_id="backup-return",
                handoff_id="cli-task", handoff_sha256=self.profile["handoff_sha256"], source_provider="codex",
                text="Synthetic unverified return.", evidence_urls=[]))
        result = self.cli("backup-ledger", "--out", "backups/checkpoint.sqlite3")
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        backup = self.root / "backups/checkpoint.sqlite3"
        self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), receipt["backup_sha256"])
        self.assertEqual((receipt["handoff_count"], receipt["context_count"], receipt["return_count"]), (1, 1, 1))
        loaded = self.cli("load-context", "--handoff", "cli-task", "--source-revision", REVISION,
            "--memory-revision", "1", "--out", "backup-loaded.json", database="backups/checkpoint.sqlite3")
        self.assertEqual(loaded.returncode, 0, loaded.stderr)
        record = json.loads((self.root / "backup-loaded.json").read_text())
        self.assertEqual(record["profile"], self.profile)
        self.assertEqual(record["review_state"], "locally_reviewed")
        with HandoffLedger(backup) as restored:
            self.assertEqual(restored.status()["handoffs"][0]["state"], "returned_unverified")
            with self.assertRaises(ValueError):
                restored.export("cli-task", expected_sha256=self.profile["handoff_sha256"])
        self.profile["execution"]["detail"] = "Later source checkpoint."
        self.write(self.profile)
        self.assertEqual(self.save(2).returncode, 0)
        with HandoffLedger(backup) as restored:
            self.assertEqual(restored.load_context("cli-task", expected_source_revision=REVISION,
                expected_memory_revision=1)["revision"], 2)

    def test_backup_reads_committed_wal_records_and_leaves_source_unchanged(self):
        with HandoffLedger(self.db) as ledger:
            ledger.db.execute("PRAGMA journal_mode=WAL")
            ledger.save_context(self.profile, expected_revision=0)
            before = list(ledger.db.iterdump())
            result = self.cli("backup-ledger", "--out", "wal-backup.sqlite3")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(ledger.db.iterdump()), before)
        with HandoffLedger(self.root / "wal-backup.sqlite3") as restored:
            self.assertEqual(restored.load_context("cli-task", expected_source_revision=REVISION,
                expected_memory_revision=1)["profile"], self.profile)

    def test_backup_refuses_missing_source_escape_overwrite_and_corrupt_context(self):
        self.assertEqual(self.cli("backup-ledger", "--out", "absent.sqlite3", database="missing.sqlite3").returncode, 1)
        self.assertFalse((self.root / "missing.sqlite3").exists())
        self.assertEqual(self.cli("backup-ledger", "--out", "../outside.sqlite3").returncode, 1)
        self.assertEqual(self.save().returncode, 0)
        self.assertEqual(self.cli("backup-ledger", "--out", "existing.sqlite3").returncode, 0)
        before = (self.root / "existing.sqlite3").read_bytes()
        self.assertEqual(self.cli("backup-ledger", "--out", "existing.sqlite3").returncode, 1)
        self.assertEqual((self.root / "existing.sqlite3").read_bytes(), before)
        with HandoffLedger(self.db) as ledger:
            ledger.db.execute("UPDATE handoff_contexts SET body='{}'")
        self.assertEqual(self.cli("backup-ledger", "--out", "invalid.sqlite3").returncode, 1)
        self.assertFalse((self.root / "invalid.sqlite3").exists())
        self.assertFalse(list(self.root.glob(".jarvis-backup-*")))
        with HandoffLedger(self.db) as ledger:
            ledger.db.execute("DROP TABLE handoff_contexts")
            ledger.db.execute("PRAGMA user_version=1")
        legacy = self.db.read_bytes()
        self.assertEqual(self.cli("backup-ledger", "--out", "legacy-copy.sqlite3").returncode, 1)
        self.assertFalse((self.root / "legacy-copy.sqlite3").exists())
        self.assertEqual(self.db.read_bytes(), legacy)

    def test_backup_rejects_corrupt_swarm_configuration_before_publication(self):
        with HandoffLedger(self.db) as ledger:
            row = ledger.db.execute("SELECT * FROM swarms").fetchone()
            manifest = json.loads(row["body"])
            manifest["assistants"][0]["max_handoffs"] = 99
            ledger.db.execute("UPDATE swarms SET body=?", (json.dumps(manifest),))
            before = list(ledger.db.iterdump())
        result = self.cli("backup-ledger", "--out", "bad-swarm.sqlite3")
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.root / "bad-swarm.sqlite3").exists())
        self.assertFalse(list(self.root.glob(".jarvis-backup-*")))
        with HandoffLedger(self.db) as ledger:
            self.assertEqual(list(ledger.db.iterdump()), before)

    def test_backup_rejects_swarm_row_digest_mismatch(self):
        with HandoffLedger(self.db) as ledger:
            ledger.db.execute("UPDATE swarms SET digest=?", ("0" * 64,))
        result = self.cli("backup-ledger", "--out", "bad-binding.sqlite3")
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.root / "bad-binding.sqlite3").exists())

    def test_backup_rejects_rehashed_nonmanual_handoff_without_mutating_source(self):
        with HandoffLedger(self.db) as ledger:
            _, body = ledger._handoff("cli-task")
            body["mode"] = "automatic_dispatch"
            ledger.db.execute("UPDATE handoffs SET body=?,digest=? WHERE id=?",
                (json.dumps(body), digest(body), "cli-task"))
            before = list(ledger.db.iterdump())
        result = self.cli("backup-ledger", "--out", "bad-contract.sqlite3")
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.root / "bad-contract.sqlite3").exists())
        with HandoffLedger(self.db) as ledger:
            self.assertEqual(list(ledger.db.iterdump()), before)

    def test_backup_rejects_rehashed_handoff_outside_registered_scope(self):
        with HandoffLedger(self.db) as ledger:
            row, handoff = ledger._handoff("cli-task")
            handoff["draft"]["target"] = "github"
            ledger.db.execute("UPDATE handoffs SET body=?,digest=? WHERE id=?",
                (json.dumps(handoff), digest(handoff), "cli-task"))
        result = self.cli("backup-ledger", "--out", "bad-scope.sqlite3")
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.root / "bad-scope.sqlite3").exists())

    def test_cli_prepares_private_reconciliation_without_releasing_or_overwriting(self):
        self.profile["execution"]["state"] = "outcome_unknown"
        self.profile["evidence_refs"] = [dict(url="https://example.invalid/evidence", revision=1, visibility="owner_private")]
        self.write(self.profile)
        checksum = json.loads(self.save().stdout)["context_sha256"]
        self.assertEqual(self.inspect(checksum).returncode, 0)
        inspected = json.loads((self.root / "inspection.json").read_text())
        args = ("prepare-reconciliation", "--handoff", "cli-task", "--digest", checksum,
            "--inspection-digest", inspected["inspection_sha256"], "--source-revision", REVISION,
            "--memory-revision", "1", "--out", "proposal.json")
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        content = (self.root / "proposal.json").read_bytes()
        packet = json.loads(content)
        self.assertEqual(packet["kind"], "jarvis.reconciliation_proposal")
        self.assertEqual(packet["evidence_verification"], "not_established")
        self.assertFalse(packet["retry_authorized"])
        self.assertEqual(self.cli(*args).returncode, 1)
        self.assertEqual((self.root / "proposal.json").read_bytes(), content)
        self.assertEqual(self.export_context(checksum).returncode, 1)

    def test_destination_context_survives_cli_backup_and_restoration_read(self):
        self.profile.update(schema_version=3, destination_id="repo-one",
            control=dict(state="paused", actor_id="local-owner", reason="Synthetic destination checkpoint."))
        self.write(self.profile)
        self.assertEqual(self.save().returncode, 0)
        self.assertEqual(self.cli("backup-ledger", "--out", "destination.sqlite3").returncode, 0)
        result = self.cli("load-context", "--handoff", "cli-task", "--source-revision", REVISION,
            "--memory-revision", "1", "--out", "destination.json", database="destination.sqlite3")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.root / "destination.json").read_text())["profile"], self.profile)

    def test_cli_destination_reconciliation_is_versioned_and_keeps_hold(self):
        self.profile.update(schema_version=3, destination_id="repo-one",
            control=dict(state="paused", actor_id="local-owner", reason="Synthetic reconciliation."))
        self.profile["execution"]["state"] = "outcome_unknown"
        self.profile["evidence_refs"] = [dict(url="https://example.invalid/evidence", revision=1, visibility="owner_private")]
        self.write(self.profile)
        checksum = json.loads(self.save().stdout)["context_sha256"]
        self.assertEqual(self.inspect(checksum).returncode, 0)
        inspected = json.loads((self.root / "inspection.json").read_text())
        args = ("prepare-reconciliation", "--handoff", "cli-task", "--digest", checksum,
            "--inspection-digest", inspected["inspection_sha256"], "--source-revision", REVISION,
            "--memory-revision", "1", "--out", "bound-proposal.json")
        with HandoffLedger(self.db) as ledger:
            before = list(ledger.db.iterdump())
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        content = (self.root / "bound-proposal.json").read_bytes()
        packet = json.loads(content)
        self.assertEqual(packet["schema_version"], 2)
        self.assertEqual(packet["destination_id"], "repo-one")
        self.assertEqual(packet["context_sha256"], checksum)
        self.assertEqual(packet["proposed_resolution"], "retain_hold")
        self.assertFalse(packet["retry_authorized"])
        self.assertEqual(self.cli(*args).returncode, 1)
        self.assertEqual((self.root / "bound-proposal.json").read_bytes(), content)
        self.assertEqual(self.export_context(checksum).returncode, 1)
        with HandoffLedger(self.db) as ledger:
            self.assertEqual(list(ledger.db.iterdump()), before)

    def test_destination_requires_context_export_instead_of_legacy_cli_packet(self):
        self.profile.update(schema_version=3, destination_id="repo-one",
            control=dict(state="active", actor_id="local-owner", reason="Synthetic exact destination."))
        self.write(self.profile)
        checksum = self.prepare_reviews()
        self.assertEqual(self.review_context(checksum).returncode, 0)
        legacy = self.cli("export", "--handoff", "cli-task", "--digest", self.profile["handoff_sha256"],
                          "--out", "legacy.json")
        self.assertEqual(legacy.returncode, 1)
        self.assertFalse((self.root / "legacy.json").exists())
        self.assertEqual(self.export_context(checksum).returncode, 0)
        packet = json.loads((self.root / "envelope.json").read_text())
        self.assertEqual(packet["context"]["destination_id"], "repo-one")

    def test_destination_status_cli_reads_existing_private_metadata_only(self):
        args = ("destination-status", "--project", "ai-jarvis", "--platform", "codex", "--destination", "repo-one")
        missing = self.cli(*args, database="missing.sqlite3")
        self.assertEqual(missing.returncode, 1)
        self.assertFalse((self.root / "missing.sqlite3").exists())
        self.profile.update(schema_version=3, destination_id="repo-one",
            control=dict(state="paused", actor_id="local-owner", reason="Synthetic private checkpoint."))
        self.write(self.profile)
        saved = json.loads(self.save().stdout)
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["records"][0]["context_sha256"], saved["context_sha256"])
        self.assertEqual(packet["records"][0]["control_state"], "paused")
        self.assertNotIn("https://", result.stdout)
        self.assertFalse(packet["dispatch_authorized"])

    def test_cli_binding_checks_exact_retained_response_bytes(self):
        self.profile.update(schema_version=3, destination_id="repo-one",
            control=dict(state="paused", actor_id="local-owner", reason="Synthetic retained response."))
        self.write(self.profile)
        checksum = json.loads(self.save().stdout)["context_sha256"]
        raw = b'{"sha":"synthetic"}\n'
        (self.root / "response.bin").write_bytes(raw)
        observation = read_observation("codex", observed_at=datetime.now(timezone.utc).isoformat(),
            evidence_url="https://example.invalid/read", response_sha256=hashlib.sha256(raw).hexdigest(),
            scope="Synthetic fixture", source_revision=REVISION)
        (self.root / "observation.json").write_text(json.dumps(observation))
        args = ("--handoff", "cli-task", "--file", "observation.json", "--digest", checksum,
            "--source-revision", REVISION, "--memory-revision", "1")
        before = self.db.read_bytes()
        result = self.cli("--read-only", "bind-observation", *args, "--response-file", "response.bin", "--out", "checked.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        legacy = self.cli("--read-only", "bind-observation", *args, "--out", "legacy-observation.json")
        self.assertEqual(legacy.returncode, 0, legacy.stderr)
        self.assertEqual((self.root / "checked.json").read_bytes(), (self.root / "legacy-observation.json").read_bytes())
        for content in (raw.rstrip(), b'x' * 65537):
            (self.root / "response.bin").write_bytes(content)
            refused = self.cli("bind-observation", *args, "--response-file", "response.bin", "--out", "rejected.json")
            self.assertEqual(refused.returncode, 1, refused.stderr)
            self.assertFalse((self.root / "rejected.json").exists())
        for name in ("missing.bin", "../outside.bin"):
            self.assertEqual(self.cli("bind-observation", *args, "--response-file", name, "--out", "rejected.json").returncode, 1)
        self.assertEqual(self.db.read_bytes(), before)

    def test_cli_dot_repository_commit_check_retains_paused_private_binding(self):
        database = "github.sqlite3"
        with HandoffLedger(self.root / database) as ledger:
            manifest = build_swarm("ai-jarvis", ["github"], swarm_id="github-pilot", source_revision=REVISION)
            staged = ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
                target="github", text="Synthetic dot repository check."), manifest,
                assistant_id="github-pilot.builder", handoff_id="github-task")
        self.profile.update(schema_version=3, handoff_id="github-task", mission_id="github-task",
            handoff_sha256=staged["handoff_sha256"], asset_id="github-pilot.builder", platform="github",
            destination_id="repo-dot", control=dict(state="paused", actor_id="local-owner", reason="Synthetic check."))
        self.write(self.profile)
        saved = self.cli("save-context", "--file", "context.json", "--expected-revision", "0", database=database)
        self.assertEqual(saved.returncode, 0, saved.stderr)
        checksum = json.loads(saved.stdout)["context_sha256"]
        url = f"https://api.github.com/repos/owner/.github/git/commits/{REVISION}"
        raw = json.dumps(dict(sha=REVISION, url=url)).encode()
        (self.root / "response.bin").write_bytes(raw)
        observation = read_observation("github", observed_at=datetime.now(timezone.utc).isoformat(),
            evidence_url=url, response_sha256=hashlib.sha256(raw).hexdigest(),
            scope="Synthetic dot repository", source_revision=REVISION)
        (self.root / "observation.json").write_text(json.dumps(observation))
        before = (self.root / database).read_bytes()
        result = self.cli("--read-only", "bind-observation", "--handoff", "github-task",
            "--file", "observation.json", "--digest", checksum, "--source-revision", REVISION,
            "--memory-revision", "1", "--response-file", "response.bin",
            "--github-commit-repository", "owner/.github", "--out", "dot-checked.json", database=database)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.root / "dot-checked.json").read_text())
        self.assertEqual(receipt["observation"], observation)
        self.assertFalse(receipt["dispatch_authorized"])
        self.assertEqual((self.root / database).read_bytes(), before)
        with HandoffLedger(self.root / database, read_only=True) as ledger:
            current = ledger.load_context("github-task", expected_source_revision=REVISION, expected_memory_revision=1)
        self.assertEqual(current["profile"], self.profile)

    def test_cli_commit_identity_option_requires_response_before_ledger_open(self):
        (self.root / "observation.json").write_text('{}')
        before = self.db.read_bytes()
        result = self.cli("bind-observation", "--handoff", "cli-task", "--file", "observation.json",
            "--digest", "0" * 64, "--source-revision", REVISION, "--memory-revision", "1",
            "--github-commit-repository", "lippytm/jarvis-nexus-core", "--out", "missing-response.json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("requires --response-file", result.stderr)
        self.assertFalse((self.root / "missing-response.json").exists())
        self.assertEqual(self.db.read_bytes(), before)

    def configured_fixture(self):
        with HandoffLedger(self.db) as ledger:
            manifest = build_swarm("ai-jarvis", ["github"], swarm_id="mapping-pilot", source_revision=REVISION)
            staged = ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
                target="github", text="Synthetic mapping CLI fixture."), manifest,
                assistant_id="mapping-pilot.builder", handoff_id="mapping-task")
            profile = deepcopy(self.profile)
            profile.update(schema_version=3, handoff_id="mapping-task", mission_id="mapping-task",
                handoff_sha256=staged["handoff_sha256"], asset_id="mapping-pilot.builder", platform="github",
                destination_id="repo-one", control=dict(state="paused", actor_id="local-owner", reason="Keep blocked."))
            saved = ledger.save_context(profile, expected_revision=0)
        url = f"https://api.github.com/repos/owner/.github/git/commits/{REVISION}"
        raw = json.dumps(dict(sha=REVISION, url=url)).encode()
        (self.root / "response.bin").write_bytes(raw)
        observation = read_observation("github", observed_at=datetime.now(timezone.utc).isoformat(), evidence_url=url,
            response_sha256=hashlib.sha256(raw).hexdigest(), scope="Synthetic configured read", source_revision=REVISION)
        (self.root / "observation.json").write_text(json.dumps(observation))
        registry = dict(schema_version=1, kind="jarvis.destination_registry", registry_id="local-fixture",
            revision=1, source_revision=REVISION, configuration_version="github-read.v1", visibility="owner_private",
            entries=[dict(project_id="ai-jarvis", platform="github", destination_id="repo-one",
                          resource_id="owner/.github", allowed_actions=["read"])])
        (self.root / "registry.json").write_text(json.dumps(registry))
        args = ["bind-observation", "--handoff", "mapping-task", "--file", "observation.json",
            "--response-file", "response.bin", "--registry-file", "registry.json", "--registry-digest", digest(registry),
            "--registry-revision", "1", "--digest", saved["context_sha256"], "--source-revision", REVISION,
            "--memory-revision", "1", "--out", "configured.json"]
        return args, registry, profile

    def test_cli_configured_read_round_trip_preserves_blocked_pause_and_refuses_overwrite(self):
        args, registry, profile = self.configured_fixture()
        before = self.db.read_bytes()
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.root / "configured.json"
        raw = path.read_bytes()
        envelope = json.loads(raw)
        self.assertEqual(envelope["kind"], "jarvis.configured_destination_observation")
        self.assertEqual(envelope["registry_binding"]["entry"], registry["entries"][0])
        self.assertFalse(envelope["dispatch_authorized"])
        self.assertEqual(envelope["visibility"], "owner_private")
        self.assertEqual(self.cli(*args).returncode, 1)
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(self.db.read_bytes(), before)
        with HandoffLedger(self.db, read_only=True) as ledger:
            loaded = ledger.load_context("mapping-task", expected_source_revision=REVISION, expected_memory_revision=1)
        self.assertEqual(loaded["profile"], profile)
        self.assertEqual(loaded["review_state"], "proposed")

    def test_cli_registry_preflight_rejects_partial_stale_or_ambiguous_options_before_open(self):
        args, _, _ = self.configured_fixture()
        from scripts.jarvis_network import main
        cases = []
        for option in ("--registry-file", "--registry-digest", "--registry-revision", "--response-file"):
            changed = list(args)
            start = changed.index(option)
            del changed[start:start + 2]
            cases.append(changed)
        for option, value in (("--registry-digest", "0" * 64), ("--registry-revision", "2")):
            changed = list(args)
            changed[changed.index(option) + 1] = value
            cases.append(changed)
        cases.append(args + ["--github-commit-repository", "owner/.github"])
        before = self.db.read_bytes()
        for changed in cases:
            with self.subTest(args=changed), patch("scripts.jarvis_network.HandoffLedger") as opened:
                self.assertEqual(main(["--root", str(self.root), "--database", "ledger.sqlite3", *changed]), 1)
                opened.assert_not_called()
        self.assertFalse((self.root / "configured.json").exists())
        self.assertEqual(self.db.read_bytes(), before)

    def test_cli_registry_wrong_resource_and_forced_read_only_refuse_changes(self):
        args, registry, _ = self.configured_fixture()
        changed = deepcopy(registry)
        changed["entries"][0]["resource_id"] = "other/repository"
        (self.root / "registry.json").write_text(json.dumps(changed))
        args[args.index("--registry-digest") + 1] = digest(changed)
        before = self.db.read_bytes()
        self.assertEqual(self.cli(*args).returncode, 1)
        self.assertEqual(self.db.read_bytes(), before)
        (self.root / "registry.json").write_text(json.dumps(registry))
        args[args.index("--registry-digest") + 1] = digest(registry)
        with HandoffLedger(self.db) as ledger:
            ledger.db.execute("DROP TABLE handoff_contexts")
            ledger.db.execute("PRAGMA user_version=1")
        before = self.db.read_bytes()
        result = self.cli(*args)
        self.assertEqual(result.returncode, 1)
        self.assertIn("read-only inspection requires", result.stderr)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertFalse((self.root / "configured.json").exists())

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'FIFO probe requires POSIX')
    def test_cli_response_file_refuses_fifo_without_blocking(self):
        (self.root / "observation.json").write_text('{}')
        os.mkfifo(self.root / "response.pipe")
        result = self.cli("bind-observation", "--handoff", "cli-task", "--file", "observation.json",
            "--digest", "0" * 64, "--source-revision", REVISION, "--memory-revision", "1",
            "--response-file", "response.pipe", "--out", "fifo.json")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse((self.root / "fifo.json").exists())

    def test_cli_binds_observation_without_overwriting_private_output(self):
        self.profile.update(schema_version=3, destination_id="repo-one",
            control=dict(state="paused", actor_id="local-owner", reason="Synthetic local read."))
        self.write(self.profile)
        checksum = json.loads(self.save().stdout)["context_sha256"]
        observation = read_observation("codex", observed_at=datetime.now(timezone.utc).isoformat(),
            evidence_url="https://example.invalid/read", response_sha256="a" * 64,
            scope="Synthetic CLI read", source_revision=REVISION)
        (self.root / "observation.json").write_text(json.dumps(observation))
        args = ("bind-observation", "--handoff", "cli-task", "--file", "observation.json", "--digest", checksum,
                "--source-revision", REVISION, "--memory-revision", "1", "--out", "bound-read.json")
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        content = (self.root / "bound-read.json").read_bytes()
        self.assertEqual(json.loads(content)["observation"], observation)
        self.assertFalse(json.loads(content)["dispatch_authorized"])
        self.assertEqual(self.cli(*args).returncode, 1)
        self.assertEqual((self.root / "bound-read.json").read_bytes(), content)

    def test_backup_publish_race_preserves_winner_and_cleans_temporary_file(self):
        target = self.root / "race.sqlite3"
        def competing_link(*_):
            target.write_bytes(b"Other writer's existing evidence")
            raise FileExistsError()
        with HandoffLedger(self.db) as ledger, patch("scripts.jarvis_network.os.link", side_effect=competing_link):
            with self.assertRaises(FileExistsError):
                _backup(ledger.db, target)
        self.assertEqual(target.read_bytes(), b"Other writer's existing evidence")
        self.assertFalse(list(self.root.glob(".jarvis-backup-*")))


if __name__ == "__main__":
    unittest.main()
