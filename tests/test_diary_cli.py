from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from control_tower.diary import diary_entry_digest
from control_tower.diary_store import DiaryStore
from scripts.jarvis_diary import _write_bytes, main

ROOT = Path(__file__).resolve().parents[1]
REVISION = "e645c64975dc05f3b0a0f9e06d7cc903d70031b0"


class DiaryCLITests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads((ROOT / "examples/diary/public-project-entry.json").read_text())

    def call(self, root, *args):
        with patch("sys.stdout", new_callable=io.StringIO) as out, patch("sys.stderr", new_callable=io.StringIO) as err:
            code = main(["--root", str(root), *args])
        return code, out.getvalue(), err.getvalue()

    def source(self, root, value=None):
        (root / "entry.json").write_text(json.dumps(value or self.value))

    def test_local_save_update_history_and_exact_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = deepcopy(self.value)
            value["visibility"] = "private"
            value["summary"] = "SENSITIVE-TEST-ONLY-SUMMARY"
            self.source(root, value)
            code, out, err = self.call(root, "save", "--entry-file", "entry.json")
            self.assertEqual(0, code, err)
            saved = json.loads(out)
            self.assertNotIn(value["summary"], out)
            value["summary"] += " changed"
            self.source(root, value)
            code, _, err = self.call(root, "save", "--entry-file", "entry.json")
            self.assertEqual(1, code)
            self.assertIn("current content hash", err)
            code, out, err = self.call(root, "save", "--entry-file", "entry.json", "--expected-sha256", saved["sha256"])
            self.assertEqual(0, code, err)
            self.assertEqual(2, json.loads(out)["revision"])
            code, out, err = self.call(root, "history", "--entry-id", value["entry_id"])
            self.assertEqual(0, code, err)
            self.assertEqual(2, len(json.loads(out)["history"]))
            self.assertNotIn(value["summary"], out)
            code, _, err = self.call(root, "export-entry", "--entry-id", value["entry_id"], "--out", "saved.json")
            self.assertEqual(0, code, err)
            self.assertEqual(value, json.loads((root / "saved.json").read_text()))

    def test_private_brief_requires_explicit_owner_audience(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = deepcopy(self.value)
            private.update(visibility="private", summary="SENSITIVE-TEST-ONLY")
            self.source(root, private)
            for audience, count in (("public", 0), ("owner", 1)):
                filename = audience + ".json"
                code, _, err = self.call(root, "briefing", "--entry-file", "entry.json", "--date", private["date"], "--audience", audience, "--out", filename)
                self.assertEqual(0, code, err)
                result = json.loads((root / filename).read_text())
                self.assertEqual(count, result["entry_count"])
                if audience == "public":
                    self.assertNotIn("SENSITIVE-TEST-ONLY", json.dumps(result))
                    self.assertNotIn(private["entry_id"], json.dumps(result))

    def test_database_symlinks_are_rejected_without_writing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = deepcopy(self.value)
            private["visibility"] = "private"
            self.source(root, private)
            target = root / "safe" / "actual.sqlite3"
            with DiaryStore(target):
                pass
            (root / "alias.sqlite3").symlink_to(target)
            (root / "linked-parent").symlink_to(root / "safe", target_is_directory=True)
            for locator in ("alias.sqlite3", "linked-parent/actual.sqlite3"):
                with self.subTest(locator=locator):
                    code, _, err = self.call(root, "--db", locator, "save", "--entry-file", "entry.json")
                    self.assertEqual(1, code)
                    self.assertIn("cannot open a safe diary store", err)
            with DiaryStore(target) as diary:
                self.assertEqual([], diary.list_metadata())

    def test_database_path_rejects_parent_absolute_and_uri_locators(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for locator in ("../outside.sqlite3", "a/../inside.sqlite3", "/tmp/outside.sqlite3", ":memory:", "file:diary", ".", ""):
                with self.subTest(locator=locator):
                    code, _, err = self.call(root, "--db", locator, "list")
                    self.assertEqual(1, code)
                    self.assertIn("relative workspace path", err)
            self.assertEqual([], list(root.iterdir()))

    def test_pack_is_real_zip_and_does_not_render_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.source(root)
            with patch("control_tower.media_render.render_previews") as renderer:
                code, out, err = self.call(root, "pack", "--entry-file", "entry.json", "--product", "cli-product", "--source-revision", REVISION, "--duration", "15", "--out", "pack.zip")
            self.assertEqual(0, code, err)
            renderer.assert_not_called()
            self.assertFalse(json.loads(out)["preview_rendered"])
            with ZipFile(root / "pack.zip") as archive:
                self.assertEqual(18, len(archive.namelist()))
                self.assertEqual(diary_entry_digest(self.value), json.loads(archive.read("manifest.json"))["source_entry_sha256"])

    def test_private_pack_failure_leaves_no_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = deepcopy(self.value)
            value["visibility"] = "private"
            self.source(root, value)
            code, _, err = self.call(root, "pack", "--entry-file", "entry.json", "--product", "private-pack", "--source-revision", REVISION, "--out", "private.zip")
            self.assertEqual(1, code)
            self.assertIn("public_candidate", err)
            self.assertFalse((root / "private.zip").exists())

    def test_existing_output_and_path_escape_fail_before_render(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.source(root)
            (root / "keep.zip").write_bytes(b"keep")
            for filename in ("keep.zip", "../outside.zip", "/tmp/outside-diary.zip", "wrong.txt"):
                with self.subTest(filename=filename), patch("control_tower.media_render.render_previews") as renderer:
                    code, _, _ = self.call(root, "pack", "--entry-file", "entry.json", "--product", "safe-test", "--source-revision", REVISION, "--render-preview", "--out", filename)
                    self.assertEqual(1, code)
                    renderer.assert_not_called()
            self.assertEqual(b"keep", (root / "keep.zip").read_bytes())

    def test_failed_renderer_leaves_no_partial_pack(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.source(root)
            with patch("control_tower.media_render.render_previews", side_effect=ValueError("local media renderer failed; no preview committed")):
                code, _, err = self.call(root, "pack", "--entry-file", "entry.json", "--product", "failed-render", "--source-revision", REVISION, "--duration", "15", "--render-preview", "--out", "failed.zip")
            self.assertEqual(1, code)
            self.assertNotIn(self.value["summary"], err)
            self.assertFalse((root / "failed.zip").exists())

    def test_exclusive_writer_preserves_existing_and_cleans_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "result.zip"
            _write_bytes(output, b"keep")
            with self.assertRaises(FileExistsError):
                _write_bytes(output, b"replace")
            self.assertEqual(b"keep", output.read_bytes())
            fresh = root / "fresh.zip"
            with patch("scripts.jarvis_diary.os.link", side_effect=OSError("private filesystem detail")), self.assertRaises(OSError):
                _write_bytes(fresh, b"draft")
            self.assertEqual(["result.zip"], sorted(p.name for p in root.iterdir()))

    def test_validate_rejects_duplicate_json_keys_without_echoing_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "entry.json").write_text('{"private":"SENSITIVE-TEST","private":true}')
            code, _, err = self.call(root, "validate", "--entry-file", "entry.json")
            self.assertEqual(1, code)
            self.assertNotIn("SENSITIVE-TEST", err)


if __name__ == "__main__":
    unittest.main()
