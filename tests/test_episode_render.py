"""Contract checks with mocked media processes; actual decode is a separate check."""
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave
from zipfile import ZipFile

from control_tower.episode import build_episode
from control_tower.episode_render import (FPS, SAMPLE_RATE, _wav, build_companion, bundle_episode,
    captions_vtt, edition_label, inspect_art, render_episode, validate_render_bundle)
from control_tower.network_contract import digest
from scripts.jarvis_episode import main

ROOT = Path(__file__).resolve().parents[1]
REVISION = "76e7a538d7c1a3a113d57727f025a2c6b27ccf13"
TEMPLATE = '''<!doctype html><html><body><img data-jarvis-inline-art="" hidden><video data-jarvis-inline-video=""><track data-jarvis-inline-captions=""></video><script type="application/json" id="episode-data">{}</script></body></html>'''


def png_header(width=1024, height=576):
    # Header-only fixture. Mocked FFmpeg does not decode it. Real render evidence
    # uses the actual supplied PNG and full FFmpeg video decoding.
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + struct.pack(">II", width, height) + b"\x08\x02\0\0\0" + b"\0" * 4


def source():
    return json.loads((ROOT / "examples/episodes/public-diary-source.json").read_text())


def compiled(value=None, audience="public"):
    return build_episode(value or source(), episode_id="test-episode", source_revision=REVISION, audience=audience)


def fake_process(arguments, folder):
    path = Path(folder) / arguments[-1]
    if path.suffix == ".wav":
        path.write_bytes(_wav(b"\0\0" * 1601))
    elif path.suffix == ".mp4":
        path.write_bytes(b"MOCK MEDIA PROCESS OUTPUT")
    else:
        raise AssertionError("unexpected subprocess output")


def rendered(episode=None):
    with patch("control_tower.episode_render._run", side_effect=fake_process), patch("control_tower.episode_render.shutil.which", return_value="/test/ffmpeg"), patch("control_tower.episode_render.FONT") as font, patch("control_tower.episode_render.music_bed", return_value=_wav(b"\0\0" * 1600)):
        font.is_file.return_value = True
        return render_episode(episode or compiled(), png_header())


