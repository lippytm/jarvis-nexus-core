from copy import deepcopy
from pathlib import Path
import json
import os
import sqlite3
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.jarvis_network import _write

from control_tower.handoffs import HandoffLedger
from control_tower.network_contract import (MAX_PACKET_BYTES, PROJECTS, TARGETS,
    digest, load_packet, validate_draft, validate_return)
from control_tower.network_demo import demonstrate_network
from control_tower.provider_catalog import provider_catalog
from control_tower.swarm_factory import ROLE_TEMPLATES, build_swarm, validate_swarm

REVISION = "575ebc777fae0165c93247e8c6da44c440539c4d"
ROOT = Path(__file__).resolve().parents[1]


def draft(**changes):
    return {"schema_version": 1, "kind": "jarvis.draft", "project_id": "ai-jarvis",
            "target": "gemini", "text": "Prepare an evidence-backed draft.", **changes}


def swarm(**changes):
    args = {"swarm_id": "test-swarm", "source_revision": REVISION, **changes}
    return build_swarm("ai-jarvis", ["gemini", "claude", "github"], **args)


class ContractTests(unittest.TestCase):
    def test_draft_preserves_text_and_is_defensive(self):
        original = draft(text="  Original wording.\n")
        checked = validate_draft(original)
        self.assertEqual(checked, original)
        checked["text"] = "Changed"
        self.assertNotEqual(checked, original)

    def test_unknown_and_extra_fields_rejected(self):
        for changes in ({"target": "unregistered"}, {"target": []}, {"project_id": []},
                        {"project_id": "unknown"}, {"schema_version": True}, {"text": []},
                        {"kind": "jarvis.command"}, {"send": True}, {"api_key": "fake"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_draft(draft(**changes))

    def test_text_size_unicode_and_controls(self):
        self.assertEqual(len(validate_draft(draft(text="é" * 10000))["text"]), 10000)
        for value in ("", "  \n", "é" * 10001, "\ud800", "word\x00word"):
            with self.subTest(size=len(value)), self.assertRaises(ValueError):
                validate_draft(draft(text=value))

    def test_catalog_and_contract_include_every_target(self):
        self.assertEqual(set(provider_catalog()), set(TARGETS))
        self.assertTrue({"facebook", "linkedin", "substack", "instagram", "threads", "youtube", "github"} <= TARGETS)

    def test_file_import_rejects_duplicate_keys_nonfinite_and_invalid_encoding(self):
        bad = [b'{"schema_version":1,"schema_version":2}', b'{"x":{"y":1,"y":2}}',
               b'{"x":NaN}', b'{"x":Infinity}', b'\xff', b'[]', b'{' + b' ' * MAX_PACKET_BYTES]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "packet.json"
            for content in bad:
                path.write_bytes(content)
                with self.subTest(content=content[:20]), self.assertRaises(ValueError):
                    load_packet(path)

    def test_file_import_accepts_exact_draft(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "packet.json"
            path.write_text(json.dumps(draft()))
            self.assertEqual(validate_draft(load_packet(path)), draft())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO probe requires POSIX")
    def test_file_import_rejects_fifo_without_blocking(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "packet.pipe"
            os.mkfifo(path)
            with self.assertRaises(ValueError):
                load_packet(path)


class FactoryTests(unittest.TestCase):
    def test_five_inactive_roles_with_exact_templates(self):
        result = swarm()
        self.assertEqual(len(result["assistants"]), 5)
        self.assertEqual({a["role"] for a in result["assistants"]}, {"researcher", "architect", "builder", "evaluator", "reporter"})
        self.assertTrue(all(a["state"] == "inactive_proposal" and a["static_evaluation"]["passed"] for a in result["assistants"]))
        self.assertEqual(result["external_actions"], 0)
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(validate_swarm(result), result)

    def test_all_projects_generate_distinct_full_manifests(self):
        results = [build_swarm(p, ["chatgpt"], swarm_id=f"project-{i}", source_revision=REVISION)
                   for i, p in enumerate(PROJECTS)]
        self.assertEqual(len({r["manifest_sha256"] for r in results}), len(PROJECTS))

    def test_target_order_does_not_change_identity(self):
        a = build_swarm("ai-jarvis", ["claude", "gemini"], swarm_id="stable-swarm", source_revision=REVISION)
        b = build_swarm("ai-jarvis", ["gemini", "claude"], swarm_id="stable-swarm", source_revision=REVISION)
        self.assertEqual(a, b)

    def test_budget_revision_and_role_tampering_rejected(self):
        for changes in ({"max_handoffs_per_assistant": True}, {"max_handoffs_per_assistant": 6},
                        {"max_depth": 3}, {"max_depth": -1}, {"source_revision": "main"}, {"swarm_id": "../../outside"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                swarm(**changes)
        record = swarm()
        record["assistants"][0]["capabilities"].append("publish_without_review")
        record["manifest_sha256"] = digest({k: v for k, v in record.items() if k != "manifest_sha256"})
        with self.assertRaises(ValueError):
            validate_swarm(record)

    def test_boolean_alias_cannot_impersonate_integer_fields(self):
        for field, value in (("schema_version", True), ("external_actions", False), ("model_calls", False)):
            record = swarm()
            record[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_swarm(record)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.path = Path(self.directory.name) / "ledger.sqlite3"
        self.ledger = HandoffLedger(self.path)
        self.manifest = swarm()

    def tearDown(self):
        self.ledger.close()
        self.directory.cleanup()

    def stage(self, handoff="task-one", **kwargs):
        return self.ledger.stage(draft(), self.manifest, assistant_id="test-swarm.builder", handoff_id=handoff, **kwargs)

    def prepare(self, handoff="task-one"):
        record = self.stage(handoff)
        self.ledger.review(handoff, reviewer_id="reviewer-local", expected_sha256=record["handoff_sha256"])
        self.ledger.export(handoff, expected_sha256=record["handoff_sha256"])
        return record

    @staticmethod
    def returned(record, **changes):
        return {"schema_version": 1, "kind": "jarvis.return", "return_id": "return-one",
                "handoff_id": record["handoff_id"], "handoff_sha256": record["handoff_sha256"],
                "source_provider": "gemini", "text": "Unverified fixture response.", "evidence_urls": [], **changes}

    def test_export_requires_exact_digest_and_distinct_review_label(self):
        record = self.stage()
        with self.assertRaises(ValueError):
            self.ledger.export("task-one", expected_sha256=record["handoff_sha256"])
        for reviewer, checksum in (("test-swarm.builder", record["handoff_sha256"]), ("reviewer-local", "0" * 64)):
            with self.assertRaises(ValueError):
                self.ledger.review("task-one", reviewer_id=reviewer, expected_sha256=checksum)
        self.assertEqual(self.ledger.status()["handoffs"][0]["state"], "pending_review")

    def test_role_catalog_cannot_invalidate_reviewed_handoff_across_restart(self):
        record = self.prepare()
        original = ROLE_TEMPLATES["builder"]
        before = self.ledger.status()
        replacement = ("validation_tool", "Changed role instructions.")
        try:
            with self.assertRaises(TypeError):
                ROLE_TEMPLATES["builder"] = replacement
        finally:
            # Keep the pre-fix reproduction from changing other tests' baseline.
            if isinstance(ROLE_TEMPLATES, dict):
                ROLE_TEMPLATES["builder"] = original
        with self.assertRaises(TypeError):
            ROLE_TEMPLATES["new_role"] = replacement
        with self.assertRaises(TypeError):
            del ROLE_TEMPLATES["evaluator"]
        self.assertEqual(validate_swarm(self.manifest), self.manifest)
        self.assertEqual(swarm(), self.manifest)
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        self.assertEqual(self.ledger.status(), before)
        self.assertTrue(self.stage()["duplicate"])
        self.assertEqual(self.ledger.export("task-one", expected_sha256=record["handoff_sha256"])["handoff_sha256"],
                         record["handoff_sha256"])

    def test_roundtrip_persists_and_duplicates_do_not_consume_budget(self):
        record = self.prepare()
        result = self.ledger.import_return(self.returned(record))
        self.assertEqual(result["state"], "returned_unverified")
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        self.assertTrue(self.stage()["duplicate"])
        self.assertTrue(self.ledger.import_return(self.returned(record))["duplicate"])
        self.assertEqual(self.ledger.status()["return_count"], 1)
        self.assertEqual(self.stage("task-two")["state"], "pending_review")

    def test_budget_survives_reopen_and_separate_connections(self):
        self.stage()
        self.ledger.close()
        self.ledger = HandoffLedger(self.path)
        self.stage("task-two")
        with HandoffLedger(self.path) as second:
            with self.assertRaises(ValueError):
                second.stage(draft(), self.manifest, assistant_id="test-swarm.builder", handoff_id="task-three")
        self.assertEqual(len(self.ledger.status()["handoffs"]), 2)

    def test_conflicting_handoff_does_not_replace_original(self):
        original = self.stage()
        with self.assertRaises(ValueError):
            self.ledger.stage(draft(text="Changed"), self.manifest, assistant_id="test-swarm.builder", handoff_id="task-one")
        self.assertEqual(self.ledger.status()["handoffs"][0]["handoff_sha256"], original["handoff_sha256"])

    def test_registered_swarm_cannot_be_redefined_to_reset_budget(self):
        self.stage()
        changed = swarm(max_handoffs_per_assistant=5)
        with self.assertRaises(ValueError):
            self.ledger.stage(draft(), changed, assistant_id="test-swarm.builder", handoff_id="task-two")

    def test_wrong_project_assistant_or_target_is_rejected(self):
        for item, assistant in ((draft(project_id="linux-education"), "test-swarm.builder"),
                                (draft(target="facebook"), "test-swarm.builder"),
                                (draft(), "stranger.builder")):
            with self.assertRaises(ValueError):
                self.ledger.stage(item, self.manifest, assistant_id=assistant, handoff_id="task-one")
        self.assertEqual(self.ledger.status()["swarm_count"], 0)

    def test_return_before_export_or_with_wrong_binding_rejected(self):
        record = self.stage()
        with self.assertRaises(ValueError):
            self.ledger.import_return(self.returned(record))
        self.prepare()
        for changes in ({"source_provider": "claude"}, {"handoff_sha256": "0" * 64}, {"handoff_id": "missing-task"}):
            with self.assertRaises(ValueError):
                self.ledger.import_return(self.returned(record, **changes))
        self.assertEqual(self.ledger.status()["return_count"], 0)

    def test_conflicting_return_rejected_without_overwriting(self):
        record = self.prepare()
        original = self.ledger.import_return(self.returned(record))
        for changes in ({"text": "Changed answer"}, {"return_id": "replacement-return"}):
            with self.assertRaises(ValueError):
                self.ledger.import_return(self.returned(record, **changes))
        self.assertEqual(self.ledger.status()["return_count"], 1)
        self.assertTrue(self.ledger.import_return(self.returned(record))["duplicate"])
        self.assertEqual(original["sender_authentication"], "not_established")

    def test_return_id_cannot_be_reused_for_another_handoff(self):
        first = self.prepare()
        second = self.prepare("task-two")
        self.ledger.import_return(self.returned(first))
        with self.assertRaises(ValueError):
            self.ledger.import_return(self.returned(second))

    def test_parent_scope_and_depth_are_bounded(self):
        record = self.prepare()
        with self.assertRaises(ValueError):
            self.stage("task-two", parent_id="task-one")
        self.ledger.import_return(self.returned(record))
        child = self.stage("task-two", parent_id="task-one")
        self.ledger.review("task-two", reviewer_id="reviewer-local", expected_sha256=child["handoff_sha256"])
        self.ledger.export("task-two", expected_sha256=child["handoff_sha256"])
        self.ledger.import_return(self.returned(child, return_id="return-two"))
        with self.assertRaises(ValueError):
            self.ledger.stage(draft(), self.manifest, assistant_id="test-swarm.researcher", handoff_id="task-three", parent_id="task-two")

    def test_stored_payload_tampering_fails_closed(self):
        record = self.prepare()
        self.ledger.db.execute("UPDATE handoffs SET body=? WHERE id='task-one'", ('{"changed":true}',))
        with self.assertRaises(ValueError):
            self.ledger.export("task-one", expected_sha256=record["handoff_sha256"])

    def test_deep_corrupt_stored_payload_is_controlled(self):
        self.stage()
        self.ledger.db.execute("UPDATE handoffs SET body=? WHERE id='task-one'", ("[" * 30000 + "]" * 30000,))
        with self.assertRaises(ValueError):
            self.ledger.status()

    def test_status_does_not_echo_draft_text(self):
        self.stage()
        self.assertNotIn(draft()["text"], json.dumps(self.ledger.status()))

    def test_damaged_or_deleted_return_blocks_status_and_child(self):
        record = self.prepare()
        self.ledger.import_return(self.returned(record))
        for action in ("UPDATE returns SET body='{broken json'", "DELETE FROM returns"):
            self.ledger.db.execute(action)
            with self.assertRaises(ValueError):
                self.ledger.status()
            with self.assertRaises(ValueError):
                self.stage("task-two", parent_id="task-one")

    def test_unrelated_database_is_preserved_and_rejected(self):
        path = Path(self.directory.name) / "other.sqlite3"
        with sqlite3.connect(path) as other:
            other.execute("CREATE TABLE unrelated (id INTEGER)")
        with self.assertRaises(ValueError):
            HandoffLedger(path)
        with sqlite3.connect(path) as other:
            self.assertEqual(other.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [("unrelated",)])

    def test_invalid_return_fields_and_evidence_are_rejected(self):
        record = self.prepare()
        for change in ({"schema_version": True}, {"source_provider": []}, {"text": "\ud800"},
                       {"evidence_urls": ["https://user:password@example.com"]}, {"execute": True}):
            with self.assertRaises(ValueError):
                validate_return(self.returned(record, **change))


class IntegrationTests(unittest.TestCase):
    def test_packet_output_round_trip_avoids_formatting_overflow(self):
        record = {"items": ["é" * 51] * 600}
        self.assertGreater(len(json.dumps(record, indent=2, ensure_ascii=False).encode()), MAX_PACKET_BYTES)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "packet.json"
            _write(path, record)
            self.assertLessEqual(path.stat().st_size, MAX_PACKET_BYTES)
            self.assertEqual(load_packet(path), record)
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                _write(path, {"changed": True})
            self.assertEqual(path.read_bytes(), before)

    def test_packet_output_byte_boundary_and_invalid_input_leave_no_artifact(self):
        # Includes multibyte text and the final newline in the exact byte limit.
        record = {"text": "é" + "x" * (MAX_PACKET_BYTES - 14)}
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "boundary.json"
            _write(path, record)
            self.assertEqual(path.stat().st_size, MAX_PACKET_BYTES)
            self.assertEqual(load_packet(path), record)
            for index, invalid in enumerate(({"text": record["text"] + "x"},
                    {"text": "\ud800"}, {"number": float("nan")}, {"value": object()})):
                with self.subTest(index=index):
                    parent = root / str(index)
                    with self.assertRaises(ValueError):
                        _write(parent / "rejected.json", invalid)
                    self.assertFalse(parent.exists())

    @unittest.skipUnless(os.name == "posix", "directory fsync requires POSIX")
    def test_json_publication_syncs_directory_and_preserves_uncertain_output(self):
        fsync = os.fsync
        with TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            calls = []
            def track_sync(fd):
                is_directory = stat.S_ISDIR(os.fstat(fd).st_mode)
                calls.append(is_directory)
                if is_directory:
                    self.assertEqual(json.loads(path.read_text()), {"safe": True})
                fsync(fd)
            with patch("scripts.jarvis_network.os.fsync", side_effect=track_sync):
                _write(path, {"safe": True})
            self.assertEqual(calls, [False, True])
            uncertain = Path(directory) / "uncertain.json"
            def fail_directory_sync(fd):
                if stat.S_ISDIR(os.fstat(fd).st_mode):
                    raise OSError("simulated directory sync failure")
                fsync(fd)
            with patch("scripts.jarvis_network.os.fsync", side_effect=fail_directory_sync), self.assertRaises(OSError):
                _write(uncertain, {"retained": True})
            # Publication already occurred: reconcile this file, never overwrite it.
            original = uncertain.read_bytes()
            self.assertEqual(json.loads(original), {"retained": True})
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ["evidence.json", "uncertain.json"])
            with self.assertRaises(FileExistsError):
                _write(uncertain, {"changed": True})
            self.assertEqual(uncertain.read_bytes(), original)

    def test_youtube_and_github_attribution_and_journeys(self):
        from control_tower.attribution import aggregate
        from control_tower.journeys import reconcile_journeys
        for channel in ("youtube", "github"):
            events = [{"event_id": "visit", "event_type": "campaign_visit", "utm_source": channel}]
            self.assertEqual(aggregate(events)[(channel, "visits")], 1)
            report = reconcile_journeys([{"event_id": "synthetic-signup", "journey_id": "synthetic-member",
                "event_type": "member_signup", "kind": "member", "occurred_at": "2026-10-22T12:00:00-07:00",
                "source": channel, "synthetic": True, "service_consent": True}])
            self.assertEqual(report["counts"]["accepted"], 1)

    def test_failed_file_sync_leaves_no_partial_output_and_can_retry(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            with patch("scripts.jarvis_network.os.fsync", side_effect=OSError("simulated file sync error")), self.assertRaises(OSError):
                _write(path, {"safe": True})
            self.assertFalse(path.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])
            _write(path, {"safe": True})
            with self.assertRaises(FileExistsError):
                _write(path, {"changed": True})
            self.assertEqual(json.loads(path.read_text()), {"safe": True})

    def test_network_demo_keeps_local_fixture_scope(self):
        report = demonstrate_network()
        self.assertEqual(report["inactive_assistant_specifications"], 35)
        self.assertTrue(report["reopen_retry_is_duplicate"])
        self.assertEqual(report["return_state"], "returned_unverified")
        self.assertEqual(report["external_actions"], 0)
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual(report["external_agents_started"], 0)

    def test_cli_refuses_escape_and_existing_output(self):
        with TemporaryDirectory() as directory:
            base = [sys.executable, str(ROOT / "scripts/jarvis_network.py"), "--root", directory, "demo", "--out"]
            escaped = subprocess.run(base + ["../escape.json"], capture_output=True, text=True)
            self.assertEqual(escaped.returncode, 1)
            self.assertIn("path leaves", escaped.stderr)
            good = subprocess.run(base + ["report.json"], capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            first = Path(directory, "report.json").read_bytes()
            again = subprocess.run(base + ["report.json"], capture_output=True, text=True)
            self.assertEqual(again.returncode, 1)
            self.assertEqual(Path(directory, "report.json").read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
