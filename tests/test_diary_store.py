"""Temporary synthetic databases only; no owner data, credentials or network."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import threading
import unittest
from unittest.mock import patch

from control_tower.diary import diary_entry_digest
from control_tower import diary_store
from control_tower.diary_store import DiaryStore


def entry(entry_id="synthetic-entry", date="2026-10-22", visibility="private"):
    return {"schema_version": 1, "kind": "jarvis.diary_entry", "entry_id": entry_id,
            "date": date, "timezone": "America/Los_Angeles", "initiative_id": "personal-workflow",
            "title": "SYNTHETIC_PRIVATE_TITLE", "visibility": visibility,
            "summary": "SYNTHETIC_PRIVATE_SUMMARY", "observations": [{"observation_id": "synthetic-observation",
                "text": "SYNTHETIC_PRIVATE_OBSERVATION", "evidence_state": "fictional", "source_ids": []}],
            "sources": [], "next_action": "SYNTHETIC_PRIVATE_ACTION",
            "media_notes": {"audience": "", "visual_style": "", "audio_style": "",
                            "learning_goal": "", "call_to_action": ""}}


class DiaryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.path = self.directory / "private" / "diary.sqlite3"

    def tearDown(self):
        self.temporary.cleanup()

    def test_roundtrip_reopen_and_defensive_results(self):
        value = entry()
        with DiaryStore(self.path) as store:
            receipt = store.save(value)
            self.assertEqual(receipt, {"entry_id": "synthetic-entry", "revision": 1,
                                      "sha256": diary_entry_digest(value), "status": "created"})
            self.assertEqual(store.get("synthetic-entry"), value)
            retrieved = store.get("synthetic-entry")
            retrieved["observations"][0]["text"] = "mutated caller copy"
            self.assertEqual(store.get("synthetic-entry"), value)
        with DiaryStore(self.path) as reopened:
            self.assertEqual(reopened.get("synthetic-entry"), value)
            self.assertEqual(len(reopened.history("synthetic-entry")), 1)
            self.assertIsNone(reopened.get("unknown-entry"))
            self.assertEqual(reopened.history("unknown-entry"), [])

    def test_default_location_and_private_permissions(self):
        previous = Path.cwd()
        try:
            os.chdir(self.directory)
            with DiaryStore() as store:
                self.assertEqual(store.path, self.directory / "reports/diary/diary.sqlite3")
                store.save(entry())
            for path, mode in ((self.directory / "reports", 0o700),
                               (self.directory / "reports/diary", 0o700),
                               (self.directory / "reports/diary/diary.sqlite3", 0o600)):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)
        finally:
            os.chdir(previous)

    def test_idempotent_retry_does_not_add_a_revision(self):
        with DiaryStore(self.path) as store:
            first = store.save(entry())
            for expected in (None, first["sha256"], "0" * 64):
                retry = store.save(entry(), expected_sha256=expected)
                self.assertEqual(retry["status"], "unchanged")
                self.assertEqual(retry["revision"], 1)
            self.assertEqual(len(store.history("synthetic-entry")), 1)
            with self.assertRaises(ValueError):
                store.save(entry(), expected_sha256=True)

    def test_changed_content_requires_current_hash_and_preserves_history(self):
        first_entry, changed = entry(), entry()
        changed["summary"] = "SYNTHETIC_REVISED_SUMMARY"
        with DiaryStore(self.path) as store:
            first = store.save(first_entry)
            for expected in (None, "0" * 64):
                with self.assertRaisesRegex(ValueError, "current content hash"):
                    store.save(changed, expected_sha256=expected)
                self.assertEqual(store.get("synthetic-entry"), first_entry)
            second = store.save(changed, expected_sha256=first["sha256"])
            self.assertEqual((second["status"], second["revision"]), ("updated", 2))
            history = store.history("synthetic-entry")
            self.assertEqual([row["sha256"] for row in history], [first["sha256"], second["sha256"]])
            self.assertEqual([row["previous_sha256"] for row in history], [None, first["sha256"]])
            self.assertEqual(json.loads(store.db.execute("SELECT body FROM diary_revisions WHERE revision=1").fetchone()[0]), first_entry)
            with self.assertRaises(ValueError):
                store.save(first_entry, expected_sha256=first["sha256"])
            self.assertEqual(len(store.history("synthetic-entry")), 2)

    def test_new_id_rejects_expected_hash_and_invalid_inputs_leave_no_rows(self):
        with DiaryStore(self.path) as store:
            with self.assertRaises(ValueError):
                store.save(entry(), expected_sha256="0" * 64)
            invalid = entry()
            invalid["summary"] += "\x00"
            with self.assertRaises(ValueError):
                store.save(invalid)
            self.assertEqual(store.list_metadata(), [])
            self.assertEqual(store.db.execute("SELECT count(*) FROM diary_revisions").fetchone()[0], 0)
            for invalid_id in (True, "x", "../private-record"):
                with self.assertRaises(ValueError):
                    store.get(invalid_id)
            with self.assertRaises(ValueError):
                store.entries_for_date("2026-02-30")

    def test_two_connections_reject_stale_updates(self):
        with DiaryStore(self.path) as first, DiaryStore(self.path) as second:
            created = first.save(entry())
            changed = entry()
            changed["summary"] = "changed by first local writer"
            saved = first.save(changed, expected_sha256=created["sha256"])
            another = entry()
            another["summary"] = "changed by second local writer"
            with self.assertRaises(ValueError):
                second.save(another, expected_sha256=created["sha256"])
            self.assertEqual(second.get("synthetic-entry"), changed)
            self.assertEqual(second.save(another, expected_sha256=saved["sha256"])["revision"], 3)

    def test_read_uses_one_snapshot_during_a_concurrent_commit(self):
        ready, start_write, committing = threading.Event(), threading.Event(), threading.Event()
        errors, commit_seen = [], []
        changed = entry()
        changed["summary"] = "synthetic concurrent update"
        with DiaryStore(self.path) as reader:
            first = reader.save(entry())
            def writer():
                try:
                    with DiaryStore(self.path) as store:
                        store.db.set_trace_callback(lambda sql: committing.set() if sql == "COMMIT" else None)
                        ready.set()
                        if not start_write.wait(3):
                            raise AssertionError("synthetic writer was not started")
                        store.save(changed, expected_sha256=first["sha256"])
                except Exception as error:
                    errors.append(error)
                    ready.set()
                    committing.set()
            thread = threading.Thread(target=writer)
            thread.start()
            self.assertTrue(ready.wait(3))
            def trace(sql):
                if sql.startswith("SELECT * FROM diary_revisions"):
                    start_write.set()
                    commit_seen.append(committing.wait(1))
            reader.db.set_trace_callback(trace)
            try:
                self.assertEqual(reader.get("synthetic-entry"), entry())
            finally:
                reader.db.set_trace_callback(None)
                start_write.set()
                thread.join(4)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(commit_seen, [True])
            self.assertEqual(reader.get("synthetic-entry"), changed)

    def test_current_date_selection_and_metadata_never_include_free_text(self):
        with DiaryStore(self.path) as store:
            first = store.save(entry("entry-b"))
            store.save(entry("entry-a"))
            changed = entry("entry-b", date="2026-10-23", visibility="public_candidate")
            store.save(changed, expected_sha256=first["sha256"])
            self.assertEqual([row["entry_id"] for row in store.entries_for_date("2026-10-22")], ["entry-a"])
            self.assertEqual(store.entries_for_date("2026-10-23"), [changed])
            listed = store.list_metadata()
            self.assertEqual([row["entry_id"] for row in listed], ["entry-a", "entry-b"])
            self.assertEqual([row["date"] for row in store.history("entry-b")], ["2026-10-22", "2026-10-23"])
            serialized = json.dumps(listed + store.history("entry-b"))
            for marker in ("SYNTHETIC_PRIVATE_TITLE", "SYNTHETIC_PRIVATE_SUMMARY",
                           "SYNTHETIC_PRIVATE_OBSERVATION", "SYNTHETIC_PRIVATE_ACTION"):
                self.assertNotIn(marker, serialized)
            self.assertNotIn("body", listed[0])

    def test_sql_revision_update_and_delete_are_blocked(self):
        with DiaryStore(self.path) as store:
            store.save(entry())
            for statement in ("UPDATE diary_revisions SET body='changed'", "DELETE FROM diary_revisions"):
                with self.assertRaises(sqlite3.IntegrityError):
                    store.db.execute(statement)
            self.assertEqual(store.get("synthetic-entry"), entry())

    def test_failed_head_change_rolls_back_the_appended_revision(self):
        with DiaryStore(self.path) as store:
            first = store.save(entry())
            store.db.execute("CREATE TRIGGER synthetic_fail_head BEFORE UPDATE ON diary_entries "
                             "BEGIN SELECT RAISE(ABORT, 'SYNTHETIC_PRIVATE_SQL_ERROR'); END")
            changed = entry()
            changed["summary"] = "synthetic revised text"
            with self.assertRaises(ValueError) as caught:
                store.save(changed, expected_sha256=first["sha256"])
            self.assertEqual(str(caught.exception), "diary store operation failed")
            self.assertFalse(store.db.in_transaction)
            self.assertEqual(store.db.execute("SELECT count(*) FROM diary_revisions").fetchone()[0], 1)
            self.assertEqual(store.get("synthetic-entry"), entry())

    def test_corrupted_body_digest_binding_and_chain_are_rejected(self):
        mutations = [("body", '{"secret":"SYNTHETIC_PRIVATE_CORRUPT_TEXT"}'),
                     ("body", '{"kind":"jarvis.diary_entry","kind":"duplicate"}'),
                     ("body", "NaN"), ("body", "x" * 65537),
                     ("sha256", "0" * 64), ("diary_date", "2026-10-21"),
                     ("visibility", "public_candidate"), ("previous_sha256", "0" * 64),
                     ("saved_at", "2026-10-22T00:00:00")]
        for index, (column, value) in enumerate(mutations):
            with self.subTest(column=column, index=index), DiaryStore(self.directory / f"corrupt-{index}.sqlite3") as store:
                store.save(entry())
                store.db.execute("DROP TRIGGER diary_revisions_no_update")
                store.db.execute(f"UPDATE diary_revisions SET {column}=?", (value,))
                for operation in (lambda: store.get("synthetic-entry"), lambda: store.history("synthetic-entry"),
                                  store.list_metadata, lambda: store.entries_for_date("2026-10-22")):
                    with self.assertRaisesRegex(ValueError, "integrity check failed") as caught:
                        operation()
                    self.assertNotIn("SYNTHETIC_PRIVATE_CORRUPT_TEXT", str(caught.exception))

    def test_historical_corruption_is_detected_even_when_current_entry_is_intact(self):
        with DiaryStore(self.path) as store:
            first = store.save(entry())
            changed = entry()
            changed["summary"] = "second revision"
            store.save(changed, expected_sha256=first["sha256"])
            store.db.execute("DROP TRIGGER diary_revisions_no_update")
            store.db.execute("UPDATE diary_revisions SET sha256=? WHERE revision=1", ("0" * 64,))
            with self.assertRaisesRegex(ValueError, "integrity check failed"):
                store.get("synthetic-entry")

    def test_oversized_external_row_fails_before_json_materialization(self):
        with DiaryStore(self.path) as store:
            store.save(entry())
            self.assertEqual(store.db.getlimit(sqlite3.SQLITE_LIMIT_LENGTH), 65536 + 4096)
            # Simulate a damaged/imported local database through a separate
            # default-limit connection, outside the store's constrained writer.
            with sqlite3.connect(self.path) as external:
                external.execute("DROP TRIGGER diary_revisions_no_update")
                external.execute("UPDATE diary_revisions SET body=?", ("SYNTHETIC_OVERSIZED_ROW" * 7000,))
            with patch.object(diary_store.json, "loads", wraps=json.loads) as parse:
                with self.assertRaisesRegex(ValueError, "^diary store operation failed$") as caught:
                    store.get("synthetic-entry")
                parse.assert_not_called()
            self.assertNotIn("SYNTHETIC_OVERSIZED_ROW", str(caught.exception))
            self.assertFalse(store.db.in_transaction)

    def test_invalid_head_or_orphan_revisions_are_rejected(self):
        with DiaryStore(self.path) as store:
            first = store.save(entry())
            changed = entry()
            changed["summary"] = "second revision"
            store.save(changed, expected_sha256=first["sha256"])
            store.db.execute("UPDATE diary_entries SET current_revision=1")
            with self.assertRaisesRegex(ValueError, "integrity check failed"):
                store.get("synthetic-entry")
            store.db.execute("DELETE FROM diary_entries")
            with self.assertRaisesRegex(ValueError, "integrity check failed"):
                store.get("synthetic-entry")
            with self.assertRaisesRegex(ValueError, "integrity check failed"):
                store.list_metadata()

    def test_capacity_bounds_preserve_existing_entries(self):
        with DiaryStore(self.path) as store:
            first = store.save(entry())
            with patch.object(diary_store, "MAX_STORED_ENTRIES", 1):
                with self.assertRaisesRegex(ValueError, "entry limit"):
                    store.save(entry("another-entry"))
            changed = entry()
            changed["summary"] = "second revision"
            with patch.object(diary_store, "MAX_REVISIONS_PER_ENTRY", 1):
                with self.assertRaisesRegex(ValueError, "revision limit"):
                    store.save(changed, expected_sha256=first["sha256"])
            self.assertEqual(store.get("synthetic-entry"), entry())
            self.assertEqual(len(store.history("synthetic-entry")), 1)

    def test_unrelated_corrupt_and_modified_schema_databases_are_rejected(self):
        for index, mode in enumerate(("unrelated", "non-sqlite", "missing-trigger", "wrong-version")):
            path = self.directory / f"invalid-{index}.sqlite3"
            path.touch(mode=0o600)
            if mode == "non-sqlite":
                path.write_text("SYNTHETIC_PRIVATE_NOT_SQLITE")
            elif mode == "unrelated":
                with sqlite3.connect(path) as db:
                    db.execute("CREATE TABLE unrelated (value TEXT)")
            else:
                with DiaryStore(path) as store:
                    store.save(entry())
                    store.db.execute("DROP TRIGGER diary_revisions_no_update" if mode == "missing-trigger" else "PRAGMA user_version=2")
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "cannot open a safe diary store") as caught:
                DiaryStore(path)
            self.assertNotIn("SYNTHETIC_PRIVATE", str(caught.exception))

    def test_symlink_database_and_parent_are_rejected_without_touching_target(self):
        target = self.directory / "target.txt"
        target.write_text("unchanged synthetic target")
        database_link = self.directory / "linked.sqlite3"
        database_link.symlink_to(target)
        with self.assertRaises(ValueError):
            DiaryStore(database_link)
        parent_link = self.directory / "parent-link"
        parent_link.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaises(ValueError):
            DiaryStore(parent_link / "unused.sqlite3")
        dangling = self.directory / "dangling.sqlite3"
        dangling.symlink_to(self.directory / "absent")
        with self.assertRaises(ValueError):
            DiaryStore(dangling)
        self.assertEqual(target.read_text(), "unchanged synthetic target")
        self.assertFalse((self.directory / "unused.sqlite3").exists())
        self.assertFalse((self.directory / "absent").exists())

    def test_fifo_directory_hardlink_and_unsafe_modes_are_rejected(self):
        fifo = self.directory / "fifo.sqlite3"
        os.mkfifo(fifo, 0o600)
        folder = self.directory / "folder.sqlite3"
        folder.mkdir(mode=0o700)
        hard_target = self.directory / "hard-target"
        hard_target.touch(mode=0o600)
        hardlink = self.directory / "hard.sqlite3"
        os.link(hard_target, hardlink)
        readable = self.directory / "readable.sqlite3"
        readable.touch(mode=0o644)
        writable_parent = self.directory / "unsafe"
        writable_parent.mkdir(mode=0o700)
        writable_parent.chmod(0o777)
        for path in (fifo, folder, hardlink, readable, writable_parent / "store.sqlite3"):
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                DiaryStore(path)
        self.assertEqual(hard_target.read_bytes(), b"")

    def test_sidecar_symlink_is_rejected_and_target_is_unchanged(self):
        target = self.directory / "sidecar-target"
        target.write_text("untouched synthetic value")
        for suffix in ("-journal", "-wal", "-shm"):
            path = self.directory / ("sidecar" + suffix + ".sqlite3")
            Path(str(path) + suffix).symlink_to(target)
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                DiaryStore(path)
        self.assertEqual(target.read_text(), "untouched synthetic value")

    def test_replaced_file_and_changed_permissions_are_rejected_after_open(self):
        with DiaryStore(self.path) as store:
            store.save(entry())
            self.path.chmod(0o644)
            with self.assertRaises(ValueError):
                store.get("synthetic-entry")
            self.path.chmod(0o600)
            moved = self.path.with_name("moved.sqlite3")
            self.path.rename(moved)
            self.path.touch(mode=0o600)
            with self.assertRaises(ValueError):
                store.save(entry("another-entry"))
            self.assertEqual(self.path.read_bytes(), b"")

    def test_special_paths_and_closed_store_fail_cleanly(self):
        for path in (":memory:", "file:database?mode=memory", "", "bad\x00path", True):
            with self.subTest(path=repr(path)), self.assertRaises(ValueError):
                DiaryStore(path)
        store = DiaryStore(self.path)
        store.close()
        store.close()
        with self.assertRaises(ValueError):
            store.get("synthetic-entry")
        with self.assertRaises(ValueError):
            with store:
                pass


if __name__ == "__main__":
    unittest.main()