class EpisodeRenderTests(unittest.TestCase):
    def test_invalid_episode_stops_before_media_dependencies(self):
        episode = compiled()
        episode["audience"] = "public"
        episode["source_visibility"] = "private"
        episode["episode_sha256"] = digest({k:v for k,v in episode.items() if k != "episode_sha256"})
        with patch("control_tower.episode_render._run") as process, self.assertRaisesRegex(ValueError, "public_candidate"):
            render_episode(episode, png_header())
        process.assert_not_called()

    def test_png_size_format_and_pixel_budget(self):
        self.assertEqual(1024, inspect_art(png_header())["width"])
        for art in (b"not an image", png_header(0, 1024), png_header(256, 9000), png_header(6000, 6000)):
            with self.subTest(art=art[:16]), self.assertRaises(ValueError):
                inspect_art(art)

    def test_owner_source_classification_is_visible_and_retained(self):
        for visibility in ("private", "internal", "public_candidate"):
            entry = source()
            entry["visibility"] = visibility
            episode = compiled(entry, "owner")
            files = rendered(episode)
            receipt = validate_render_bundle(episode, png_header(), files)
            self.assertEqual("owner", receipt["audience"])
            self.assertEqual(visibility, receipt["source_visibility"])
            self.assertTrue(files["transcript.txt"].startswith(edition_label(episode).encode()))
            self.assertEqual(visibility, json.loads(files["timeline.json"])["source_visibility"])

    def test_continuous_audio_frame_clock_and_nonoverlapping_captions(self):
        files = rendered()
        timeline = json.loads(files["timeline.json"])
        with wave.open(io.BytesIO(files["narration.wav"]), "rb") as audio:
            duration_ms = audio.getnframes() * 1000 / audio.getframerate()
            self.assertEqual(SAMPLE_RATE, audio.getframerate())
        self.assertEqual(duration_ms, timeline["duration_ms"])
        previous_end = 0
        for scene in timeline["scenes"]:
            self.assertEqual(previous_end, scene["start_ms"])
            self.assertEqual(scene["video_frames"] * 1000 / FPS, scene["end_ms"] - scene["start_ms"])
            previous_end = scene["end_ms"]
        previous_end = 0
        for cue in timeline["cues"]:
            self.assertGreaterEqual(cue["start_ms"], previous_end)
            self.assertGreater(cue["end_ms"], cue["start_ms"])
            previous_end = cue["end_ms"]
        self.assertLess(previous_end, duration_ms)

    def test_text_never_enters_filter_or_command_syntax(self):
        entry = source()
        attack = "$(touch /tmp/not-a-command); %{metadata:evil} ' , <script>fake</script>"
        entry["observations"][0]["text"] = attack
        episode = compiled(entry)
        seen_text, calls = [], []
        def inspect_process(arguments, folder):
            calls.append(arguments)
            path = Path(folder)
            seen_text.append((path / "utterance.txt").read_text())
            if arguments[-1].startswith("scene-"):
                seen_text.append((path / "title.txt").read_text())
                seen_text.append((path / "edition.txt").read_text())
            fake_process(arguments, folder)
        with patch("control_tower.episode_render._run", side_effect=inspect_process), patch("control_tower.episode_render.shutil.which", return_value="/test/ffmpeg"), patch("control_tower.episode_render.FONT") as font, patch("control_tower.episode_render.music_bed", return_value=_wav(b"\0\0" * 1600)):
            font.is_file.return_value = True
            render_episode(episode, png_header())
        self.assertIn("$(touch", " ".join(seen_text))
        self.assertIn("PUBLIC-CANDIDATE DRAFT", " ".join(seen_text))
        for arguments in calls:
            self.assertNotIn("$(touch", " ".join(arguments))
            if "-vf" in arguments:
                self.assertIn("expansion=none", arguments[arguments.index("-vf")+1])

    def test_vtt_escapes_markup_and_preserves_measured_times(self):
        result = captions_vtt([{"start_ms":125,"end_ms":1234,"text":"<script> & --> literal"}]).decode()
        self.assertIn("00:00:00.125 --> 00:00:01.234", result)
        self.assertIn("&lt;script&gt; &amp; --&gt; literal", result)
        self.assertNotIn("<script>", result)

    def test_receipt_rejects_changed_media_episode_art_and_classification(self):
        episode = compiled()
        files = rendered(episode)
        validate_render_bundle(episode, png_header(), files)
        modified = dict(files, **{"episode.mp4":b"other video"})
        with self.assertRaisesRegex(ValueError, "hash"):
            validate_render_bundle(episode, png_header(), modified)
        with self.assertRaisesRegex(ValueError, "artwork"):
            validate_render_bundle(episode, png_header(1025,576), files)
        other = compiled()
        other["audience"] = "owner"
        other["episode_sha256"] = digest({k:v for k,v in other.items() if k != "episode_sha256"})
        with self.assertRaisesRegex(ValueError, "episode"):
            validate_render_bundle(other, png_header(), files)

    def test_embedded_json_cannot_close_script_and_media_remain_inline(self):
        entry = source()
        entry["title"] = "</script><script>alert('literal diary text')</script>"
        episode = compiled(entry)
        files = rendered(episode)
        result = build_companion(episode,png_header(),files,TEMPLATE).decode()
        self.assertNotIn(entry["title"], result)
        self.assertEqual(1, result.count("</script>"))
        self.assertIn("data:video/mp4;base64,", result)
        self.assertIn("data:image/png;base64,", result)
        self.assertIn("data:text/vtt;base64,", result)
        self.assertIn('data-jarvis-inline-video="data:video/mp4;base64,', result)

    def test_receipt_cannot_change_render_kind_permissions_or_capabilities(self):
        episode, files = compiled(), rendered()
        for key, value in (("publication_approval","granted"),("model_calls",7),("character_lipsync",True),
                ("schema_version",False),("fps",10000),("news_status","verified_today"),("extra_field",True)):
            changed = dict(files)
            receipt = json.loads(changed["render_receipt.json"])
            receipt[key] = value
            changed["render_receipt.json"] = json.dumps(receipt).encode()
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_render_bundle(episode,png_header(),changed)

    def test_rehashed_timeline_cannot_erase_records_or_change_caption_clock(self):
        episode, files = compiled(), rendered()
        for mutation in ("empty-scenes","empty-cues","bad-rate","wrong-source","overlap","wrong-text","wrong-frames"):
            changed = dict(files)
            timeline = json.loads(changed["timeline.json"])
            if mutation == "empty-scenes": timeline["scenes"] = []
            elif mutation == "empty-cues": timeline["cues"] = []
            elif mutation == "bad-rate": timeline["sample_rate"] = 1
            elif mutation == "wrong-source": timeline["scenes"][1]["source_ids"] = []
            elif mutation == "overlap": timeline["cues"][1]["start_ms"] = 400
            elif mutation == "wrong-text": timeline["cues"][1]["text"] = "Different story"
            else: timeline["scenes"][1]["video_frames"] += 1
            changed["timeline.json"] = json.dumps(timeline).encode()
            receipt = json.loads(changed["render_receipt.json"])
            for item in receipt["files"]:
                if item["path"] == "timeline.json":
                    item.update(bytes=len(changed["timeline.json"]),sha256=sha256(changed["timeline.json"]).hexdigest())
            changed["render_receipt.json"] = json.dumps(receipt).encode()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_render_bundle(episode,png_header(),changed)

    def test_duplicate_render_keys_and_nonfinite_values_are_rejected(self):
        episode, files = compiled(), rendered()
        for name in ("render_receipt.json", "timeline.json"):
            for prefix in (b'{"schema_version":false,', b'{"schema_version":NaN,'):
                changed = dict(files)
                changed[name] = prefix + changed[name].lstrip()[1:]
                with self.subTest(name=name,prefix=prefix), self.assertRaisesRegex(ValueError, "invalid render metadata"):
                    validate_render_bundle(episode,png_header(),changed)

    def test_packager_requires_exact_empty_hooks_and_fixed_inventory(self):
        episode, art = compiled(), png_header()
        files = rendered(episode)
        for template in (TEMPLATE.replace('data-jarvis-inline-art=""',''), TEMPLATE + '<img data-jarvis-inline-art="">', TEMPLATE.replace('<video ', '<video src="https://example.org/x.mp4" ')):
            with self.subTest(template=template[-80:]), self.assertRaises(ValueError):
                build_companion(episode,art,files,template)
        with ZipFile(io.BytesIO(bundle_episode(episode,art,files,TEMPLATE))) as archive:
            self.assertEqual(10, len(archive.namelist()))
            self.assertEqual(episode,json.loads(archive.read("episode.json")))
            self.assertEqual(art,archive.read("art.png"))
            self.assertIn(b"data:video/mp4;base64,",archive.read("watch-and-play.html"))


