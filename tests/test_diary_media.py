from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave
from xml.etree import ElementTree as ET
from zipfile import ZIP_STORED, ZipFile

from control_tower.diary import validate_diary_entry
from control_tower.media import build_media_files, bundle_media, music_bed
from control_tower.media_render import _run, render_previews
from control_tower.network_contract import canonical, digest, validate_draft

ROOT = Path(__file__).resolve().parents[1]
REVISION = "e645c64975dc05f3b0a0f9e06d7cc903d70031b0"
TIMESTAMP = "2026-10-22T22:00:00Z"


def entry():
    return json.loads((ROOT / "examples/diary/public-project-entry.json").read_text())


def build(value=None, **kwargs):
    return build_media_files(value or entry(), product_id="diary-media-example", source_revision=REVISION,
                             edition_timestamp=TIMESTAMP, **kwargs)


class DiaryMediaTests(unittest.TestCase):
    def test_manifest_describes_actual_files_and_retains_source_identity(self):
        original = entry()
        files = build(original)
        self.assertEqual(18, len(files))
        manifest = json.loads(files["manifest.json"])
        self.assertEqual(digest(original), manifest["source_entry_sha256"])
        self.assertEqual(original, json.loads(files["source_entry.json"]))
        self.assertEqual(0, manifest["model_calls"])
        self.assertEqual(0, manifest["external_actions"])
        self.assertIsNone(manifest["actual_revenue"])
        self.assertEqual({k for k in files if k != "manifest.json"}, {f["path"] for f in manifest["files"]})
        for item in manifest["files"]:
            self.assertEqual(len(files[item["path"]]), item["bytes"])
            self.assertEqual(sha256(files[item["path"]]).hexdigest(), item["sha256"])
        self.assertEqual(digest({k: v for k, v in manifest.items() if k != "manifest_sha256"}), manifest["manifest_sha256"])

    def test_private_and_internal_entries_fail_before_audio_generation(self):
        for visibility in ("private", "internal"):
            value = entry()
            value["visibility"] = visibility
            with self.subTest(visibility=visibility), patch("control_tower.media.music_bed") as synthesizer:
                with self.assertRaisesRegex(ValueError, "public_candidate"):
                    build(value)
                synthesizer.assert_not_called()

    def test_pack_is_reproducible_with_explicit_edition_timestamp(self):
        first, second = build(), build()
        self.assertEqual(first, second)
        self.assertEqual(first, build(json.loads(json.dumps(entry(), sort_keys=True))))
        self.assertEqual(bundle_media(first), bundle_media(second))

    def test_epub_container_metadata_manifest_navigation_and_spine(self):
        with ZipFile(io.BytesIO(build()["book.epub"])) as archive:
            first = archive.infolist()[0]
            self.assertEqual("mimetype", first.filename)
            self.assertEqual(ZIP_STORED, first.compress_type)
            self.assertEqual(b"", first.extra)
            self.assertEqual(0, first.flag_bits & 1)
            self.assertEqual(b"application/epub+zip", archive.read("mimetype"))
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            node = container.find("{urn:oasis:names:tc:opendocument:xmlns:container}rootfiles/{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
            self.assertEqual("application/oebps-package+xml", node.attrib["media-type"])
            opf = ET.fromstring(archive.read(node.attrib["full-path"]))
            ns = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/", "x": "http://www.w3.org/1999/xhtml"}
            self.assertEqual("3.0", opf.attrib["version"])
            identifier = opf.find("opf:metadata/dc:identifier", ns)
            self.assertEqual(identifier.attrib["id"], opf.attrib["unique-identifier"])
            self.assertEqual(TIMESTAMP, opf.find("opf:metadata/opf:meta", ns).text)
            resources = {i.attrib["id"]: i for i in opf.findall("opf:manifest/opf:item", ns)}
            for resource in resources.values():
                ET.fromstring(archive.read("EPUB/" + resource.attrib["href"]))
            for spine in opf.findall("opf:spine/opf:itemref", ns):
                self.assertIn(spine.attrib["idref"], resources)
            navigation = [i for i in resources.values() if i.attrib.get("properties") == "nav"]
            self.assertEqual(1, len(navigation))
            nav = ET.fromstring(archive.read("EPUB/" + navigation[0].attrib["href"]))
            for link in nav.findall(".//x:a", ns):
                self.assertIn("EPUB/" + link.attrib["href"], archive.namelist())

    def test_ssml_preserves_text_as_xml_data_and_uses_required_namespace(self):
        value = entry()
        value["summary"] = 'Text <audio src="https://example.org"> & "quoted" content.'
        files = build(value)
        speak = ET.fromstring(files["narration.ssml"])
        self.assertEqual("{http://www.w3.org/2001/10/synthesis}speak", speak.tag)
        self.assertEqual("1.1", speak.attrib["version"])
        self.assertEqual("en-US", speak.attrib["{http://www.w3.org/XML/1998/namespace}lang"])
        self.assertFalse(speak.findall(".//{http://www.w3.org/2001/10/synthesis}audio"))
        self.assertIn(value["summary"], " ".join(speak.itertext()))

    def test_xml_ineligible_text_rejects_without_mutating_diary(self):
        for character in ("\ufffe", "\uffff"):
            value = entry()
            value["media_notes"]["visual_style"] += character
            before = deepcopy(value)
            validate_diary_entry(value)
            with self.assertRaisesRegex(ValueError, "XML"):
                build(value)
            self.assertEqual(before, value)

    def test_all_fiction_or_reported_entries_do_not_become_source_linked(self):
        for state in ("fictional", "owner_reported"):
            value = entry()
            value["sources"] = []
            for observation in value["observations"]:
                observation.update(evidence_state=state, source_ids=[])
            files = build(value)
            with ZipFile(io.BytesIO(files["book.epub"])) as archive:
                body = archive.read("EPUB/book.xhtml").decode()
            self.assertIn("Selected diary edition", body)
            self.assertNotIn("Source-linked project diary edition", body)
            self.assertIn("No source-linked claims", files["ad_copy.md"].decode())

    def test_planned_and_fictional_records_are_excluded_from_ad_claims(self):
        value = entry()
        value["observations"][2].update(text="PRIVATE-FICTION-CLAIM-MARKER", evidence_state="fictional", source_ids=[])
        files = build(value)
        self.assertNotIn("PRIVATE-FICTION-CLAIM-MARKER", files["ad_copy.md"].decode())
        self.assertIn("Fiction; not a factual event", files["diary.md"].decode())
        self.assertIn("fictional", files["movie_treatment.md"].decode().lower())
        self.assertIn("fictional", files["music_film.md"].decode().lower())

    def test_unassigned_affiliate_destination_stays_unassigned(self):
        value = entry()
        value["initiative_id"] = "affiliate-builder"
        content = build(value)["ad_copy.md"].decode()
        self.assertIn("unassigned", content)
        self.assertNotIn("aievolutionaryevolutions.com", content)

    def test_html_data_roundtrip_escapes_closing_script_and_dom_uses_text(self):
        value = entry()
        value["summary"] = '</script><script>fetch("https://example.org")</script>& <img src=x>'
        content = build(value)["interactive_book.html"].decode()
        scripts = re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", content)
        self.assertEqual(3, len(scripts))
        data = json.loads(scripts[0])
        self.assertEqual(value["summary"], data["summary"])
        self.assertNotIn("innerHTML", scripts[2])
        self.assertNotIn("localStorage", content)
        self.assertNotIn("sessionStorage", content)
        source = (ROOT / "control_tower/media.py").read_text()
        helper = re.search(r'<script id="media-helper">([\s\S]+?)</script>', source).group(1)
        self.assertEqual(helper, scripts[1])

    def test_timeline_is_shared_and_vtt_has_no_injected_blocks(self):
        value = entry()
        value["observations"][0]["text"] = "A --> B\n\nWEBVTT <script> & end"
        files = build(value, duration_seconds=15)
        cues = json.loads(files["trailer_cues.json"])["cues"]
        self.assertEqual(0, cues[0]["start_ms"])
        self.assertEqual(15000, cues[-1]["end_ms"])
        for first, second in zip(cues, cues[1:]):
            self.assertEqual(first["end_ms"], second["start_ms"])
        vtt = files["trailer_text.vtt"].decode()
        self.assertTrue(vtt.startswith("WEBVTT\n\n"))
        self.assertEqual(4, len(re.findall(r"^\d\d:\d\d:\d\d\.\d{3} --> \d\d:\d\d:\d\d\.\d{3}$", vtt, re.MULTILINE)))
        self.assertIn("A --&gt; B", vtt)
        self.assertNotIn("<script>", vtt)

    def test_synthesized_music_has_declared_pcm_format_and_bounded_level(self):
        with wave.open(io.BytesIO(music_bed(15)), "rb") as audio:
            self.assertEqual((1, 2, 16000, 240000), (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()))
            frames = audio.readframes(audio.getnframes())
        samples = [value[0] for value in __import__("struct").iter_unpack("<h", frames)]
        self.assertGreater(max(samples), 0)
        self.assertLess(max(abs(v) for v in samples), 5000)
        self.assertEqual(0, samples[0])

    def test_large_and_escape_heavy_valid_entries_fit_handoff(self):
        for text in ("x" * 1000, "\n" * 999 + "x", '"' * 1000, "字" * 333):
            value = entry()
            value["summary"] = "S" * 3000
            value["observations"] = [{"observation_id": f"record-{i}", "text": text, "evidence_state": "planned", "source_ids": []} for i in range(8)]
            value["next_action"] = "N" * 1500
            value["media_notes"] = {k: "M" * 600 for k in value["media_notes"]}
            files = build(value, duration_seconds=15)
            handoff = validate_draft(json.loads(files["media_handoff.json"]))
            self.assertLess(len(handoff["text"].encode()), 5000)
            self.assertIn("does not contain the full diary", handoff["text"])
            self.assertEqual(value, json.loads(files["source_entry.json"]))

    def test_invalid_build_parameters_are_controlled(self):
        for changes in ({"duration_seconds": True}, {"duration_seconds": 16}, {"target": "unknown"}, {"edition_timestamp": "2026-02-30T00:00:00Z"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                parameters = dict(product_id="sample-product", source_revision=REVISION, edition_timestamp=TIMESTAMP)
                parameters.update(changes)
                build_media_files(entry(), **parameters)
        for bad in ("main", "F" * 40, None):
            with self.assertRaises(ValueError):
                build_media_files(entry(), product_id="sample-product", source_revision=bad)

    def test_zip_has_fixed_names_and_foreign_paths_are_rejected(self):
        files = build()
        with ZipFile(io.BytesIO(bundle_media(files))) as archive:
            self.assertEqual(set(files), set(archive.namelist()))
            self.assertEqual(files["source_entry.json"], archive.read("source_entry.json"))
        files["../private.txt"] = b"no"
        with self.assertRaises(ValueError):
            bundle_media(files)

    def test_bundle_checks_base_manifest_before_packaging(self):
        files = build()
        changed = dict(files)
        changed["diary.md"] += b"altered after compilation"
        with self.assertRaisesRegex(ValueError, "manifest"):
            bundle_media(changed)
        changed = dict(files)
        changed["manifest.json"] = b'[]'
        with self.assertRaisesRegex(ValueError, "evidence record"):
            bundle_media(changed)


class LocalRendererTests(unittest.TestCase):
    def test_bundle_binds_receipt_duration_hashes_and_exact_types(self):
        def fake_run(args, directory):
            (directory / args[-1]).write_bytes(b"synthetic test output")
        with patch("control_tower.media_render.shutil.which", return_value="/trusted/ffmpeg"), patch("control_tower.media_render.FONT", ROOT / "README.md"), patch("control_tower.media_render._run", side_effect=fake_run):
            result = render_previews(entry(), product_id="preview-test", source_revision=REVISION, duration_seconds=15)
        base = build(duration_seconds=15)
        with self.assertRaisesRegex(ValueError, "duration"):
            bundle_media(build(duration_seconds=60), previews=result)
        altered = dict(result)
        altered["preview.mp4"] += b"changed"
        with self.assertRaisesRegex(ValueError, "receipt does not match"):
            bundle_media(base, previews=altered)
        original = json.loads(result["render_receipt.json"])
        variants = []
        for key, value in (("schema_version", True), ("external_actions", False), ("expected_video_duration_seconds", 15.0), ("files", [])):
            record = deepcopy(original)
            record[key] = value
            variants.append(json.dumps(record).encode())
        record = deepcopy(original)
        record["files"][0]["bytes"] = float(record["files"][0]["bytes"])
        variants.append(json.dumps(record).encode())
        variants.extend([b'[]', b'{"schema_version":1,"schema_version":1}', b'{"value":NaN}'])
        for raw in variants:
            with self.subTest(raw=raw[:70]), self.assertRaises(ValueError):
                bundle_media(base, previews={**result, "render_receipt.json": raw})

    def test_private_selection_never_invokes_renderer(self):
        value = entry()
        value["visibility"] = "private"
        with patch("control_tower.media_render._run") as runner, self.assertRaises(ValueError):
            render_previews(value, product_id="preview-test", source_revision=REVISION)
        runner.assert_not_called()

    def test_missing_dependency_returns_controlled_error(self):
        with patch("control_tower.media_render.shutil.which", return_value=None), self.assertRaisesRegex(ValueError, "FFmpeg"):
            render_previews(entry(), product_id="preview-test", source_revision=REVISION, duration_seconds=15)

    def test_source_text_never_enters_filter_or_shell_arguments(self):
        value = entry()
        marker = "%{eif:1+2:d}; $(never_run) ' :"
        value["observations"][0]["text"] = marker
        calls = []
        def fake_run(args, directory):
            calls.append(args)
            self.assertNotIn(marker, " ".join(args))
            if args[-1] == "preview.mp4":
                self.assertIn(marker, (directory / "scene-01.txt").read_text())
                self.assertIn("expansion=none", " ".join(args))
                (directory / "preview.mp4").write_bytes(b"synthetic test output")
            else:
                (directory / "narration.wav").write_bytes(b"synthetic test output")
        with patch("control_tower.media_render.shutil.which", return_value="/trusted/ffmpeg"), patch("control_tower.media_render.FONT", ROOT / "README.md"), patch("control_tower.media_render._run", side_effect=fake_run):
            result = render_previews(value, product_id="preview-test", source_revision=REVISION, duration_seconds=15)
        self.assertEqual(2, len(calls))
        self.assertEqual({"preview.mp4", "narration.wav", "render_receipt.json"}, set(result))
        self.assertEqual("not_implemented; storyboard text cues are separate", json.loads(result["render_receipt.json"])["speech_alignment"])
        with ZipFile(io.BytesIO(bundle_media(build(value, duration_seconds=15), previews=result))) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(20, len(manifest["files"]))
        result["render_receipt.json"] = result["render_receipt.json"].replace(REVISION.encode(), b"0" * 40)
        with self.assertRaisesRegex(ValueError, "source"):
            bundle_media(build(value, duration_seconds=15), previews=result)

    def test_subprocess_failures_are_sanitized_and_timeout_is_bounded(self):
        for failure in (OSError("secret-path"), subprocess.TimeoutExpired(["private-command"], 45)):
            with patch("control_tower.media_render.subprocess.run", side_effect=failure) as process, self.assertRaisesRegex(ValueError, "unavailable or timed out"):
                _run(["ffmpeg", "fixed"], Path("."))
            self.assertFalse(process.call_args.kwargs["shell"])
            self.assertEqual(45, process.call_args.kwargs["timeout"])
        with patch("control_tower.media_render.subprocess.run", return_value=subprocess.CompletedProcess([], 1)), self.assertRaisesRegex(ValueError, "failed"):
            _run(["ffmpeg"], Path("."))


if __name__ == "__main__":
    unittest.main()
