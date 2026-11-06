"""The verifier separates machine summaries from retained diagnostic output."""
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import verify_control_tower as verifier


class VerifierOutputTests(unittest.TestCase):
    def test_companion_symlinks_are_rejected_before_checks_or_writes(self):
        for aliases_json in (False, True):
            with self.subTest(aliases_json=aliases_json), TemporaryDirectory() as directory:
                base = Path(directory)
                root = base / "root"
                (root / "reports").mkdir(parents=True)
                output = root / "reports/result.json"
                companion = output.with_suffix(".txt")
                target = output if aliases_json else base / "sentinel.txt"
                target.write_bytes(b"KEEP")
                try:
                    companion.symlink_to(target)
                except (OSError, NotImplementedError) as exc:
                    self.skipTest(f"symlinks unavailable: {exc}")
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch.object(verifier, "ROOT", root), \
                     patch.object(sys, "argv", ["verify", "--out", "reports/result.json"]), \
                     patch.object(unittest.defaultTestLoader, "discover",
                                  return_value=unittest.TestSuite()) as discover, \
                     patch("control_tower.demo.demonstrate", return_value={}) as demo, \
                     redirect_stdout(stdout), redirect_stderr(stderr):
                    try:
                        code = verifier.main()
                    except SystemExit as exc:
                        code = exc.code
                self.assertEqual(target.read_bytes(), b"KEEP")
                self.assertEqual(code, 2)
                self.assertIn("text report cannot be a symlink", stderr.getvalue())
                self.assertEqual(stdout.getvalue(), "")
                discover.assert_not_called()
                demo.assert_not_called()
                self.assertTrue(companion.is_symlink())
                if not aliases_json:
                    self.assertFalse(output.exists())

    def test_noisy_success_and_failure_keep_json_summary_and_complete_log(self):
        for failing in (False, True):
            with self.subTest(failing=failing), TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "tests").mkdir()

                class NoisyFixture(unittest.TestCase):
                    def runTest(self):
                        print("FIXTURE_STDOUT")
                        print("FIXTURE_STDERR", file=sys.stderr)
                        if failing:
                            self.fail("FIXTURE_FAILURE")

                def discover(_):
                    print("DISCOVERY_STDOUT")
                    return unittest.TestSuite([NoisyFixture()])

                stdout, stderr = io.StringIO(), io.StringIO()
                with patch.object(verifier, "ROOT", root), \
                     patch.object(sys, "argv", ["verify", "--out", "reports/result.json"]), \
                     patch.object(unittest.defaultTestLoader, "discover", side_effect=discover), \
                     patch("control_tower.demo.demonstrate", return_value={"synthetic": True}) as demo, \
                     redirect_stdout(stdout), redirect_stderr(stderr):
                    code = verifier.main()
                summary = json.loads(stdout.getvalue())
                self.assertEqual(stderr.getvalue(), "")
                self.assertEqual(code, 1 if failing else 0)
                self.assertEqual(summary["passed"], not failing)
                self.assertEqual(summary["tests"]["run"], 1)
                self.assertEqual(summary["tests"]["failures"], int(failing))
                self.assertEqual(summary["tests"]["errors"], 0)
                self.assertEqual(demo.call_count, 0 if failing else 1)
                record = json.loads((root / "reports/result.json").read_text())
                checksum = record.pop("record_sha256")
                self.assertEqual(checksum, sha256(json.dumps(record, sort_keys=True,
                    separators=(",", ":")).encode()).hexdigest())
                self.assertEqual(summary["record_sha256"], checksum)
                self.assertEqual(summary["tests"], record["tests"])
                log = (root / "reports/result.txt").read_text()
                for marker in ("DISCOVERY_STDOUT", "FIXTURE_STDOUT", "FIXTURE_STDERR"):
                    self.assertIn(marker, log)
                    self.assertNotIn(marker, stdout.getvalue())
                self.assertIn("FAILED (failures=1)" if failing else "OK", log)
                if failing:
                    self.assertIn("FIXTURE_FAILURE", log)