class EpisodeCLITests(unittest.TestCase):
    def call(self, root, *arguments):
        with patch("sys.stdout",new_callable=io.StringIO) as out,patch("sys.stderr",new_callable=io.StringIO) as err:
            code=main(["--root",str(root),*arguments])
        return code,out.getvalue(),err.getvalue()

    def args(self, command, output):
        return [command,"--entry-file","entry.json","--source-revision",REVISION,"--episode","test-episode","--out",output]

    def test_compile_does_not_render_and_owner_requires_explicit_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            entry=source()
            entry["visibility"]="private"
            (root/"entry.json").write_text(json.dumps(entry))
            with patch("scripts.jarvis_episode.render_episode") as renderer:
                code,out,err=self.call(root,*self.args("compile","default.json"))
                self.assertEqual(1,code)
                self.assertFalse((root/"default.json").exists())
                code,out,err=self.call(root,*self.args("compile","owner.json"),"--audience","owner")
                self.assertEqual(0,code,err)
                renderer.assert_not_called()
                self.assertEqual("owner",json.loads(out)["audience"])
                self.assertEqual("private",json.loads((root/"owner.json").read_text())["source_visibility"])

    def test_output_and_art_path_escape_fail_before_render(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"entry.json").write_text(json.dumps(source()))
            (root/"keep.zip").write_bytes(b"keep")
            for output,art in (("keep.zip","art.png"),("../outside.zip","art.png"),("wrong.json","art.png"),("fresh.zip","../outside.png")):
                with self.subTest(output=output,art=art),patch("scripts.jarvis_episode.render_episode") as renderer:
                    code,_,_=self.call(root,*self.args("render",output),"--art-file",art)
                    self.assertEqual(1,code)
                    renderer.assert_not_called()
            self.assertEqual(b"keep",(root/"keep.zip").read_bytes())

    def test_renderer_failure_leaves_no_partial_output_or_private_error_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"entry.json").write_text(json.dumps(source()))
            (root/"art.png").write_bytes(png_header())
            with patch("scripts.jarvis_episode.render_episode",side_effect=OSError("sensitive test path")):
                code,_,err=self.call(root,*self.args("render","failed.zip"),"--art-file","art.png")
            self.assertEqual(1,code)
            self.assertNotIn("sensitive test path",err)
            self.assertFalse((root/"failed.zip").exists())

    def test_owner_render_pack_uses_selected_entry_and_retains_classification(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            entry=source()
            entry["visibility"]="private"
            episode=compiled(entry,"owner")
            files=rendered(episode)
            (root/"entry.json").write_text(json.dumps(entry))
            (root/"art.png").write_bytes(png_header())
            with patch("scripts.jarvis_episode.render_episode",return_value=files):
                code,out,err=self.call(root,*self.args("render","owner.zip"),"--art-file","art.png","--audience","owner")
            self.assertEqual(0,code,err)
            self.assertTrue(json.loads(out)["rendered"])
            with ZipFile(root/"owner.zip") as archive:
                self.assertEqual(episode,json.loads(archive.read("episode.json")))
                self.assertIn(b'"source_visibility":"private"',archive.read("watch-and-play.html"))
                self.assertTrue(archive.read("READ-ME.txt").startswith(b"OWNER EDITION / PRIVATE SOURCE"))


if __name__ == "__main__":
    unittest.main()
