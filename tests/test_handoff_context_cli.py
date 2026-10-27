"""Actual CLI subprocesses against synthetic private checkpoint fixtures."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from control_tower.handoffs import HandoffLedger
from control_tower.swarm_factory import build_swarm

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


if __name__ == "__main__":
    unittest.main()
