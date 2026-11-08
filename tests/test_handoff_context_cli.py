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
from control_tower.network_contract import digest, TARGETS
from control_tower.connections import read_observation
from scripts.jarvis_network import _backup, _set_context_control

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

    def registry_input(self):
        record = dict(schema_version=1, kind="jarvis.destination_registry", registry_id="private-registry",
            revision=1, source_revision=REVISION, configuration_version="read.v1", visibility="owner_private",
            entries=[dict(project_id="ai-jarvis", platform=target, destination_id="private-destination",
                resource_id="owner/private-repository" if target == "github" else "opaque-private-resource",
                allowed_actions=["read"]) for target in sorted(TARGETS)])
        path = self.root / "registry.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        return ["inspect-registry", "--file", "registry.json", "--digest", digest(record),
                "--registry-revision", "1", "--source-revision", REVISION]

    def test_observation_revision_cli_rejects_stale_selection_before_output(self):
        from datetime import datetime, timezone
        checksum = self.controlled(execution="outcome_unknown")
        original = deepcopy(self.profile)
        self.profile["execution"]["detail"] = "Synthetic intervening context."
        self.write(self.profile)
        self.assertEqual(self.save(1).returncode, 0)
        self.profile = original
        self.write(original)
        self.assertEqual(self.save(2).returncode, 0)
        observation = read_observation("codex", observed_at=datetime.now(timezone.utc).isoformat(),
            evidence_url="https://example.invalid/read", response_sha256="a" * 64,
            scope="Synthetic read", source_revision=REVISION)
        (self.root / "observation.json").write_text(json.dumps(observation))
        before = self.db.read_bytes()
        args = ("--read-only", "bind-observation", "--handoff", "cli-task", "--file", "observation.json",
            "--digest", checksum, "--source-revision", REVISION, "--memory-revision", "1")
        for revision in ("1", "4", "0"):
            rejected = self.cli(*args, "--context-revision", revision, "--out", "rejected/read.json")
            self.assertEqual(rejected.returncode, 1, rejected.stderr)
            self.assertIn("context retrieval revision", rejected.stderr)
            self.assertFalse((self.root / "rejected").exists())
            self.assertEqual(self.db.read_bytes(), before)
        selected = self.cli(*args, "--context-revision", "3", "--out", "private/read.json")
        self.assertEqual(selected.returncode, 0, selected.stderr)
        output = self.root / "private/read.json"
        content = output.read_bytes()
        self.assertEqual(json.loads(content)["context_revision"], 3)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.cli(*args, "--context-revision", "3", "--out", "private/read.json").returncode, 1)
        self.assertEqual(output.read_bytes(), content)
        self.assertEqual(self.cli(*args, "--out", "default.json").returncode, 0)
        self.assertEqual((self.root / "default.json").read_bytes(), content)
        self.assertEqual(self.db.read_bytes(), before)

    def test_registry_platform_selection_is_versioned_private_and_guarded(self):
        from control_tower.connections import inspect_destination_registry
        args = self.registry_input()
        path = self.root / "registry.json"
        registry = json.loads(path.read_text())
        guards = dict(expected_sha256=digest(registry), expected_revision=1,
                      expected_source_revision=REVISION)
        before = path.read_bytes(), self.db.read_bytes()
        for target in sorted(TARGETS):
            selected = inspect_destination_registry(registry, platform=target, **guards)
            self.assertEqual(selected["schema_version"], 3)
            self.assertEqual(selected["platform"], target)
            self.assertEqual(selected["platform_counts"], {target: 1})
            self.assertEqual(selected["entry_count"], 1)
            self.assertEqual(selected["acceptance_state"], "proposed_unverified")
            self.assertFalse(selected["dispatch_authorized"])
            self.assertEqual(selected["receipt_sha256"], digest(
                {k: v for k, v in selected.items() if k != "receipt_sha256"}))
            self.assertNotIn("opaque-private-resource", json.dumps(selected))
        legacy = inspect_destination_registry(registry, **guards)
        self.assertEqual(legacy, inspect_destination_registry(registry, platform=None, **guards))
        self.assertEqual(legacy["schema_version"], 1)
        self.assertEqual(inspect_destination_registry(registry, project_id="ai-jarvis", **guards)["schema_version"], 2)
        for target in ("unknown", "", True, 1):
            with self.assertRaises(ValueError):
                inspect_destination_registry(registry, platform=target, **guards)
        changed = deepcopy(registry)
        changed["entries"][-1]["resource_id"] = "changed-private-neighbor"
        with self.assertRaises(ValueError):
            inspect_destination_registry(changed, platform="codex", **guards)
        changed["entries"][-1]["allowed_actions"] = ["write"]
        with self.assertRaises(ValueError):
            inspect_destination_registry(changed, platform="codex",
                **{**guards, "expected_sha256": digest(changed)})
        selected = self.cli(*args, "--platform", "codex", "--project", "ai-jarvis",
                            "--out", "private/codex.json", database="absent/ledger.sqlite3")
        self.assertEqual(selected.returncode, 0, selected.stderr)
        output = self.root / "private/codex.json"
        content = output.read_bytes()
        record = json.loads(content)
        self.assertEqual(record["platform_counts"], {"codex": 1})
        self.assertEqual(record["project_id"], "ai-jarvis")
        self.assertEqual(record["schema_version"], 3)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.cli(*args, "--platform", "codex", "--out", "private/codex.json").returncode, 1)
        self.assertEqual(output.read_bytes(), content)
        rejected = self.cli(*args, "--platform", "unknown", "--out", "rejected/summary.json")
        self.assertEqual(rejected.returncode, 1)
        self.assertFalse((self.root / "rejected").exists())
        self.assertFalse((self.root / "absent").exists())
        self.assertEqual((path.read_bytes(), self.db.read_bytes()), before)

    def test_registry_combined_scope_intersects_mixed_projects_and_platforms(self):
        from control_tower.connections import inspect_destination_registry
        from control_tower.network_contract import PROJECTS
        self.registry_input()
        path = self.root / "registry.json"
        registry = json.loads(path.read_text())
        other, empty = sorted(p for p in PROJECTS if p != "ai-jarvis")[:2]
        # Different counts expose accidental union, project-only or platform-only selection.
        registry["entries"] = [dict(project_id=project, platform=target,
            destination_id=f"private-{index}", resource_id="private-resource-" + str(index),
            allowed_actions=["read"]) for index, (project, target) in enumerate([
                ("ai-jarvis", "codex"), ("ai-jarvis", "codex"), ("ai-jarvis", "gemini"),
                (other, "codex"), (other, "gemini"), (other, "gemini")])]
        path.write_text(json.dumps(registry))
        before = path.read_bytes(), self.db.read_bytes()
        guards = dict(expected_sha256=digest(registry), expected_revision=1,
                      expected_source_revision=REVISION)
        default = inspect_destination_registry(registry, **guards)
        self.assertEqual(default["entry_count"], 6)
        self.assertEqual(default["platform_counts"], {"codex": 3, "gemini": 3})
        receipts = set()
        for index, (project, target, count) in enumerate([
                ("ai-jarvis", "codex", 2), ("ai-jarvis", "gemini", 1),
                (other, "codex", 1), (other, "gemini", 2), (empty, "codex", 0)]):
            with self.subTest(project=project, platform=target):
                expected = inspect_destination_registry(registry, project_id=project, platform=target, **guards)
                self.assertEqual(expected["entry_count"], count)
                self.assertEqual(expected["platform_counts"], {target: count} if count else {})
                self.assertEqual(expected["project_id"], project)
                self.assertEqual(expected["platform"], target)
                self.assertEqual(expected["schema_version"], 3)
                self.assertEqual(expected["visibility"], "owner_private")
                self.assertFalse(expected["dispatch_authorized"])
                receipts.add(expected["receipt_sha256"])
                args = ("--read-only", "inspect-registry", "--file", "registry.json",
                    "--digest", guards["expected_sha256"], "--registry-revision", "1",
                    "--source-revision", REVISION, "--project", project, "--platform", target)
                first = self.cli(*args, database="absent/ledger.sqlite3")
                second = self.cli(*args, database="absent/ledger.sqlite3")
                self.assertEqual(first.returncode, 0, first.stderr)
                self.assertEqual(second.returncode, 0, second.stderr)
                self.assertEqual(first.stdout, second.stdout)
                self.assertEqual(json.loads(first.stdout), expected)
                self.assertNotIn("private-resource-", first.stdout)
                self.assertNotIn("private-0", first.stdout)
        self.assertEqual(len(receipts), 5)
        self.assertEqual(inspect_destination_registry(registry, **guards), default)
        self.assertFalse((self.root / "absent").exists())
        self.assertEqual((path.read_bytes(), self.db.read_bytes()), before)

    def test_registry_inspection_receipt_guard_pins_scope_before_output(self):
        from control_tower.connections import inspect_destination_registry
        args = self.registry_input()
        path = self.root / "registry.json"
        registry = json.loads(path.read_text())
        guards = dict(expected_sha256=digest(registry), expected_revision=1,
                      expected_source_revision=REVISION)
        selected = inspect_destination_registry(registry, platform="codex", **guards)
        checksum = selected["receipt_sha256"]
        before = path.read_bytes(), self.db.read_bytes()
        self.assertEqual(inspect_destination_registry(registry, platform="codex",
            expected_receipt_sha256=checksum, **guards), selected)
        for scope in ({}, {"platform": "gemini"}, {"platform": "codex", "project_id": "ai-jarvis"}):
            with self.subTest(scope=scope), self.assertRaisesRegex(ValueError, "inspection receipt"):
                inspect_destination_registry(registry, expected_receipt_sha256=checksum, **scope, **guards)
        with self.assertRaises(ValueError):
            inspect_destination_registry(registry, expected_receipt_sha256="invalid", **guards)
        output = self.root / "private/existing.json"
        output.parent.mkdir()
        output.write_bytes(b"KEEP")
        for scope in ((), ("--platform", "gemini"), ("--platform", "codex", "--project", "ai-jarvis")):
            for destination in ("private/existing.json", "rejected/summary.json"):
                rejected = self.cli(*args, *scope, "--expected-receipt-digest", checksum,
                    "--out", destination, database="absent/ledger.sqlite3")
                self.assertEqual(rejected.returncode, 1, rejected.stderr)
                # Existing-file preflight may reject before registry inspection.
                self.assertIn("output already exists" if destination == "private/existing.json"
                              else "inspection receipt", rejected.stderr)
                self.assertEqual(rejected.stdout, "")
                self.assertEqual(output.read_bytes(), b"KEEP")
                self.assertFalse((self.root / "rejected").exists())
        valid_args = (*args, "--platform", "codex", "--expected-receipt-digest", checksum)
        first = self.cli(*valid_args, database="absent/ledger.sqlite3")
        second = self.cli(*valid_args, database="absent/ledger.sqlite3")
        legacy = self.cli(*args, "--platform", "codex", database="absent/ledger.sqlite3")
        for result in (first, second, legacy):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), selected)
        self.assertEqual(first.stdout, legacy.stdout)
        self.assertEqual(first.stdout, second.stdout)
        self.assertFalse((self.root / "absent").exists())
        self.assertEqual((path.read_bytes(), self.db.read_bytes()), before)

    def test_guarded_registry_files_round_trip_all_existing_receipt_versions(self):
        args = self.registry_input()
        before = (self.root / "registry.json").read_bytes(), self.db.read_bytes()
        scopes = [((), 1), (("--project", "ai-jarvis"), 2),
                  (("--platform", "codex"), 3),
                  (("--project", "ai-jarvis", "--platform", "codex"), 3)]
        for index, (scope, version) in enumerate(scopes):
            with self.subTest(scope=scope):
                selected_args = ("--read-only", *args, *scope)
                first = self.cli(*selected_args, database="absent/ledger.sqlite3")
                self.assertEqual(first.returncode, 0, first.stderr)
                record = json.loads(first.stdout)
                self.assertEqual(record["schema_version"], version)
                self.assertEqual(record["receipt_sha256"], digest(
                    {k: v for k, v in record.items() if k != "receipt_sha256"}))
                self.assertEqual(record["visibility"], "owner_private")
                self.assertEqual(record["acceptance_state"], "proposed_unverified")
                self.assertFalse(record["dispatch_authorized"])
                self.assertEqual(record["external_actions"], 0)
                guard = ("--expected-receipt-digest", record["receipt_sha256"])
                guarded_name, default_name = f"private/guarded-{index}.json", f"private/default-{index}.json"
                for name, extra in ((guarded_name, guard), (default_name, ())):
                    saved = self.cli(*selected_args, *extra, "--out", name,
                                     database="absent/ledger.sqlite3")
                    self.assertEqual(saved.returncode, 0, saved.stderr)
                    output = self.root / name
                    self.assertEqual(json.loads(output.read_bytes()), record)
                    self.assertEqual(output.stat().st_mode & 0o777, 0o600)
                content = (self.root / guarded_name).read_bytes()
                self.assertEqual((self.root / default_name).read_bytes(), content)
                duplicate = self.cli(*selected_args, *guard, "--out", guarded_name,
                                     database="absent/ledger.sqlite3")
                self.assertEqual(duplicate.returncode, 1)
                self.assertEqual((self.root / guarded_name).read_bytes(), content)
                fresh = self.cli(*selected_args, *guard, database="absent/ledger.sqlite3")
                self.assertEqual(fresh.returncode, 0, fresh.stderr)
                self.assertEqual(fresh.stdout, first.stdout)
        self.assertFalse((self.root / "absent").exists())
        self.assertFalse(list((self.root / "private").glob(".jarvis-write-*")))
        self.assertEqual(((self.root / "registry.json").read_bytes(), self.db.read_bytes()), before)

    def test_registry_project_preflight_is_selective_without_ledger(self):
        from control_tower.network_contract import PROJECTS
        self.registry_input()
        path = self.root / "registry.json"
        registry = json.loads(path.read_text())
        other = next(p for p in PROJECTS if p != "ai-jarvis")
        registry["entries"].append({**deepcopy(registry["entries"][0]), "project_id": other})
        path.write_text(json.dumps(registry))
        before = path.read_bytes(), self.db.read_bytes()
        args = ("--read-only", "inspect-registry", "--file", "registry.json", "--digest", digest(registry),
                "--registry-revision", "1", "--source-revision", REVISION, "--project", other)
        selected = self.cli(*args, database="absent/ledger.sqlite3")
        self.assertEqual(selected.returncode, 0, selected.stderr)
        record = json.loads(selected.stdout)
        self.assertEqual(record["schema_version"], 2)
        self.assertEqual(record["project_id"], other)
        self.assertEqual(record["entry_count"], 1)
        saved = self.cli(*args, "--out", "private/selected.json", database="absent/ledger.sqlite3")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        output = self.root / "private/selected.json"
        content = output.read_bytes()
        self.assertEqual(json.loads(content), record)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.cli(*args, "--out", "private/selected.json").returncode, 1)
        self.assertEqual(output.read_bytes(), content)
        invalid = self.cli(*args[:-1], "unknown", "--out", "rejected/summary.json")
        self.assertEqual(invalid.returncode, 1)
        self.assertFalse((self.root / "rejected").exists())
        self.assertFalse((self.root / "absent").exists())
        self.assertEqual((path.read_bytes(), self.db.read_bytes()), before)

    def test_registry_project_cli_rejects_invalid_neighbors_without_output(self):
        from control_tower.network_contract import PROJECTS
        self.registry_input()
        path = self.root / "registry.json"
        original = json.loads(path.read_text())
        other = next(p for p in PROJECTS if p != "ai-jarvis")
        neighbor = {**deepcopy(original["entries"][0]), "project_id": other,
                    "resource_id": "private-neighbor-resource"}
        original["entries"].append(neighbor)
        invalid_scope = deepcopy(original)
        invalid_scope["entries"][-1]["allowed_actions"] = ["read", "write"]
        duplicate = deepcopy(original)
        duplicate["entries"].append(deepcopy(neighbor))
        output = self.root / "private/existing.json"
        output.parent.mkdir()
        output.write_bytes(b"KEEP")
        database_bytes = self.db.read_bytes()
        for index, registry in enumerate((invalid_scope, duplicate)):
            path.write_text(json.dumps(registry))
            registry_bytes = path.read_bytes()
            args = ("--read-only", "inspect-registry", "--file", "registry.json", "--digest", digest(registry),
                    "--registry-revision", "1", "--source-revision", REVISION, "--project", "ai-jarvis")
            for destination in ("rejected/summary.json", "private/existing.json"):
                with self.subTest(case=index, destination=destination):
                    rejected = self.cli(*args, "--out", destination, database="absent/ledger.sqlite3")
                    self.assertEqual(rejected.returncode, 1, rejected.stderr)
                    self.assertEqual(rejected.stdout, "")
                    self.assertNotIn("private-neighbor-resource", rejected.stderr)
                    self.assertFalse((self.root / "rejected").exists())
                    self.assertFalse((self.root / "absent").exists())
                    self.assertEqual(output.read_bytes(), b"KEEP")
                    self.assertEqual(path.read_bytes(), registry_bytes)
                    self.assertEqual(self.db.read_bytes(), database_bytes)

    def test_registry_preflight_without_ledger_survives_process_restart(self):
        args = self.registry_input()
        before = self.db.read_bytes(), (self.root / "registry.json").read_bytes()
        first = self.cli("--read-only", *args, database="absent/ledger.sqlite3")
        self.assertEqual(first.returncode, 0, first.stderr)
        result = json.loads(first.stdout)
        self.assertEqual(set(result["platform_counts"]), set(TARGETS))
        self.assertEqual(result["acceptance_state"], "proposed_unverified")
        self.assertFalse(result["dispatch_authorized"])
        self.assertEqual(result["visibility"], "owner_private")
        second = self.cli("--read-only", *args, "--out", "private/inspection.json",
                          database="absent/ledger.sqlite3")
        self.assertEqual(second.returncode, 0, second.stderr)
        output = self.root / "private/inspection.json"
        self.assertEqual(json.loads(output.read_text()), result)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        for private in ("private-destination", "owner/private-repository", "opaque-private-resource"):
            self.assertNotIn(private, output.read_text())
        self.assertFalse((self.root / "absent").exists())
        self.assertEqual((self.db.read_bytes(), (self.root / "registry.json").read_bytes()), before)
        third = self.cli(*args, "--out", "private/inspection.json")
        self.assertEqual(third.returncode, 1)
        self.assertEqual(json.loads(output.read_text()), result)

    def test_registry_preflight_stale_guards_leave_no_output_or_database(self):
        args = self.registry_input()
        before = self.db.read_bytes()
        for flag, value in (("--digest", "0" * 64), ("--registry-revision", "2"),
                            ("--source-revision", "0" * 40)):
            changed = list(args)
            changed[changed.index(flag) + 1] = value
            result = self.cli(*changed, "--out", "rejected/summary.json", database="absent/ledger.sqlite3")
            self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse((self.root / "rejected").exists())
        self.assertFalse((self.root / "absent").exists())
        self.assertEqual(self.db.read_bytes(), before)

    def test_registry_preflight_rejects_duplicate_json_and_escaping_input(self):
        args = self.registry_input()
        path = self.root / "registry.json"
        path.write_text('{"revision":1,' + path.read_text()[1:], encoding="utf-8")
        result = self.cli(*args, "--out", "rejected/summary.json", database="absent/ledger.sqlite3")
        self.assertEqual(result.returncode, 1)
        args[args.index("--file") + 1] = "../outside.json"
        self.assertEqual(self.cli(*args, database="absent/ledger.sqlite3").returncode, 1)
        self.assertFalse((self.root / "rejected").exists())
        self.assertFalse((self.root / "absent").exists())

    def controlled(self, execution="execution_blocked"):
        self.profile.update(schema_version=3, destination_id="synthetic-codex-workspace",
            control=dict(state="active", actor_id="local-controller", reason="Synthetic active task."))
        self.profile["execution"]["state"] = execution
        self.profile["context_refs"] = [dict(url="https://example.invalid/private-control-context",
            revision=1, visibility="owner_private")]
        self.write(self.profile)
        saved = self.save()
        self.assertEqual(saved.returncode, 0, saved.stderr)
        return json.loads(saved.stdout)["context_sha256"]

    def control(self, checksum, state="paused", memory=1, source=REVISION):
        return self.cli("set-context-control", "--handoff", "cli-task", "--state", state,
            "--actor", "local-controller", "--reason", "Synthetic operator hold.",
            "--digest", checksum, "--source-revision", source, "--memory-revision", str(memory))

    def control_snapshot(self):
        # Writable ledger opens may update SQLite file metadata. Compare every
        # saved record/schema statement rather than the database header bytes.
        with HandoffLedger(self.db, read_only=True) as ledger:
            return (ledger.db.execute("PRAGMA user_version").fetchone()[0], tuple(ledger.db.iterdump()))

    def test_control_cli_pause_restart_duplicate_and_review_invalidation(self):
        checksum = self.controlled()
        with HandoffLedger(self.db) as ledger:
            manifest = build_swarm("ai-jarvis", ["codex"], swarm_id="cli-pilot", source_revision=REVISION)
            staged = ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
                target="codex", text="Independent synthetic task."), manifest,
                assistant_id="cli-pilot.builder", handoff_id="other-task")
            independent = deepcopy(self.profile)
            independent.update(handoff_id="other-task", mission_id="other-task",
                handoff_sha256=staged["handoff_sha256"], destination_id="other-synthetic-workspace")
            ledger.save_context(independent, expected_revision=0)
        self.assertEqual(self.review_context(checksum).returncode, 0)
        paused = self.control(checksum)
        self.assertEqual(paused.returncode, 0, paused.stderr)
        receipt = json.loads(paused.stdout)
        self.assertEqual((receipt["revision"], receipt["memory_revision"]), (2, 2))
        self.assertFalse(receipt["retry_authorized"])
        self.assertFalse(receipt["dispatch_authorized"])
        self.assertEqual(self.load(memory=2).returncode, 0)
        retained = json.loads((self.root / "resumed.json").read_text())
        expected = deepcopy(self.profile)
        expected.update(memory_revision=2, control=dict(state="paused", actor_id="local-controller",
            reason="Synthetic operator hold."))
        self.assertEqual(retained["profile"], expected)
        self.assertEqual(retained["review_state"], "proposed")
        before = self.control_snapshot()
        duplicate = self.control(receipt["context_sha256"], memory=2)
        self.assertEqual(duplicate.returncode, 0, duplicate.stderr)
        replay = json.loads(duplicate.stdout)
        self.assertTrue(replay["duplicate"])
        self.assertEqual((replay["revision"], replay["memory_revision"]), (2, 2))
        self.assertEqual(self.control_snapshot(), before)
        cancelled = self.control(receipt["context_sha256"], state="cancelled", memory=2)
        self.assertEqual(cancelled.returncode, 0, cancelled.stderr)
        terminal = json.loads(cancelled.stdout)
        before = self.control_snapshot()
        self.assertNotEqual(self.control(terminal["context_sha256"], memory=3).returncode, 0)
        self.assertEqual(self.control_snapshot(), before)
        with HandoffLedger(self.db, read_only=True) as ledger:
            self.assertEqual(ledger.load_context("other-task", expected_source_revision=REVISION,
                expected_memory_revision=1)["profile"], independent)

    def test_control_cli_preserves_unknown_outcome_and_checkpoint(self):
        checksum = self.controlled(execution="outcome_unknown")
        paused = self.control(checksum)
        self.assertEqual(paused.returncode, 0, paused.stderr)
        receipt = json.loads(paused.stdout)
        self.assertEqual(receipt["execution_state"], "outcome_unknown")
        self.assertEqual(self.load(memory=2).returncode, 0)
        retained = json.loads((self.root / "resumed.json").read_text())["profile"]
        self.assertEqual(retained["execution"], self.profile["execution"])
        self.assertEqual(retained["destination_id"], self.profile["destination_id"])
        self.assertEqual(retained["handoff_sha256"], self.profile["handoff_sha256"])

    def test_control_revision_cli_rejects_restored_selection_and_retains_duplicate(self):
        checksum = self.controlled(execution="outcome_unknown")
        changed = deepcopy(self.profile)
        changed["execution"]["detail"] = "Temporary private control edit."
        self.write(changed)
        self.assertEqual(self.save(revision=1).returncode, 0)
        self.write(self.profile)
        restored = self.save(revision=2)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(json.loads(restored.stdout)["context_sha256"], checksum)
        args = ("set-context-control", "--handoff", "cli-task", "--state", "paused",
                "--actor", "local-controller", "--reason", "Synthetic operator hold.",
                "--source-revision", REVISION)
        before = self.control_snapshot()
        for revision in ("1", "2", "4", "0", "-1"):
            rejected = self.cli(*args, "--digest", checksum, "--memory-revision", "1",
                                "--context-revision", revision)
            self.assertEqual(rejected.returncode, 1, rejected.stderr)
            self.assertIn("context retrieval revision", rejected.stderr)
            self.assertEqual(self.control_snapshot(), before)
        accepted = self.cli(*args, "--digest", checksum, "--memory-revision", "1",
                            "--context-revision", "3")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        result = json.loads(accepted.stdout)
        self.assertEqual(result["revision"], 4)
        self.assertEqual(result["memory_revision"], 2)
        self.assertEqual(result["execution_state"], "outcome_unknown")
        self.assertFalse(result["duplicate"])
        for flag in ("retry_authorized", "dispatch_authorized", "external_actions"):
            self.assertFalse(result[flag])
        with HandoffLedger(self.db, read_only=True) as ledger:
            current = ledger.load_context("cli-task", expected_source_revision=REVISION,
                                          expected_memory_revision=2, expected_revision=4)
        expected = deepcopy(self.profile)
        expected["control"] = dict(state="paused", actor_id="local-controller", reason="Synthetic operator hold.")
        expected["memory_revision"] = 2
        self.assertEqual(current["profile"], expected)
        self.assertEqual(current["review_state"], "proposed")
        before = self.control_snapshot()
        fresh = (*args, "--digest", result["context_sha256"], "--memory-revision", "2")
        self.assertEqual(self.cli(*fresh, "--context-revision", "3").returncode, 1)
        for options in (("--context-revision", "4"), ()):
            repeated = self.cli(*fresh, *options)
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertTrue(json.loads(repeated.stdout)["duplicate"])
            self.assertEqual(self.control_snapshot(), before)

    def test_control_cli_refuses_legacy_stale_guards_and_read_only(self):
        saved = self.save()
        checksum = json.loads(saved.stdout)["context_sha256"]
        before = self.control_snapshot()
        result = self.control(checksum)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("explicitly saved", result.stderr)
        self.assertEqual(self.control_snapshot(), before)
        self.profile.update(schema_version=2,
            control=dict(state="active", actor_id="local-controller", reason="Synthetic active task."))
        self.write(self.profile)
        checksum = json.loads(self.save(1).stdout)["context_sha256"]
        before = self.control_snapshot()
        for guard in (("0" * 64, REVISION, 1), (checksum, "f" * 40, 1), (checksum, REVISION, 2)):
            result = self.control(guard[0], source=guard[1], memory=guard[2])
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.control_snapshot(), before)
        readonly = self.cli("--read-only", "set-context-control", "--handoff", "cli-task",
            "--state", "paused", "--actor", "local-controller", "--reason", "Synthetic hold.",
            "--digest", checksum, "--source-revision", REVISION, "--memory-revision", "1")
        self.assertNotEqual(readonly.returncode, 0)
        self.assertIn("read-only", readonly.stderr)
        self.assertEqual(self.control_snapshot(), before)
        self.profile["visibility"] = "public_candidate"
        self.write(self.profile)
        checksum = json.loads(self.save(2).stdout)["context_sha256"]
        before = self.control_snapshot()
        public = self.control(checksum)
        self.assertNotEqual(public.returncode, 0)
        self.assertIn("owner-private", public.stderr)
        self.assertEqual(self.control_snapshot(), before)

    def test_control_edit_retains_all_portable_target_scopes(self):
        from control_tower.network_contract import TARGETS
        with HandoffLedger(self.db) as ledger:
            for target in sorted(TARGETS):
                swarm = "control-" + target
                handoff = "hold-" + target
                manifest = build_swarm("ai-jarvis", [target], swarm_id=swarm, source_revision=REVISION)
                staged = ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
                    target=target, text="Synthetic portable control task."), manifest,
                    assistant_id=swarm + ".builder", handoff_id=handoff)
                profile = deepcopy(self.profile)
                profile.update(schema_version=3, handoff_id=handoff, mission_id=handoff,
                    handoff_sha256=staged["handoff_sha256"], asset_id=swarm + ".builder", platform=target,
                    destination_id="dest-" + target,
                    control=dict(state="active", actor_id="local-controller", reason="Synthetic active task."))
                saved = ledger.save_context(profile, expected_revision=0)
                result = _set_context_control(ledger, handoff_id=handoff, state="paused",
                    actor_id="local-controller", reason="Synthetic portable hold.",
                    expected_sha256=saved["context_sha256"], expected_source_revision=REVISION,
                    expected_memory_revision=1)
                self.assertEqual(result["memory_revision"], 2)
        with HandoffLedger(self.db, read_only=True) as ledger:
            for target in sorted(TARGETS):
                retained = ledger.load_context("hold-" + target, expected_source_revision=REVISION,
                                               expected_memory_revision=2)["profile"]
                self.assertEqual(retained["platform"], target)
                self.assertEqual(retained["destination_id"], "dest-" + target)
                self.assertEqual(retained["control"]["state"], "paused")
                self.assertEqual(retained["execution"], self.profile["execution"])

    def test_guarded_cancellation_retains_all_portable_targets_after_restart(self):
        retained = {}
        with HandoffLedger(self.db) as ledger:
            for target in sorted(TARGETS):
                with self.subTest(target=target):
                    swarm, handoff = "terminal-" + target, "cancel-" + target
                    manifest = build_swarm("ai-jarvis", [target], swarm_id=swarm, source_revision=REVISION)
                    staged = ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
                        target=target, text="Synthetic portable cancellation task."), manifest,
                        assistant_id=swarm + ".builder", handoff_id=handoff)
                    profile = deepcopy(self.profile)
                    profile.update(schema_version=3, handoff_id=handoff, mission_id=handoff,
                        handoff_sha256=staged["handoff_sha256"], asset_id=swarm + ".builder",
                        platform=target, destination_id="dest-" + target,
                        control=dict(state="active", actor_id="local-controller", reason="Synthetic active task."))
                    profile["execution"]["state"] = "outcome_unknown"
                    saved = ledger.save_context(profile, expected_revision=0)
                    args = dict(handoff_id=handoff, state="cancelled", actor_id="local-controller",
                        reason="Synthetic terminal hold.", expected_source_revision=REVISION)
                    cancelled = _set_context_control(ledger, **args,
                        expected_sha256=saved["context_sha256"], expected_memory_revision=1, expected_revision=1)
                    self.assertEqual(cancelled["revision"], 2)
                    self.assertFalse(cancelled["duplicate"])
                    for flag in ("dispatch_authorized", "retry_authorized", "external_actions"):
                        self.assertFalse(cancelled[flag])
                    guards = dict(expected_sha256=cancelled["context_sha256"], expected_memory_revision=2)
                    before = tuple(ledger.db.iterdump())
                    with self.assertRaisesRegex(ValueError, "context retrieval revision mismatch"):
                        _set_context_control(ledger, **args, **guards, expected_revision=1)
                    duplicate = _set_context_control(ledger, **args, **guards, expected_revision=2)
                    self.assertTrue(duplicate["duplicate"])
                    self.assertEqual(duplicate["revision"], 2)
                    with self.assertRaisesRegex(ValueError, "cancelled handoff cannot resume"):
                        _set_context_control(ledger, **{**args, "state": "paused"}, **guards, expected_revision=2)
                    self.assertEqual(tuple(ledger.db.iterdump()), before)
                    profile["memory_revision"] = 2
                    profile["control"] = dict(state="cancelled", actor_id="local-controller", reason="Synthetic terminal hold.")
                    retained[handoff] = profile
        before = self.db.read_bytes()
        with HandoffLedger(self.db, read_only=True) as restarted:
            for handoff, expected in retained.items():
                selected = restarted.load_context(handoff, expected_source_revision=REVISION,
                    expected_memory_revision=2, expected_revision=2)
                self.assertEqual(selected["profile"], expected)
                self.assertEqual(selected["review_state"], "proposed")
                self.assertEqual(selected["sender_authentication"], "not_established")
            self.assertEqual(len(retained), len(TARGETS))
        self.assertEqual(self.db.read_bytes(), before)

    def test_control_edit_rejects_concurrent_update_without_overwriting(self):
        checksum = self.controlled()
        with HandoffLedger(self.db) as ledger, HandoffLedger(self.db) as other:
            original_load = ledger.load_context
            def interleave(*args, **kwargs):
                selected = original_load(*args, **kwargs)
                changed = deepcopy(selected["profile"])
                changed["execution"]["detail"] = "Concurrent retained checkpoint."
                changed["memory_revision"] = 2
                other.save_context(changed, expected_revision=selected["revision"])
                return selected
            with patch.object(ledger, "load_context", side_effect=interleave):
                with self.assertRaisesRegex(ValueError, "context revision mismatch"):
                    _set_context_control(ledger, handoff_id="cli-task", state="paused",
                        actor_id="local-controller", reason="Synthetic hold.",
                        expected_sha256=checksum, expected_source_revision=REVISION, expected_memory_revision=1)
            retained = other.load_context("cli-task", expected_source_revision=REVISION,
                                          expected_memory_revision=2)["profile"]
            self.assertEqual(retained["control"]["state"], "active")
            self.assertEqual(retained["execution"]["detail"], "Concurrent retained checkpoint.")

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

    def test_cli_queue_review_state_private_snapshot_invalidates_on_review(self):
        saved = json.loads(self.save().stdout)
        args = ("--read-only", "queue-report", "--project", "ai-jarvis", "--mission", "cli-task", "--include-review-state")
        first = json.loads(self.cli(*args).stdout)
        self.assertEqual(first["schema_version"], 3)
        self.assertFalse(first["bindings"][0]["context_review_current"])
        review = self.cli("review-context", "--handoff", "cli-task", "--reviewer", "local-evaluator",
                          "--digest", saved["context_sha256"])
        self.assertEqual(review.returncode, 0, review.stderr)
        before = self.db.read_bytes()
        stale = self.cli(*args, "--expected-report-digest", first["report_sha256"], "--out", "stale/review.json")
        self.assertEqual(stale.returncode, 1)
        self.assertFalse((self.root / "stale").exists())
        fresh = json.loads(self.cli(*args).stdout)
        self.assertTrue(fresh["bindings"][0]["context_review_current"])
        self.assertFalse(fresh["bindings"][0]["handoff_review_current"])
        written = self.cli(*args, "--expected-report-digest", fresh["report_sha256"], "--out", "private/review.json")
        self.assertEqual(written.returncode, 0, written.stderr)
        output = self.root / "private/review.json"
        self.assertEqual(json.loads(output.read_text()), fresh)
        if os.name == "posix":
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("local-evaluator", output.read_text())
        self.assertFalse(fresh["dispatch_authorized"])
        self.assertEqual(self.db.read_bytes(), before)

    def test_cli_queue_snapshot_guard_refuses_stale_file_without_writes(self):
        self.assertEqual(self.save().returncode, 0)
        args = ("--read-only", "queue-report", "--project", "ai-jarvis", "--mission", "cli-task")
        first = json.loads(self.cli(*args).stdout)
        guarded = (*args, "--expected-report-digest", first["report_sha256"])
        self.assertEqual(json.loads(self.cli(*guarded).stdout), first)
        saved = self.cli(*guarded, "--out", "private/current.json")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        output = self.root / "private/current.json"
        retained = output.read_bytes()
        if os.name == "posix":
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.profile["memory_revision"] = 2
        self.profile["execution"]["detail"] = "New private checkpoint detail."
        self.write(self.profile)
        self.assertEqual(self.save(revision=1).returncode, 0)
        before = self.db.read_bytes()
        stale = self.cli(*guarded, "--out", "stale/should-not-exist.json")
        self.assertEqual(stale.returncode, 1)
        self.assertIn("queue report is stale", json.loads(stale.stderr)["error"])
        self.assertFalse((self.root / "stale").exists())
        self.assertEqual(output.read_bytes(), retained)
        self.assertEqual(self.db.read_bytes(), before)
        fresh = json.loads(self.cli(*args).stdout)
        self.assertNotEqual(fresh["report_sha256"], first["report_sha256"])
        self.assertEqual(json.loads(self.cli(*args, "--expected-report-digest", fresh["report_sha256"]).stdout), fresh)
        self.assertEqual(self.db.read_bytes(), before)

    def test_cli_mission_queue_report_private_file_round_trip(self):
        self.assertEqual(self.save().returncode, 0)
        before = self.db.read_bytes()
        args = ("--read-only", "queue-report", "--project", "ai-jarvis", "--mission", "cli-task")
        first = self.cli(*args)
        self.assertEqual(first.returncode, 0, first.stderr)
        record = json.loads(first.stdout)
        self.assertEqual(record["schema_version"], 2)
        self.assertEqual(record["handoff_count"], 1)
        self.assertEqual(record["mission_id"], "cli-task")
        self.assertEqual(record["execution_states"]["execution_blocked"], 1)
        saved = self.cli(*args, "--out", "private/mission.json")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        output = self.root / "private/mission.json"
        self.assertEqual(json.loads(output.read_text()), record)
        if os.name == "posix":
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(self.cli(*args).stdout), record)
        self.assertEqual(self.cli(*args, "--out", "private/mission.json").returncode, 1)
        self.assertEqual(json.loads(output.read_text()), record)
        empty = self.cli("--read-only", "queue-report", "--project", "ai-jarvis", "--mission", "absent-mission")
        self.assertEqual(json.loads(empty.stdout)["handoff_count"], 0)
        self.assertEqual(self.cli("--read-only", "queue-report", "--project", "ai-jarvis", "--mission", "../bad").returncode, 1)
        self.assertEqual(self.cli(*args, database="absent/ledger.sqlite3").returncode, 1)
        self.assertFalse((self.root / "absent").exists())
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

    def test_report_files_retain_exact_private_metadata_without_ledger_writes(self):
        checksum = self.controlled(execution="outcome_unknown")
        self.assertEqual(self.control(checksum).returncode, 0)
        before = self.db.read_bytes()
        commands = [("queue-report", "--project", "ai-jarvis"),
            ("destination-status", "--project", "ai-jarvis", "--platform", "codex",
             "--destination", "synthetic-codex-workspace")]
        for index, command in enumerate(commands):
            with self.subTest(command=command[0]):
                observed = self.cli("--read-only", *command)
                self.assertEqual(observed.returncode, 0, observed.stderr)
                output = f"private/report-{index}.json"
                saved = self.cli("--read-only", *command, "--out", output)
                self.assertEqual(saved.returncode, 0, saved.stderr)
                self.assertEqual(json.loads(saved.stdout), {"saved": output, "external_actions": 0})
                path = self.root / output
                packet = json.loads(path.read_text())
                self.assertEqual(packet, json.loads(observed.stdout))
                self.assertEqual(packet["visibility"], "owner_private")
                self.assertFalse(packet["dispatch_authorized"])
                self.assertNotIn("https://", path.read_text())
                self.assertNotIn(self.profile["execution"]["detail"], path.read_text())
                if os.name == "posix":
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                if command[0] == "queue-report":
                    self.assertEqual(packet["execution_states"]["outcome_unknown"], 1)
                    self.assertEqual(packet["control_states"]["paused"], 1)
                else:
                    self.assertEqual(packet["records"][0]["execution_state"], "outcome_unknown")
                    self.assertEqual(packet["records"][0]["control_state"], "paused")
                self.assertEqual(self.db.read_bytes(), before)

    def test_report_file_guards_preserve_existing_evidence_and_missing_ledger(self):
        self.controlled()
        before = self.db.read_bytes()
        for command in [("queue-report", "--project", "ai-jarvis"),
            ("destination-status", "--project", "ai-jarvis", "--platform", "codex",
             "--destination", "synthetic-codex-workspace")]:
            with self.subTest(command=command[0]):
                existing = self.root / "keep.json"
                existing.write_text("Retained earlier evidence.")
                rejected = self.cli("--read-only", *command, "--out", "keep.json")
                self.assertEqual(rejected.returncode, 1, rejected.stderr)
                self.assertEqual(existing.read_text(), "Retained earlier evidence.")
                escaped = self.cli("--read-only", *command, "--out", "../escape.json")
                self.assertEqual(escaped.returncode, 1, escaped.stderr)
                missing = self.cli("--read-only", *command, "--out", "absent/report.json",
                                   database="missing.sqlite3")
                self.assertEqual(missing.returncode, 1, missing.stderr)
                self.assertFalse((self.root / "missing.sqlite3").exists())
                self.assertFalse((self.root / "absent").exists())
                self.assertEqual(self.db.read_bytes(), before)

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

    def test_cli_historical_export_rejects_invalid_neighbor_before_creating_output(self):
        self.profile.update(schema_version=3, destination_id="private-repository",
            control=dict(state="active", actor_id="local-owner", reason="Synthetic scope."))
        with HandoffLedger(self.db) as ledger:
            first = ledger.save_context(self.profile, expected_revision=0)
            ledger.checkpoint_context("cli-task", expected_sha256=first["context_sha256"],
                expected_source_revision=REVISION, expected_memory_revision=1)
            middle = deepcopy(self.profile)
            middle["memory_revision"] = 2
            second = ledger.save_context(middle, expected_revision=1)
            ledger.checkpoint_context("cli-task", expected_sha256=second["context_sha256"],
                expected_source_revision=REVISION, expected_memory_revision=2)
            current = deepcopy(middle)
            current["memory_revision"] = 3
            current["control"]["state"] = "paused"
            current["execution"]["state"] = "outcome_unknown"
            ledger.save_context(current, expected_revision=2)
            damaged = deepcopy(middle)
            damaged["memory_revision"] = 4
            damaged["execution"]["detail"] = "PRIVATE_NEIGHBOR_CONTEXT"
            ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=? AND revision=2",
                (json.dumps(damaged), digest(damaged), "cli-task"))
        args = ("load-checkpoint", "--handoff", "cli-task", "--digest", first["context_sha256"],
                "--source-revision", REVISION, "--memory-revision", "1", "--checkpoint-revision", "1",
                "--out", "uncreated/nested/history.json")
        before = self.db.read_bytes()
        result = self.cli(*args)  # A new process must reject before invoking the output writer.
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("checkpoint integrity", json.loads(result.stderr)["error"])
        self.assertNotIn("PRIVATE_NEIGHBOR_CONTEXT", result.stderr)
        self.assertFalse((self.root / "uncreated").exists())
        self.assertFalse(list(self.root.glob("ledger.sqlite3-*")))
        self.assertEqual(self.db.read_bytes(), before)
        with HandoffLedger(self.db, read_only=True) as ledger:
            self.assertEqual(ledger.load_context("cli-task", expected_source_revision=REVISION,
                expected_memory_revision=3)["profile"], current)
        # Fixture-only restoration is separate from the CLI; no repair command is implied.
        with HandoffLedger(self.db) as ledger:
            ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=? AND revision=2",
                (json.dumps(middle), digest(middle), "cli-task"))
        before = self.db.read_bytes()
        valid = self.cli(*args)
        self.assertEqual(valid.returncode, 0, valid.stderr)
        output = self.root / "uncreated/nested/history.json"
        retained = output.read_bytes()
        packet = json.loads(retained)
        self.assertEqual(packet["profile"], self.profile)
        self.assertEqual(packet["visibility"], "owner_private")
        self.assertEqual(packet["authority"], "historical_context_only_not_approval")
        self.assertFalse(packet["retry_authorized"])
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.cli(*args).returncode, 1)
        self.assertEqual(output.read_bytes(), retained)
        self.assertEqual(self.db.read_bytes(), before)

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

    def test_checkpoint_index_digest_cli_rejects_stale_before_output_and_retains_private_file(self):
        checksum = self.controlled(execution="outcome_unknown")
        args = ("list-checkpoints", "--handoff", "cli-task")
        old = self.cli(*args, "--include-digest")
        self.assertEqual(old.returncode, 0, old.stderr)
        old_digest = json.loads(old.stdout)["report_sha256"]
        self.assertEqual(self.cli("capture-checkpoint", "--allow-schema-upgrade", "--handoff", "cli-task",
            "--digest", checksum, "--source-revision", REVISION, "--memory-revision", "1").returncode, 0)
        before = self.db.read_bytes()
        for value in (old_digest, "bad"):
            rejected = self.cli(*args, "--expected-report-digest", value, "--out", "rejected/index.json")
            self.assertEqual(rejected.returncode, 1, rejected.stderr)
            self.assertFalse((self.root / "rejected").exists())
        fresh = self.cli(*args, "--include-digest")
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        report = json.loads(fresh.stdout)
        saved = self.cli(*args, "--expected-report-digest", report["report_sha256"], "--out", "private/index.json")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        output = self.root / "private/index.json"
        self.assertEqual(json.loads(output.read_text()), report)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        retained = output.read_bytes()
        self.assertEqual(self.cli(*args, "--include-digest", "--out", "private/index.json").returncode, 1)
        self.assertEqual(output.read_bytes(), retained)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertNotIn("Synthetic", fresh.stdout)
        self.assertFalse(report["retry_authorized"])

    def test_checkpoint_index_file_survives_restart_without_copying_private_context(self):
        checksum = self.controlled(execution="outcome_unknown")
        self.assertEqual(self.cli("capture-checkpoint", "--allow-schema-upgrade", "--handoff", "cli-task",
            "--digest", checksum, "--source-revision", REVISION, "--memory-revision", "1").returncode, 0)
        self.assertEqual(self.control(checksum).returncode, 0)
        before = self.db.read_bytes()
        observed = self.cli("list-checkpoints", "--handoff", "cli-task")
        saved = self.cli("list-checkpoints", "--handoff", "cli-task", "--out", "private/index.json")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertEqual(json.loads(saved.stdout), {"saved": "private/index.json", "external_actions": 0})
        path = self.root / "private/index.json"
        index = json.loads(path.read_text())
        self.assertEqual(index, json.loads(observed.stdout))
        self.assertEqual(index["visibility"], "owner_private")
        self.assertFalse(index["retry_authorized"])
        self.assertEqual(index["checkpoints"][0]["execution_state"], "outcome_unknown")
        self.assertNotIn("https://", path.read_text())
        self.assertNotIn(self.profile["execution"]["detail"], path.read_text())
        if os.name == "posix":
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        checkpoint = index["checkpoints"][0]
        restored = self.cli("load-checkpoint", "--handoff", "cli-task", "--checkpoint-revision",
            str(checkpoint["checkpoint_revision"]), "--digest", checkpoint["context_sha256"],
            "--source-revision", checkpoint["source_revision"], "--memory-revision",
            str(checkpoint["memory_revision"]), "--out", "private/history.json")
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(self.db.read_bytes(), before)
        with HandoffLedger(self.db, read_only=True) as ledger:
            current = ledger.load_context("cli-task", expected_source_revision=REVISION,
                expected_memory_revision=2, audience="owner_private")
        self.assertEqual(current["profile"]["control"]["state"], "paused")
        self.assertEqual(current["profile"]["execution"]["state"], "outcome_unknown")

    def test_checkpoint_index_file_guards_and_empty_legacy_history(self):
        before = self.db.read_bytes()
        empty = self.cli("--read-only", "list-checkpoints", "--handoff", "cli-task", "--out", "empty.json")
        self.assertEqual(empty.returncode, 0, empty.stderr)
        path = self.root / "empty.json"
        original = path.read_bytes()
        self.assertEqual(json.loads(original)["checkpoints"], [])
        for extra in [("--out", "empty.json"), ("--out", "../escape.json")]:
            rejected = self.cli("list-checkpoints", "--handoff", "cli-task", *extra)
            self.assertEqual(rejected.returncode, 1, rejected.stderr)
        self.assertEqual(path.read_bytes(), original)
        unknown = self.cli("list-checkpoints", "--handoff", "unknown-task", "--out", "unknown.json")
        self.assertEqual(unknown.returncode, 1, unknown.stderr)
        self.assertFalse((self.root / "unknown.json").exists())
        missing = self.cli("list-checkpoints", "--handoff", "cli-task", "--out", "absent/index.json",
            database="missing.sqlite3")
        self.assertEqual(missing.returncode, 1, missing.stderr)
        self.assertFalse((self.root / "missing.sqlite3").exists())
        self.assertFalse((self.root / "absent").exists())
        self.assertEqual(self.db.read_bytes(), before)

    def test_backup_rejects_historical_attempt_regression_without_changing_holds(self):
        checksum = self.controlled(execution="outcome_unknown")
        self.assertEqual(self.cli("capture-checkpoint", "--allow-schema-upgrade", "--handoff", "cli-task",
            "--digest", checksum, "--source-revision", REVISION, "--memory-revision", "1").returncode, 0)
        self.assertEqual(self.control(checksum).returncode, 0)
        damaged = deepcopy(self.profile)
        damaged["execution"]["attempts"] = 2
        with HandoffLedger(self.db) as ledger:
            ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=?",
                (json.dumps(damaged), digest(damaged), "cli-task"))
        before = self.db.read_bytes()
        result = self.cli("--read-only", "backup-ledger", "--out", "private/rejected.sqlite3")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse((self.root / "private/rejected.sqlite3").exists())
        self.assertFalse(list((self.root / "private").glob(".jarvis-backup-*")))
        self.assertEqual(self.db.read_bytes(), before)
        with HandoffLedger(self.db, read_only=True) as ledger:
            retained = ledger.load_context("cli-task", expected_source_revision=REVISION,
                expected_memory_revision=2, audience="owner_private")["profile"]
        self.assertEqual(retained["control"]["state"], "paused")
        self.assertEqual(retained["execution"]["state"], "outcome_unknown")

    def test_backup_rejects_historical_mission_drift_without_repair_or_publication(self):
        checksum = self.controlled(execution="outcome_unknown")
        self.assertEqual(self.cli("capture-checkpoint", "--allow-schema-upgrade", "--handoff", "cli-task",
            "--digest", checksum, "--source-revision", REVISION, "--memory-revision", "1").returncode, 0)
        self.assertEqual(self.control(checksum).returncode, 0)
        damaged = {**self.profile, "mission_id": "different-mission"}
        with HandoffLedger(self.db) as ledger:
            ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=?",
                (json.dumps(damaged), digest(damaged), "cli-task"))
        before = self.db.read_bytes()
        result = self.cli("--read-only", "backup-ledger", "--out", "private/rejected.sqlite3")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse((self.root / "private/rejected.sqlite3").exists())
        self.assertFalse(list((self.root / "private").glob(".jarvis-backup-*")))
        self.assertEqual(self.db.read_bytes(), before)
        with HandoffLedger(self.db, read_only=True) as ledger:
            retained = ledger.load_context("cli-task", expected_source_revision=REVISION,
                expected_memory_revision=2, audience="owner_private")["profile"]
        self.assertEqual(retained["control"]["state"], "paused")
        self.assertEqual(retained["execution"]["state"], "outcome_unknown")

    def test_backup_rejects_historical_destination_drift_without_changing_holds(self):
        checksum = self.controlled(execution="outcome_unknown")
        self.assertEqual(self.cli("capture-checkpoint", "--allow-schema-upgrade", "--handoff", "cli-task",
            "--digest", checksum, "--source-revision", REVISION, "--memory-revision", "1").returncode, 0)
        self.assertEqual(self.control(checksum).returncode, 0)
        damaged = {**self.profile, "destination_id": "different-destination"}
        with HandoffLedger(self.db) as ledger:
            ledger.db.execute("UPDATE context_checkpoints SET body=?,digest=? WHERE handoff_id=?",
                (json.dumps(damaged), digest(damaged), "cli-task"))
        before = self.db.read_bytes()
        result = self.cli("--read-only", "backup-ledger", "--out", "private/rejected.sqlite3")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse((self.root / "private/rejected.sqlite3").exists())
        self.assertFalse(list((self.root / "private").glob(".jarvis-backup-*")))
        self.assertEqual(self.db.read_bytes(), before)
        with HandoffLedger(self.db, read_only=True) as ledger:
            retained = ledger.load_context("cli-task", expected_source_revision=REVISION,
                expected_memory_revision=2, audience="owner_private")["profile"]
        self.assertEqual(retained["destination_id"], self.profile["destination_id"])
        self.assertEqual(retained["control"]["state"], "paused")
        self.assertEqual(retained["execution"]["state"], "outcome_unknown")

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

    def test_export_revision_cli_rejects_stale_selection_without_output_or_state_change(self):
        checksum = self.prepare_reviews()
        changed = deepcopy(self.profile)
        changed["execution"]["detail"] = "Synthetic intervening context."
        self.write(changed)
        self.assertEqual(self.save(1).returncode, 0)
        self.write(self.profile)
        restored = self.save(2)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(json.loads(restored.stdout)["context_sha256"], checksum)
        self.assertEqual(self.review_context(checksum).returncode, 0)
        before = self.control_snapshot()
        args = ("export-context", "--handoff", "cli-task", "--digest", checksum,
                "--source-revision", REVISION, "--memory-revision", "1", "--context-revision")
        for revision in ("1", "2", "4", "0", "-1"):
            with self.subTest(revision=revision):
                rejected = self.cli(*args, revision, "--out", "rejected/envelope.json")
                self.assertEqual(rejected.returncode, 1, rejected.stderr)
                self.assertIn("context export revision", rejected.stderr)
                self.assertEqual(rejected.stdout, "")
                self.assertFalse((self.root / "rejected").exists())
                self.assertEqual(self.control_snapshot(), before)
        exported = self.cli(*args, "3", "--out", "private/envelope.json")
        self.assertEqual(exported.returncode, 0, exported.stderr)
        path = self.root / "private/envelope.json"
        content = path.read_bytes()
        packet = json.loads(content)
        self.assertEqual(packet["context_revision"], 3)
        self.assertEqual(packet["schema_version"], 1)
        self.assertEqual(packet["context"], self.profile)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        after = self.control_snapshot()
        self.assertEqual(self.cli(*args, "3", "--out", "private/envelope.json").returncode, 1)
        self.assertEqual(path.read_bytes(), content)
        self.assertEqual(self.control_snapshot(), after)
        self.assertEqual(self.export_context(checksum, out="default.json").returncode, 0)
        self.assertEqual(json.loads((self.root / "default.json").read_bytes()), packet)
        self.assertEqual(self.control_snapshot(), after)

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

    def test_large_valid_context_envelope_saves_complete_after_review(self):
        from control_tower.network_contract import MAX_PACKET_BYTES, canonical, load_packet
        draft = dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
                     target="codex", text="D" * 20000)
        with HandoffLedger(self.db) as ledger:
            manifest = build_swarm("ai-jarvis", ["codex"], swarm_id="cli-pilot", source_revision=REVISION)
            staged = ledger.stage(draft, manifest, assistant_id="cli-pilot.builder", handoff_id="large-task")
        profile = deepcopy(self.profile)
        profile.update(schema_version=2, handoff_id="large-task", mission_id="large-task",
                       handoff_sha256=staged["handoff_sha256"])
        profile["control"] = dict(state="active", actor_id="local-controller", reason="R" * 20000)
        profile["execution"]["detail"] = "E" * 20000
        profile["context_refs"] = [dict(url="https://example.invalid/" + str(i) + "x" * 1800,
            revision=1, visibility="owner_private") for i in range(5)]
        (self.root / "context.json").write_bytes(canonical(profile))
        self.assertEqual(load_packet(self.root / "context.json"), profile)
        saved = self.save()
        self.assertEqual(saved.returncode, 0, saved.stderr)
        checksum = json.loads(saved.stdout)["context_sha256"]
        args = ("export-context", "--handoff", "large-task", "--digest", checksum,
                "--source-revision", REVISION, "--memory-revision", "1", "--out", "large-envelope.json")
        self.assertNotEqual(self.cli(*args).returncode, 0)
        self.assertFalse((self.root / "large-envelope.json").exists())
        for command, value in (("review", staged["handoff_sha256"]), ("review-context", checksum)):
            reviewed = self.cli(command, "--handoff", "large-task", "--digest", value,
                                "--reviewer", "local-reviewer")
            self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        exported = self.cli(*args)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        path = self.root / "large-envelope.json"
        original = path.read_bytes()
        self.assertGreater(len(original), MAX_PACKET_BYTES)
        envelope = json.loads(original)
        self.assertEqual(envelope["context"], profile)
        self.assertEqual(envelope["handoff"]["draft"], draft)
        self.assertEqual(envelope["context_sha256"], checksum)
        self.assertEqual(envelope["external_actions"], 0)
        with HandoffLedger(self.db, read_only=True) as ledger:
            restored = ledger.load_context("large-task", expected_source_revision=REVISION, expected_memory_revision=1)
            self.assertEqual(restored["profile"], profile)
        self.assertNotEqual(self.cli(*args).returncode, 0)
        self.assertEqual(path.read_bytes(), original)

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

    def test_inspection_cli_can_pin_stored_revision_after_content_restore(self):
        self.profile["execution"]["state"] = "outcome_unknown"
        self.write(self.profile)
        first = json.loads(self.save().stdout)
        original = deepcopy(self.profile)
        self.profile["execution"]["detail"] = "Temporary edit."
        self.write(self.profile)
        self.assertEqual(self.save(1).returncode, 0)
        self.write(original)
        restored = json.loads(self.save(2).stdout)
        self.assertEqual(first["context_sha256"], restored["context_sha256"])
        before = self.db.read_bytes()
        args = ("--read-only", "inspect-recovery", "--handoff", "cli-task", "--digest",
            first["context_sha256"], "--source-revision", REVISION, "--memory-revision", "1")
        for value in ("1", "2", "4", "0", "-1", "bad"):
            with self.subTest(value=value):
                rejected = self.cli(*args, "--context-revision", value, "--out", "rejected.json")
                self.assertNotEqual(rejected.returncode, 0)
                self.assertFalse((self.root / "rejected.json").exists())
        accepted = self.cli(*args, "--context-revision", "3", "--out", "pinned.json")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(self.cli(*args, "--out", "default.json").returncode, 0)
        pinned = json.loads((self.root / "pinned.json").read_text())
        self.assertEqual(pinned, json.loads((self.root / "default.json").read_text()))
        self.assertEqual(pinned["lineage"][0]["context"]["revision"], 3)
        self.assertIn("outcome_unknown", pinned["lineage"][0]["holds"])
        self.assertFalse(pinned["retry_authorized"])
        self.assertEqual(self.db.read_bytes(), before)

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

    def test_backup_rejects_missing_or_cyclic_parent_without_publishing(self):
        # Recomputed row hashes alone cannot establish valid Hermes dependencies.
        for parent in ("missing-parent", "cli-task"):
            with self.subTest(parent=parent):
                with HandoffLedger(self.db) as ledger:
                    row, body = ledger._handoff("cli-task")
                    body.update(parent_id=parent, depth=1)
                    ledger.db.execute("UPDATE handoffs SET body=?,digest=? WHERE id=?",
                        (json.dumps(body), digest(body), "cli-task"))
                before = self.db.read_bytes()
                output = parent + ".sqlite3"
                result = self.cli("backup-ledger", "--out", output)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertFalse((self.root / output).exists())
                self.assertFalse(list(self.root.glob(".jarvis-backup-*")))
                self.assertEqual(self.db.read_bytes(), before)

    def test_backup_rejects_inconsistent_context_review_bindings_without_publication(self):
        self.controlled(execution="outcome_unknown")
        with HandoffLedger(self.db) as ledger:
            checksum = ledger._context("cli-task")[0]["digest"]
        cases = [(None, checksum), ("cli-pilot.builder", checksum), ("../reviewer", checksum),
                 ("local-reviewer", "0" * 64), ("local-reviewer", None)]
        for index, (reviewer, reviewed) in enumerate(cases):
            with self.subTest(reviewer=reviewer, reviewed=reviewed):
                with HandoffLedger(self.db) as ledger:
                    ledger.db.execute("UPDATE handoff_contexts SET reviewer_id=?,reviewed_digest=? WHERE handoff_id='cli-task'",
                                      (reviewer, reviewed))
                before = self.db.read_bytes()
                output = f"invalid-context-review-{index}.sqlite3"
                result = self.cli("backup-ledger", "--out", output)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("review", result.stderr)
                self.assertFalse((self.root / output).exists())
                self.assertFalse(list(self.root.glob(".jarvis-backup-*")))
                self.assertEqual(self.db.read_bytes(), before)

    def test_backup_rejects_inconsistent_review_bindings_without_publication(self):
        checksum = self.profile["handoff_sha256"]
        cases = [("reviewed", None, checksum), ("reviewed", "cli-pilot.builder", checksum),
                 ("reviewed", "../reviewer", checksum), ("reviewed", "local-reviewer", "0" * 64),
                 ("pending_review", "local-reviewer", checksum)]
        for index, (state, reviewer, reviewed) in enumerate(cases):
            with self.subTest(state=state, reviewer=reviewer, reviewed=reviewed):
                with HandoffLedger(self.db) as ledger:
                    ledger.db.execute("UPDATE handoffs SET state=?,reviewer_id=?,reviewed_digest=? WHERE id='cli-task'",
                                      (state, reviewer, reviewed))
                before = self.db.read_bytes()
                output = f"invalid-review-{index}.sqlite3"
                result = self.cli("backup-ledger", "--out", output)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("review", result.stderr)
                self.assertFalse((self.root / output).exists())
                self.assertFalse(list(self.root.glob(".jarvis-backup-*")))
                self.assertEqual(self.db.read_bytes(), before)

    def test_backup_rejects_rehashed_invalid_depth_without_publishing(self):
        for index, depth in enumerate((True, -1, 2, "0", None, 1)):
            with self.subTest(depth=depth):
                with HandoffLedger(self.db) as ledger:
                    row = ledger.db.execute("SELECT body FROM handoffs WHERE id='cli-task'").fetchone()
                    body = json.loads(row["body"])
                    body["depth"] = depth
                    ledger.db.execute("UPDATE handoffs SET body=?,digest=? WHERE id=?",
                        (json.dumps(body), digest(body), "cli-task"))
                before = self.db.read_bytes()
                output = f"invalid-depth-{index}.sqlite3"
                result = self.cli("backup-ledger", "--out", output)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("depth", result.stderr)
                self.assertFalse((self.root / output).exists())
                self.assertFalse(list(self.root.glob(".jarvis-backup-*")))
                self.assertEqual(self.db.read_bytes(), before)

    def test_backup_retains_valid_child_with_held_parent_and_history(self):
        with HandoffLedger(self.db) as ledger:
            manifest = build_swarm("ai-jarvis", ["codex"], swarm_id="cli-pilot", source_revision=REVISION)
            parent_digest = self.profile["handoff_sha256"]
            ledger.review("cli-task", reviewer_id="local-reviewer", expected_sha256=parent_digest)
            ledger.export("cli-task", expected_sha256=parent_digest)
            ledger.import_return(dict(schema_version=1, kind="jarvis.return", return_id="parent-return",
                handoff_id="cli-task", handoff_sha256=parent_digest, source_provider="codex",
                text="Synthetic unverified parent return.", evidence_urls=[]))
            ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
                target="codex", text="Synthetic bounded follow-up."), manifest,
                assistant_id="cli-pilot.builder", handoff_id="child-task", parent_id="cli-task")
            self.profile.update(schema_version=2,
                control=dict(state="paused", actor_id="local-controller", reason="Retain parent hold."))
            self.profile["execution"]["state"] = "outcome_unknown"
            saved = ledger.save_context(self.profile, expected_revision=0)
            ledger.checkpoint_context("cli-task", expected_sha256=saved["context_sha256"],
                expected_source_revision=REVISION, expected_memory_revision=1)
        before = self.db.read_bytes()
        result = self.cli("backup-ledger", "--out", "valid-parent.sqlite3")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.db.read_bytes(), before)
        with HandoffLedger(self.root / "valid-parent.sqlite3", read_only=True) as restored:
            self.assertEqual([row["id"] for row, _ in restored._lineage("child-task")],
                             ["child-task", "cli-task"])
            self.assertEqual(restored.load_context("cli-task", expected_source_revision=REVISION,
                expected_memory_revision=1)["profile"], self.profile)
            self.assertEqual(len(restored.list_checkpoints("cli-task")["checkpoints"]), 1)
            self.assertEqual(restored.status()["return_count"], 1)
            with self.assertRaisesRegex(ValueError, "unknown outcome"):
                restored.export("child-task", expected_sha256=restored._handoff("child-task")[0]["digest"])

    def test_backup_rejects_parent_from_another_swarm_or_source(self):
        for index, revision in enumerate((REVISION, "f" * 40)):
            with self.subTest(source=revision):
                with HandoffLedger(self.db) as ledger:
                    swarm = f"unrelated-{index}"
                    parent = f"unrelated-parent-{index}"
                    manifest = build_swarm("ai-jarvis", ["codex"], swarm_id=swarm,
                                           source_revision=revision)
                    ledger.stage(dict(schema_version=1, kind="jarvis.draft", project_id="ai-jarvis",
                        target="codex", text="Independent synthetic mission."), manifest,
                        assistant_id=swarm + ".builder", handoff_id=parent)
                    _, body = ledger._handoff("cli-task")
                    body.update(parent_id=parent, depth=1)
                    ledger.db.execute("UPDATE handoffs SET body=?,digest=? WHERE id=?",
                        (json.dumps(body), digest(body), "cli-task"))
                before = self.db.read_bytes()
                output = f"wrong-scope-{index}.sqlite3"
                result = self.cli("backup-ledger", "--out", output)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("ancestry scope", result.stderr)
                self.assertFalse((self.root / output).exists())
                self.assertFalse(list(self.root.glob(".jarvis-backup-*")))
                self.assertEqual(self.db.read_bytes(), before)

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

    def test_capture_revision_cli_rejects_restored_selection_before_upgrade(self):
        checksum = self.controlled(execution="outcome_unknown")
        changed = deepcopy(self.profile)
        changed["execution"]["detail"] = "Temporary private capture edit."
        self.write(changed)
        self.assertEqual(self.save(revision=1).returncode, 0)
        self.write(self.profile)
        self.assertEqual(self.save(revision=2).returncode, 0)
        args = ("capture-checkpoint", "--allow-schema-upgrade", "--handoff", "cli-task",
                "--digest", checksum, "--source-revision", REVISION, "--memory-revision", "1")
        before = self.control_snapshot()
        for revision in ("1", "2", "4", "0", "-1"):
            rejected = self.cli(*args, "--context-revision", revision)
            self.assertEqual(rejected.returncode, 1, rejected.stderr)
            self.assertIn("checkpoint revision", rejected.stderr)
            self.assertEqual(self.control_snapshot(), before)
        accepted = self.cli(*args, "--context-revision", "3")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout)["checkpoint_revision"], 3)
        self.assertFalse(json.loads(accepted.stdout)["duplicate"])
        before = self.control_snapshot()
        for options in (("--context-revision", "3"), ()):
            duplicate = self.cli(*args, *options)
            self.assertEqual(duplicate.returncode, 0, duplicate.stderr)
            self.assertTrue(json.loads(duplicate.stdout)["duplicate"])
            self.assertEqual(self.control_snapshot(), before)
        with HandoffLedger(self.db, read_only=True) as restarted:
            current = restarted.load_context("cli-task", expected_source_revision=REVISION,
                                            expected_memory_revision=1, expected_revision=3)
            history = restarted.load_checkpoint("cli-task", 3, expected_sha256=checksum,
                expected_source_revision=REVISION, expected_memory_revision=1)
            self.assertEqual(current["profile"], self.profile)
            self.assertEqual(history["profile"], self.profile)
            self.assertEqual(current["review_state"], "proposed")
            self.assertFalse(history["retry_authorized"])

    def test_load_context_digest_cli_rejects_same_memory_edit_before_output(self):
        checksum = self.controlled(execution="outcome_unknown")
        self.profile["execution"]["detail"] = "Changed private detail without changing memory revision."
        self.write(self.profile)
        changed = self.save(revision=1)
        self.assertEqual(changed.returncode, 0, changed.stderr)
        fresh_digest = json.loads(changed.stdout)["context_sha256"]
        before = self.db.read_bytes()
        args = ("--read-only", "load-context", "--handoff", "cli-task", "--source-revision", REVISION,
                "--memory-revision", "1")
        for value in (checksum, "bad"):
            rejected = self.cli(*args, "--digest", value, "--out", "rejected/context.json")
            self.assertEqual(rejected.returncode, 1, rejected.stderr)
            self.assertFalse((self.root / "rejected").exists())
            self.assertNotIn("Changed private detail", rejected.stderr + rejected.stdout)
        accepted = self.cli(*args, "--digest", fresh_digest, "--out", "private/context.json")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        output = self.root / "private/context.json"
        content = output.read_bytes()
        self.assertEqual(json.loads(content)["profile"], self.profile)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.cli(*args, "--digest", fresh_digest, "--out", "private/context.json").returncode, 1)
        self.assertEqual(output.read_bytes(), content)
        legacy = self.cli(*args, "--out", "legacy.json")
        self.assertEqual(legacy.returncode, 0, legacy.stderr)
        self.assertEqual((self.root / "legacy.json").read_bytes(), content)
        self.assertEqual(self.db.read_bytes(), before)

    def test_load_context_revision_cli_rejects_restored_content_before_output(self):
        checksum = self.controlled(execution="outcome_unknown")
        changed = deepcopy(self.profile)
        changed["execution"]["detail"] = "Temporary private retrieval edit."
        self.write(changed)
        self.assertEqual(self.save(revision=1).returncode, 0)
        self.write(self.profile)
        restored = self.save(revision=2)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(json.loads(restored.stdout)["context_sha256"], checksum)
        before = self.db.read_bytes()
        args = ("--read-only", "load-context", "--handoff", "cli-task", "--source-revision", REVISION,
                "--memory-revision", "1", "--digest", checksum)
        for revision in ("1", "2", "4", "0", "-1"):
            rejected = self.cli(*args, "--context-revision", revision, "--out", "rejected/context.json")
            self.assertEqual(rejected.returncode, 1, rejected.stderr)
            self.assertIn("context retrieval revision", rejected.stderr)
            self.assertFalse((self.root / "rejected").exists())
            self.assertNotIn("Temporary private", rejected.stderr + rejected.stdout)
        invalid = self.cli(*args, "--context-revision", "not-an-integer", "--out", "rejected/context.json")
        self.assertEqual(invalid.returncode, 2)
        self.assertFalse((self.root / "rejected").exists())
        accepted = self.cli(*args, "--context-revision", "3", "--out", "private/context.json")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        output = self.root / "private/context.json"
        content = output.read_bytes()
        record = json.loads(content)
        self.assertEqual(record["revision"], 3)
        self.assertEqual(record["profile"], self.profile)
        self.assertEqual(record["review_state"], "proposed")
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.cli(*args, "--context-revision", "3", "--out", "private/context.json").returncode, 1)
        self.assertEqual(output.read_bytes(), content)
        legacy = self.cli(*args, "--out", "legacy.json")
        self.assertEqual(legacy.returncode, 0, legacy.stderr)
        self.assertEqual((self.root / "legacy.json").read_bytes(), content)
        self.assertEqual(self.db.read_bytes(), before)

    def test_context_review_revision_cli_rejects_restored_content_without_changing_holds(self):
        checksum = self.controlled(execution="outcome_unknown")
        changed = {**self.profile, "execution": {**self.profile["execution"], "detail": "Temporary private edit."}}
        self.write(changed)
        self.assertEqual(self.save(revision=1).returncode, 0)
        self.write(self.profile)
        restored = self.save(revision=2)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(json.loads(restored.stdout)["context_sha256"], checksum)
        with HandoffLedger(self.db, read_only=True) as ledger:
            before = list(ledger.db.iterdump())
        args = ("review-context", "--handoff", "cli-task", "--reviewer", "local-reviewer", "--digest", checksum)
        for revision in ("1", "2", "4", "0", "-1"):
            rejected = self.cli(*args, "--context-revision", revision)
            self.assertEqual(rejected.returncode, 1, rejected.stderr)
            self.assertNotIn("Temporary private", rejected.stderr + rejected.stdout)
            # Writable CLI startup may update SQLite's schema-version header;
            # rejected review must preserve every logical record and hold.
            with HandoffLedger(self.db, read_only=True) as ledger:
                self.assertEqual(list(ledger.db.iterdump()), before)
        with HandoffLedger(self.db, read_only=True) as ledger:
            self.assertEqual(ledger.load_context("cli-task", expected_source_revision=REVISION,
                expected_memory_revision=1)["review_state"], "proposed")
        accepted = self.cli(*args, "--context-revision", "3")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout)["authority"], "local_record_only_not_identity_authentication")
        with HandoffLedger(self.db, read_only=True) as ledger:
            current = ledger.load_context("cli-task", expected_source_revision=REVISION, expected_memory_revision=1)
            self.assertEqual(current["review_state"], "locally_reviewed")
            self.assertEqual(current["profile"], self.profile)
        self.assertEqual(self.cli(*args).returncode, 0)

    def test_context_review_receipt_cli_is_explicit_and_keeps_legacy_response(self):
        checksum = self.controlled(execution="outcome_unknown")
        args = ("review-context", "--handoff", "cli-task", "--reviewer", "local-reviewer", "--digest", checksum)
        with HandoffLedger(self.db, read_only=True) as ledger:
            before = list(ledger.db.iterdump())
        rejected = self.cli(*args, "--include-receipt")
        self.assertEqual(rejected.returncode, 1, rejected.stderr)
        self.assertNotIn("jarvis.context_review_receipt", rejected.stdout)
        with HandoffLedger(self.db, read_only=True) as ledger:
            self.assertEqual(list(ledger.db.iterdump()), before)
        accepted = self.cli(*args, "--context-revision", "1", "--include-receipt")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        receipt = json.loads(accepted.stdout)
        self.assertEqual(receipt["kind"], "jarvis.context_review_receipt")
        self.assertEqual((receipt["context_revision"], receipt["memory_revision"]), (1, 1))
        self.assertEqual(receipt["source_revision"], REVISION)
        self.assertEqual(receipt["context_sha256"], checksum)
        self.assertEqual(receipt["platform"], "codex")
        self.assertEqual(receipt["visibility"], "owner_private")
        self.assertEqual(receipt["authority"], "local_record_only_not_identity_authentication")
        self.assertEqual(receipt["receipt_sha256"], digest({k: v for k, v in receipt.items() if k != "receipt_sha256"}))
        self.assertFalse(receipt["dispatch_authorized"])
        self.assertFalse(receipt["retry_authorized"])
        self.assertNotIn("https://", accepted.stdout)
        old = self.cli(*args, "--context-revision", "1")
        self.assertEqual(old.returncode, 0, old.stderr)
        self.assertEqual(set(json.loads(old.stdout)), {"handoff_id", "context_sha256", "review_state", "external_actions", "authority"})
        with HandoffLedger(self.db, read_only=True) as ledger:
            self.assertEqual(ledger.load_context("cli-task", expected_source_revision=REVISION,
                expected_memory_revision=1)["profile"], self.profile)

    def test_context_review_receipt_saves_private_exact_record_without_profile_text(self):
        checksum = self.controlled(execution="outcome_unknown")
        args = ("review-context", "--handoff", "cli-task", "--reviewer", "local-reviewer", "--digest", checksum,
                "--context-revision", "1", "--include-receipt", "--out", "private/review.json")
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"saved": "private/review.json", "external_actions": 0})
        path = self.root / "private/review.json"
        before = path.read_bytes()
        receipt = json.loads(before)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(receipt["kind"], "jarvis.context_review_receipt")
        self.assertEqual(receipt["context_sha256"], checksum)
        self.assertEqual(receipt["context_revision"], 1)
        self.assertEqual(receipt["receipt_sha256"], digest({k: v for k, v in receipt.items() if k != "receipt_sha256"}))
        self.assertEqual(receipt["visibility"], "owner_private")
        self.assertFalse(receipt["dispatch_authorized"])
        self.assertFalse(receipt["retry_authorized"])
        self.assertNotIn("https://", before.decode())
        self.assertNotIn("context_sha256", result.stdout)
        with HandoffLedger(self.db, read_only=True) as ledger:
            rows = list(ledger.db.iterdump())
            current = ledger.load_context("cli-task", expected_source_revision=REVISION, expected_memory_revision=1)
            self.assertEqual(current["review_state"], "locally_reviewed")
            self.assertEqual(current["profile"], self.profile)
        self.assertEqual(self.cli(*args).returncode, 1)
        self.assertEqual(path.read_bytes(), before)
        with HandoffLedger(self.db, read_only=True) as ledger:
            self.assertEqual(list(ledger.db.iterdump()), rows)

    def test_context_review_receipt_output_guards_precede_ledger_mutation(self):
        checksum = self.controlled(execution="outcome_unknown")
        args = ("review-context", "--handoff", "cli-task", "--reviewer", "local-reviewer", "--digest", checksum)
        with HandoffLedger(self.db, read_only=True) as ledger:
            rows = list(ledger.db.iterdump())
        cases = [("--out", "rejected/no-flags.json"),
                 ("--context-revision", "1", "--out", "rejected/no-receipt.json"),
                 ("--include-receipt", "--out", "rejected/no-revision.json"),
                 ("--include-receipt", "--context-revision", "2", "--out", "rejected/stale.json"),
                 ("--include-receipt", "--context-revision", "1", "--out", "../escape.json")]
        for flags in cases:
            with self.subTest(flags=flags):
                result = self.cli(*args, *flags)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, "")
                with HandoffLedger(self.db, read_only=True) as ledger:
                    self.assertEqual(list(ledger.db.iterdump()), rows)
        self.assertFalse((self.root / "rejected").exists())

    @unittest.skipUnless(os.name == "posix", "directory fsync is POSIX-specific")
    def test_review_receipt_fsync_failures_retain_review_and_reconcilable_output(self):
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        from scripts.jarvis_network import main
        real_fsync = os.fsync
        checksum = self.controlled(execution="outcome_unknown")
        for fail_at in (1, 2):
            with self.subTest(fsync_call=fail_at):
                if fail_at == 2:
                    self.profile["execution"]["detail"] = "Second private receipt attempt."
                    self.write(self.profile)
                    checksum = json.loads(self.save(revision=1).stdout)["context_sha256"]
                output = self.root / f"private/receipt-{fail_at}.json"
                args = ["review-context", "--handoff", "cli-task", "--reviewer", "local-reviewer",
                    "--digest", checksum, "--context-revision", str(fail_at), "--include-receipt",
                    "--out", str(output.relative_to(self.root))]
                calls = []

                def fail_fsync(fd):
                    calls.append(fd)
                    if len(calls) == fail_at:
                        raise OSError("Synthetic private path detail must not escape.")
                    return real_fsync(fd)

                stdout, stderr = StringIO(), StringIO()
                with patch("scripts.jarvis_network.os.fsync", side_effect=fail_fsync), \
                        redirect_stdout(stdout), redirect_stderr(stderr):
                    code = main(["--root", str(self.root), "--database", "ledger.sqlite3", *args])
                self.assertEqual(code, 1)
                self.assertEqual(len(calls), fail_at)  # No implicit replay.
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(json.loads(stderr.getvalue()), {"error": "OSError", "external_actions": 0})
                self.assertEqual(list(output.parent.glob(".jarvis-write-*")), [])
                with HandoffLedger(self.db, read_only=True) as ledger:
                    rows = list(ledger.db.iterdump())
                    current = ledger.load_context("cli-task", expected_source_revision=REVISION,
                                                  expected_memory_revision=1)
                    self.assertEqual(current["review_state"], "locally_reviewed")
                    self.assertEqual(current["profile"], self.profile)
                if fail_at == 1:
                    self.assertFalse(output.exists())
                else:
                    content = output.read_bytes()
                    receipt = json.loads(content)
                    self.assertEqual(output.stat().st_mode & 0o777, 0o600)
                    self.assertEqual(receipt["context_sha256"], checksum)
                    self.assertEqual(receipt["context_revision"], 2)
                    self.assertEqual(receipt["receipt_sha256"], digest({k: v for k, v in receipt.items() if k != "receipt_sha256"}))
                    self.assertFalse(receipt["dispatch_authorized"])
                    self.assertFalse(receipt["retry_authorized"])
                    self.assertEqual(self.cli(*args).returncode, 1)
                    self.assertEqual(output.read_bytes(), content)
                    with HandoffLedger(self.db, read_only=True) as ledger:
                        self.assertEqual(list(ledger.db.iterdump()), rows)

    @unittest.skipUnless(os.name == "posix", "directory fsync is POSIX-specific")
    def test_export_fsync_failures_retain_committed_state_and_reconcilable_file(self):
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        from scripts.jarvis_network import main
        checksum = self.controlled()
        with HandoffLedger(self.db) as ledger:
            ledger.review("cli-task", reviewer_id="local-reviewer",
                          expected_sha256=self.profile["handoff_sha256"])
            ledger.review_context("cli-task", reviewer_id="local-reviewer",
                                  expected_sha256=checksum, expected_revision=1)
        seed_bytes = self.db.read_bytes()
        real_fsync = os.fsync
        for fail_at in (1, 2):
            with self.subTest(fsync_call=fail_at):
                database = f"export-{fail_at}.sqlite3"
                case_db = self.root / database
                case_db.write_bytes(seed_bytes)
                output = self.root / f"private/export-{fail_at}.json"
                args = ["export-context", "--handoff", "cli-task", "--digest", checksum,
                    "--source-revision", REVISION, "--memory-revision", "1",
                    "--context-revision", "1", "--out", str(output.relative_to(self.root))]
                calls = []

                def fail_fsync(fd):
                    calls.append(fd)
                    if len(calls) == fail_at:
                        raise OSError("Synthetic private export path must not escape.")
                    return real_fsync(fd)

                stdout, stderr = StringIO(), StringIO()
                with patch("scripts.jarvis_network.os.fsync", side_effect=fail_fsync), \
                        redirect_stdout(stdout), redirect_stderr(stderr):
                    code = main(["--root", str(self.root), "--database", database, *args])
                self.assertEqual(code, 1)
                self.assertEqual(len(calls), fail_at)  # No automatic replay.
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(json.loads(stderr.getvalue()), {"error": "OSError", "external_actions": 0})
                self.assertEqual(list(output.parent.glob(".jarvis-write-*")), [])
                with HandoffLedger(case_db, read_only=True) as ledger:
                    rows = tuple(ledger.db.iterdump())
                    self.assertEqual(ledger._handoff("cli-task")[0]["state"], "export_prepared")
                    current = ledger.load_context("cli-task", expected_source_revision=REVISION,
                        expected_memory_revision=1, expected_revision=1)
                    self.assertEqual(current["profile"], self.profile)
                    self.assertEqual(current["review_state"], "locally_reviewed")
                if fail_at == 1:
                    self.assertFalse(output.exists())
                else:
                    content = output.read_bytes()
                    packet = json.loads(content)
                    self.assertEqual(packet["context"], self.profile)
                    self.assertEqual(packet["context_sha256"], checksum)
                    self.assertEqual(packet["context_revision"], 1)
                    self.assertEqual(packet["handoff_sha256"], self.profile["handoff_sha256"])
                    self.assertEqual(packet["external_actions"], 0)
                    self.assertEqual(output.stat().st_mode & 0o777, 0o600)
                    self.assertEqual(self.cli(*args, database=database).returncode, 1)
                    self.assertEqual(output.read_bytes(), content)
                    with HandoffLedger(case_db, read_only=True) as ledger:
                        self.assertEqual(tuple(ledger.db.iterdump()), rows)
                self.assertEqual(self.db.read_bytes(), seed_bytes)

    def test_saved_review_check_cli_reopens_without_ledger_or_receipt_writes(self):
        checksum = self.controlled(execution="outcome_unknown")
        created = self.cli("review-context", "--handoff", "cli-task", "--reviewer", "local-reviewer",
            "--digest", checksum, "--context-revision", "1", "--include-receipt", "--out", "receipt.json")
        self.assertEqual(created.returncode, 0, created.stderr)
        before = self.db.read_bytes(), (self.root / "receipt.json").read_bytes()
        args = ("check-review-receipt", "--handoff", "cli-task", "--file", "receipt.json")
        first = self.cli(*args)
        self.assertEqual(first.returncode, 0, first.stderr)
        checked = json.loads(first.stdout)
        self.assertEqual(checked["kind"], "jarvis.context_review_check")
        self.assertTrue(checked["local_binding_matches"])
        self.assertEqual(checked["receipt_sha256"], json.loads(before[1])["receipt_sha256"])
        self.assertFalse(checked["dispatch_authorized"])
        self.assertFalse(checked["retry_authorized"])
        self.assertNotIn("https://", first.stdout)
        self.assertNotIn("local-reviewer", first.stdout)
        saved = self.cli("--read-only", *args, "--out", "private/check.json")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        output = self.root / "private/check.json"
        self.assertEqual(json.loads(output.read_text()), checked)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.cli(*args, "--out", "private/check.json").returncode, 1)
        self.assertEqual(json.loads(output.read_text()), checked)
        self.assertEqual((self.db.read_bytes(), (self.root / "receipt.json").read_bytes()), before)

    def test_saved_review_check_cli_can_pin_one_exact_receipt(self):
        checksum = self.controlled(execution="outcome_unknown")
        reviewed = self.cli("review-context", "--handoff", "cli-task", "--reviewer", "local-reviewer",
            "--digest", checksum, "--context-revision", "1", "--include-receipt")
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        receipt = json.loads(reviewed.stdout)
        path = self.root / "receipt.json"
        path.write_text(reviewed.stdout)
        args = ["check-review-receipt", "--handoff", "cli-task", "--file", "receipt.json"]
        before = self.db.read_bytes()
        original = self.cli("--read-only", *args, "--receipt-digest", receipt["receipt_sha256"])
        self.assertEqual(original.returncode, 0, original.stderr)
        self.assertEqual(json.loads(original.stdout)["receipt_sha256"], receipt["receipt_sha256"])
        # Timestamp is not archived/attested. A different internally consistent
        # receipt remains acceptable by default, but is not the pinned receipt.
        replacement = {**receipt, "recorded_at": "2001-01-01T00:00:00+00:00"}
        replacement["receipt_sha256"] = digest({k: v for k, v in replacement.items() if k != "receipt_sha256"})
        path.write_text(json.dumps(replacement))
        self.assertEqual(self.cli(*args).returncode, 0)
        for expected in (receipt["receipt_sha256"], "0" * 64, "invalid"):
            rejected = self.cli(*args, "--receipt-digest", expected, "--out", "rejected/check.json")
            self.assertEqual(rejected.returncode, 1, rejected.stderr)
            self.assertEqual(rejected.stdout, "")
        from scripts.jarvis_network import main
        with patch("scripts.jarvis_network.HandoffLedger") as opened:
            self.assertEqual(main(["--root", str(self.root), *args,
                "--receipt-digest", receipt["receipt_sha256"]]), 1)
            opened.assert_not_called()
        accepted = self.cli(*args, "--receipt-digest", replacement["receipt_sha256"], "--out", "private/pinned.json")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        checked = json.loads((self.root / "private/pinned.json").read_text())
        self.assertEqual(checked["receipt_sha256"], replacement["receipt_sha256"])
        self.assertFalse(checked["dispatch_authorized"])
        self.assertFalse(checked["retry_authorized"])
        self.assertFalse((self.root / "rejected").exists())
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(json.loads(path.read_text()), replacement)

    def test_saved_review_check_cli_rejects_bad_input_missing_ledger_and_stale_receipt(self):
        checksum = self.controlled(execution="outcome_unknown")
        reviewed = self.cli("review-context", "--handoff", "cli-task", "--reviewer", "local-reviewer",
            "--digest", checksum, "--context-revision", "1", "--include-receipt")
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        receipt = json.loads(reviewed.stdout)
        (self.root / "receipt.json").write_text(reviewed.stdout)
        args = ("check-review-receipt", "--handoff", "cli-task", "--file", "receipt.json")
        before = self.db.read_bytes()
        missing = self.cli(*args, "--out", "rejected/check.json", database="absent/ledger.sqlite3")
        self.assertEqual(missing.returncode, 1)
        self.assertFalse((self.root / "absent").exists())
        for raw in ('{"kind":"one","kind":"two"}', json.dumps({**receipt, "receipt_sha256": "0" * 64})):
            (self.root / "bad.json").write_text(raw)
            result = self.cli("--read-only", "check-review-receipt", "--handoff", "cli-task",
                "--file", "bad.json", "--out", "rejected/check.json")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(result.stdout, "")
        self.assertEqual(self.db.read_bytes(), before)
        self.assertFalse((self.root / "rejected").exists())
        self.profile["execution"]["detail"] = "Later context invalidates the old receipt."
        self.write(self.profile)
        self.assertEqual(self.save(revision=1).returncode, 0)
        before = self.db.read_bytes()
        stale = self.cli(*args, "--out", "rejected/stale.json")
        self.assertEqual(stale.returncode, 1, stale.stderr)
        self.assertEqual(stale.stdout, "")
        self.assertFalse((self.root / "rejected").exists())
        self.assertEqual(self.db.read_bytes(), before)

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

    def test_destination_mission_cli_retains_private_selection_and_rejects_stale_scope(self):
        self.profile.update(schema_version=3, destination_id="repo-one",
            control=dict(state="paused", actor_id="local-owner", reason="Synthetic private hold."))
        self.profile["execution"]["state"] = "outcome_unknown"
        self.write(self.profile)
        self.assertEqual(self.save().returncode, 0)
        args = ("--read-only", "destination-status", "--project", "ai-jarvis", "--platform", "codex", "--destination", "repo-one")
        first = self.cli(*args, "--mission", "cli-task")
        self.assertEqual(first.returncode, 0, first.stderr)
        report = json.loads(first.stdout)
        self.assertEqual((report["schema_version"], report["mission_id"]), (3, "cli-task"))
        before = self.db.read_bytes()
        for suffix in (("--mission", "other-task"), (), ("--mission", "../bad")):
            rejected = self.cli(*args, *suffix, "--expected-report-digest", report["report_sha256"], "--out", "stale/mission.json")
            self.assertEqual(rejected.returncode, 1)
            self.assertFalse((self.root / "stale").exists())
        saved = self.cli(*args, "--mission", "cli-task", "--expected-report-digest", report["report_sha256"], "--out", "private/mission.json")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        output = self.root / "private/mission.json"
        self.assertEqual(json.loads(output.read_text()), report)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(report["records"][0]["control_state"], "paused")
        self.assertEqual(report["records"][0]["execution_state"], "outcome_unknown")
        self.assertFalse(report["dispatch_authorized"])
        self.assertEqual(self.db.read_bytes(), before)

    def test_destination_review_cli_stale_gate_and_private_output(self):
        self.profile.update(schema_version=3, destination_id="repo-one",
            control=dict(state="paused", actor_id="local-owner", reason="Synthetic private hold."))
        self.profile["execution"]["state"] = "outcome_unknown"
        self.write(self.profile)
        self.assertEqual(self.save().returncode, 0)
        args = ("--read-only", "destination-status", "--project", "ai-jarvis", "--platform", "codex",
                "--destination", "repo-one", "--mission", "cli-task", "--include-review-state")
        first = self.cli(*args)
        self.assertEqual(first.returncode, 0, first.stderr)
        old = json.loads(first.stdout)
        with HandoffLedger(self.db) as ledger:
            checksum = ledger.load_context("cli-task", expected_source_revision=REVISION, expected_memory_revision=1)["context_sha256"]
            ledger.review_context("cli-task", reviewer_id="local-evaluator", expected_sha256=checksum)
        before = self.db.read_bytes()
        stale = self.cli(*args, "--expected-report-digest", old["report_sha256"], "--out", "stale/report.json")
        self.assertEqual(stale.returncode, 1)
        self.assertIn("destination report is stale", stale.stderr)
        self.assertFalse((self.root / "stale").exists())
        fresh = json.loads(self.cli(*args).stdout)
        written = self.cli(*args, "--expected-report-digest", fresh["report_sha256"], "--out", "private/report.json")
        self.assertEqual(written.returncode, 0, written.stderr)
        output = self.root / "private/report.json"
        self.assertEqual(json.loads(output.read_text()), fresh)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        retained = output.read_bytes()
        self.assertEqual(self.cli(*args, "--out", "private/report.json").returncode, 1)
        self.assertEqual(output.read_bytes(), retained)
        row = fresh["records"][0]
        self.assertEqual((fresh["schema_version"], row["handoff_review_current"], row["context_review_current"]), (4, False, True))
        self.assertEqual((row["control_state"], row["execution_state"]), ("paused", "outcome_unknown"))
        self.assertFalse(fresh["dispatch_authorized"])
        self.assertEqual(self.db.read_bytes(), before)

    def test_destination_snapshot_cli_rejects_before_output_and_preserves_holds(self):
        self.profile.update(schema_version=3, destination_id="repo-one",
            control=dict(state="paused", actor_id="local-owner", reason="Synthetic private hold."))
        self.profile["execution"]["state"] = "outcome_unknown"
        self.write(self.profile)
        self.assertEqual(self.save().returncode, 0)
        args = ("--read-only", "destination-status", "--project", "ai-jarvis", "--platform", "codex", "--destination", "repo-one")
        observed = self.cli(*args, "--include-digest")
        self.assertEqual(observed.returncode, 0, observed.stderr)
        first = json.loads(observed.stdout)
        self.profile["execution"]["detail"] = "Changed private evidence; retain unknown outcome."
        self.write(self.profile)
        self.assertEqual(self.save(1).returncode, 0)
        before = self.db.read_bytes()
        stale = self.cli(*args, "--expected-report-digest", first["report_sha256"], "--out", "stale/destination.json")
        self.assertEqual(stale.returncode, 1)
        self.assertIn("destination report is stale", stale.stderr)
        self.assertFalse((self.root / "stale").exists())
        fresh = json.loads(self.cli(*args, "--include-digest").stdout)
        written = self.cli(*args, "--expected-report-digest", fresh["report_sha256"], "--out", "private/destination.json")
        self.assertEqual(written.returncode, 0, written.stderr)
        output = self.root / "private/destination.json"
        self.assertEqual(json.loads(output.read_text()), fresh)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        retained = output.read_bytes()
        self.assertEqual(self.cli(*args, "--expected-report-digest", fresh["report_sha256"], "--out", "private/destination.json").returncode, 1)
        self.assertEqual(output.read_bytes(), retained)
        self.assertEqual(fresh["records"][0]["execution_state"], "outcome_unknown")
        self.assertEqual(fresh["records"][0]["control_state"], "paused")
        self.assertFalse(fresh["dispatch_authorized"])
        self.assertEqual(self.db.read_bytes(), before)

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

    @unittest.skipUnless(os.name == "posix", "directory fsync is POSIX-specific")
    def test_backup_fsync_failures_preserve_source_and_reconcilable_output(self):
        self.controlled(execution="outcome_unknown")
        self.profile["control"]["state"] = "paused"
        self.write(self.profile)
        saved = self.save(1)
        self.assertEqual(saved.returncode, 0, saved.stderr)
        checksum = json.loads(saved.stdout)["context_sha256"]
        self.assertEqual(self.review_context(checksum).returncode, 0)
        source_bytes = self.db.read_bytes()
        real_fsync = os.fsync
        with HandoffLedger(self.db, read_only=True) as source:
            rows = tuple(source.db.iterdump())
            for fail_at in (1, 2):
                with self.subTest(fsync_call=fail_at):
                    target = self.root / f"private/backup-{fail_at}.sqlite3"
                    failure = OSError("Synthetic backup synchronization failure")
                    calls, returned = [], []

                    def fail_fsync(fd):
                        calls.append(fd)
                        if len(calls) == fail_at:
                            raise failure
                        return real_fsync(fd)

                    with patch("scripts.jarvis_network.os.fsync", side_effect=fail_fsync):
                        with self.assertRaises(OSError) as raised:
                            returned.append(_backup(source.db, target))
                    self.assertIs(raised.exception, failure)
                    self.assertEqual(returned, [])
                    self.assertEqual(len(calls), fail_at)  # No automatic replay.
                    self.assertFalse(list(target.parent.glob(".jarvis-backup-*")))
                    self.assertEqual(self.db.read_bytes(), source_bytes)
                    self.assertEqual(tuple(source.db.iterdump()), rows)
                    if fail_at == 1:
                        self.assertFalse(target.exists())
                    else:
                        content = target.read_bytes()
                        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
                        with HandoffLedger(target, read_only=True) as restored:
                            self.assertEqual(tuple(restored.db.iterdump()), rows)
                            current = restored.load_context("cli-task", expected_source_revision=REVISION,
                                expected_memory_revision=1, expected_revision=2)
                            self.assertEqual(current["profile"], self.profile)
                            self.assertEqual(current["review_state"], "locally_reviewed")
                            with self.assertRaises(ValueError):
                                restored.export_context("cli-task", expected_sha256=checksum,
                                    expected_source_revision=REVISION, expected_memory_revision=1,
                                    expected_revision=2)
                        with self.assertRaises(FileExistsError):
                            _backup(source.db, target)
                        self.assertEqual(target.read_bytes(), content)
                        self.assertFalse(list(target.parent.glob(".jarvis-backup-*")))
                        self.assertEqual(self.db.read_bytes(), source_bytes)
                        self.assertEqual(tuple(source.db.iterdump()), rows)

    def test_backup_digest_cli_checks_bytes_without_opening_a_ledger(self):
        self.controlled(execution="outcome_unknown")
        created = self.cli("backup-ledger", "--out", "private/backup.sqlite3")
        self.assertEqual(created.returncode, 0, created.stderr)
        checksum = json.loads(created.stdout)["backup_sha256"]
        backup = self.root / "private/backup.sqlite3"
        before = self.db.read_bytes(), backup.read_bytes()
        args = ("--read-only", "check-backup-digest", "--file", "private/backup.sqlite3", "--digest", checksum)
        result = self.cli(*args, database="absent/ledger.sqlite3")
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)
        self.assertEqual(record["backup_sha256"], checksum)
        self.assertEqual(record["bytes"], len(before[1]))
        self.assertEqual(record["ledger_validation"], "not_performed")
        self.assertFalse(record["restore_authorized"])
        self.assertFalse(record["retry_authorized"])
        self.assertEqual(record["external_actions"], 0)
        saved = self.cli(*args, "--out", "reports/check.json", database="absent/ledger.sqlite3")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        output = self.root / "reports/check.json"
        content = output.read_bytes()
        self.assertEqual(json.loads(content), record)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.cli(*args, "--out", "reports/check.json").returncode, 1)
        self.assertEqual(output.read_bytes(), content)
        self.assertEqual((self.db.read_bytes(), backup.read_bytes()), before)
        self.assertFalse((self.root / "absent").exists())

    def test_backup_digest_rejects_mismatch_bounds_and_nonregular_inputs(self):
        from scripts.jarvis_network import _check_backup_digest
        path = self.root / "retained.bin"
        path.write_bytes(b"Retained bytes are not proof of a valid ledger.")
        before = self.db.read_bytes(), path.read_bytes()
        expected = hashlib.sha256(before[1]).hexdigest()
        with patch("scripts.jarvis_network.sqlite3.connect", side_effect=AssertionError("must not open SQLite")):
            report = _check_backup_digest(path, expected)
        self.assertEqual(report["ledger_validation"], "not_performed")
        with patch("scripts.jarvis_network.os.open", side_effect=AssertionError("must validate digest first")):
            with self.assertRaises(ValueError):
                _check_backup_digest(path, "invalid")
        with patch("scripts.jarvis_network.time.monotonic", side_effect=[0, 11]):
            with self.assertRaisesRegex(ValueError, "time budget"):
                _check_backup_digest(path, expected)
        oversized = self.root / "oversized.bin"
        with oversized.open("wb") as handle:
            handle.truncate(128 * 1024 * 1024 + 1)
        candidates = [("retained.bin", "0" * 64), ("retained.bin", "invalid"),
                      ("missing.bin", expected), ("../outside.bin", expected),
                      ("oversized.bin", expected), ("reports", expected)]
        (self.root / "reports").mkdir()
        if hasattr(os, "mkfifo"):
            os.mkfifo(self.root / "pipe")
            candidates.append(("pipe", expected))
        for name, checksum in candidates:
            with self.subTest(name=name):
                result = self.cli("check-backup-digest", "--file", name, "--digest", checksum,
                                  "--out", "rejected/check.json", database="absent/ledger.sqlite3")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertFalse((self.root / "rejected").exists())
                self.assertFalse((self.root / "absent").exists())
                self.assertEqual((self.db.read_bytes(), path.read_bytes()), before)

    def test_backup_digest_rejects_final_read_finishing_after_budget(self):
        from scripts.jarvis_network import _check_backup_digest
        path = self.root / "retained.bin"
        path.write_bytes(b"Synthetic retained backup bytes")
        before = self.db.read_bytes(), path.read_bytes()
        expected = hashlib.sha256(before[1]).hexdigest()
        clock, readers = [0], []
        fdopen = os.fdopen

        def slow_eof(*args, **kwargs):
            handle = fdopen(*args, **kwargs)
            readers.append(handle)
            read = handle.read

            def delayed_read(size):
                block = read(size)
                if not block:
                    clock[0] = 11  # The final real EOF read exceeded the budget.
                return block

            handle.read = delayed_read
            return handle

        with patch("scripts.jarvis_network.os.fdopen", side_effect=slow_eof), \
             patch("scripts.jarvis_network.time.monotonic", side_effect=lambda: clock[0]), \
             patch("scripts.jarvis_network.sqlite3.connect", side_effect=AssertionError("must not open SQLite")):
            with self.assertRaisesRegex(ValueError, "time budget"):
                _check_backup_digest(path, expected)
        self.assertEqual(len(readers), 1)
        self.assertTrue(readers[0].closed)
        self.assertEqual((self.db.read_bytes(), path.read_bytes()), before)

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
