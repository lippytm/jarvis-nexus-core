"""Local anime-inspired motion-comic rendering and offline RPG packaging.

The renderer uses one supplied PNG, generic Flite speech and an original local
oscillator score. It does not call a model, publish, authenticate sources or
perform character animation. Text always enters FFmpeg through fixed files.
"""
import base64
from hashlib import sha256
import html
import io
import json
from pathlib import Path
import re
import shutil
import struct
import tempfile
import textwrap
import wave
from zipfile import ZIP_DEFLATED, ZipFile

from control_tower.episode import validate_episode
from control_tower.media import music_bed
from control_tower.media_render import FONT, _run
from control_tower.network_contract import _invalid_constant, _unique_object, canonical

SAMPLE_RATE = 16000
FPS = 24
MAX_SECONDS = 240
MAX_FILE_BYTES = 50 * 1024 * 1024
RENDER_FILES = frozenset({"episode.mp4", "narration.wav", "captions.vtt", "transcript.txt", "timeline.json"})
WORLD_COLORS = {"archive": "0xf7c978", "forge": "0xffad75", "observatory": "0x8ee3e0"}


def _json(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _bounded_bytes(value, limit=MAX_FILE_BYTES):
    if type(value) is not bytes or not 0 < len(value) <= limit:
        raise ValueError("empty or oversized episode asset")
    return value


def inspect_art(art):
    """Bound a still PNG before handing it to the optional local decoder."""
    _bounded_bytes(art, 20 * 1024 * 1024)
    if len(art) < 33 or art[:8] != b"\x89PNG\r\n\x1a\n" or art[8:16] != b"\x00\x00\x00\rIHDR":
        raise ValueError("episode artwork must be a PNG with an IHDR header")
    width, height = struct.unpack(">II", art[16:24])
    if not 256 <= width <= 8192 or not 256 <= height <= 8192 or width * height > 12_000_000:
        raise ValueError("episode artwork dimensions exceed bounds")
    return {"width": width, "height": height, "sha256": sha256(art).hexdigest()}


def edition_label(episode):
    if episode["audience"] == "owner":
        return "OWNER EDITION / " + episode["source_visibility"].replace("_", " ").upper() + " SOURCE"
    return "PUBLIC-CANDIDATE DRAFT / PROJECT PILOT"


def utterances(text):
    """Short spoken chunks are the measured caption units, not word alignment."""
    normalized = " ".join(text.split())
    return textwrap.wrap(normalized, width=110, break_long_words=True, break_on_hyphens=False)


def _stamp(milliseconds):
    hours, remaining = divmod(milliseconds, 3600000)
    minutes, remaining = divmod(remaining, 60000)
    seconds, milliseconds = divmod(remaining, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def captions_vtt(cues):
    lines = ["WEBVTT", "", "NOTE Captions follow measured synthetic utterances, not word alignment.", ""]
    for index, cue in enumerate(cues, 1):
        lines.extend([str(index), _stamp(cue["start_ms"]) + " --> " + _stamp(cue["end_ms"]),
                      html.escape(cue["text"], quote=False), ""])
    return ("\n".join(lines) + "\n").encode("utf-8")


def _pcm(path):
    try:
        with wave.open(str(path), "rb") as source:
            if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (1, 2, SAMPLE_RATE, "NONE"):
                raise ValueError("unexpected narration audio format")
            if not 0 < source.getnframes() <= 30 * SAMPLE_RATE:
                raise ValueError("narration utterance exceeds duration bound")
            frames = source.readframes(source.getnframes())
            if len(frames) != source.getnframes() * 2:
                raise ValueError("incomplete narration audio")
            return frames
    except (wave.Error, EOFError):
        raise ValueError("invalid narration audio") from None


def _wav(pcm):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE)
        audio.writeframes(pcm)
    return output.getvalue()


def _text_file(folder, name, value, width=62, max_lines=3):
    lines = []
    for line in value.splitlines():
        lines.extend(textwrap.wrap(line, width=width, break_long_words=True, break_on_hyphens=False))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][:max(1, width - 3)] + "..."
    (folder / name).write_text("\n".join(lines), encoding="utf-8")


def _draw(name, *, x, y, size, color="0xf2f6ff", enable=None):
    value = f"drawtext=fontfile={FONT}:textfile={name}:expansion=none:fontcolor={color}:fontsize={size}:line_spacing=8:x={x}:y={y}"
    if enable is not None:
        value += f":enable='{enable}'"
    return value


def render_episode(episode, art):
    """Return actual local MP4/WAV/VTT assets and a content-bound receipt.

    An episode is an internally validated draft. The CLI compiles it directly
    from the selected diary; this lower-level API cannot authenticate a source.
    Each scene is aligned to an exact number of video frames before one continuous
    narration track is muxed. No per-scene AAC padding enters the caption clock.
    """
    episode = validate_episode(episode)
    art_info = inspect_art(art)
    executable = shutil.which("ffmpeg")
    if executable is None or not FONT.is_file():
        raise ValueError("local FFmpeg with Flite, libx264 and the documented font is required")
    common = [executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-n"]
    timeline_scenes, cues, full_pcm = [], [], bytearray()
    with tempfile.TemporaryDirectory(prefix="jarvis-episode-") as directory:
        folder = Path(directory)
        (folder / "art.png").write_bytes(art)
        (folder / "music.wav").write_bytes(music_bed(30))
        _text_file(folder, "brand.txt", "JARVIS / MULTIVERSE DIARY", 80, 1)
        _text_file(folder, "edition.txt", edition_label(episode), 90, 1)
        for index, scene in enumerate(episode["scenes"]):
            scene_start = len(full_pcm) // 2
            scene_pcm = bytearray(b"\0\0" * 6400)
            scene_cues = []
            for chunk_index, text in enumerate(utterances(scene["voiceover"])):
                # Fixed paths and a fixed filter; arbitrary diary text is never
                # parsed as a shell command, filter expression or filename.
                (folder / "utterance.txt").write_text(text, encoding="utf-8")
                speech_name = f"speech-{index:02d}-{chunk_index:02d}.wav"
                _run(common + ["-f", "lavfi", "-i", "flite=textfile=utterance.txt:voice=slt",
                    "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", speech_name], folder)
                pcm = _pcm(folder / speech_name)
                start = scene_start + len(scene_pcm) // 2
                end = start + len(pcm) // 2
                cue = {"scene_id": scene["scene_id"], "start_ms": round(start * 1000 / SAMPLE_RATE),
                       "end_ms": round(end * 1000 / SAMPLE_RATE), "text": text}
                cues.append(cue)
                scene_cues.append(cue)
                scene_pcm.extend(pcm)
                scene_pcm.extend(b"\0\0" * 2400)
            scene_pcm.extend(b"\0\0" * 4800)
            # 2000 samples at 16 kHz are exactly three frames at 24 fps.
            padding = (-len(scene_pcm) // 2) % 2000
            scene_pcm.extend(b"\0\0" * padding)
            scene_samples = len(scene_pcm) // 2
            if scene_start + scene_samples > MAX_SECONDS * SAMPLE_RATE:
                raise ValueError("episode exceeds four-minute local render budget")
            full_pcm.extend(scene_pcm)
            duration = scene_samples / SAMPLE_RATE
            frames = scene_samples * FPS // SAMPLE_RATE
            world = next(item for item in episode["worlds"] if item["world_id"] == scene["world_id"])
            color = WORLD_COLORS[scene["world_id"]]
            _text_file(folder, "title.txt", scene["title"], 48, 2)
            _text_file(folder, "world.txt", world["title"].upper(), 70, 1)
            _text_file(folder, "state.txt", scene["evidence_state"].replace("_", " ").upper(), 45, 1)
            _text_file(folder, "scene.txt", f"CHAPTER {index + 1:02d} / {len(episode['scenes']):02d}   |   {episode['date']}", 80, 1)
            filters = [
                "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
                "zoompan=z='min(1.10,1.03+on*0.00008)':x='iw/2-iw/zoom/2+sin(on/100)*12':y='ih/2-ih/zoom/2':d=1:s=1280x720:fps=24",
                "drawbox=x=0:y=0:w=810:h=178:color=0x071121@0.85:t=fill",
                "drawbox=x=840:y=0:w=440:h=106:color=0x071121@0.85:t=fill",
                "drawbox=x=0:y=528:w=1280:h=192:color=0x071121@0.92:t=fill",
                f"drawbox=x=34:y=38:w=4:h=107:color={color}:t=fill",
                _draw("brand.txt", x=54, y=24, size=16, color=color),
                _draw("title.txt", x=54, y=56, size=30),
                _draw("world.txt", x=54, y=140, size=15, color=color),
                _draw("state.txt", x=860, y=30, size=17, color=color),
                _draw("scene.txt", x=860, y=65, size=14),
                _draw("edition.txt", x=34, y=687, size=13, color="0xbdc9da"),
                "drawbox=x=34:y=660:w=1212:h=3:color=0x344258:t=fill",
                f"drawbox=x=34:y=660:w={round(1212 * (index + 1) / len(episode['scenes']))}:h=3:color={color}:t=fill",
            ]
            for cue_index, cue in enumerate(scene_cues):
                name = f"caption-{cue_index:02d}.txt"
                _text_file(folder, name, cue["text"], 74, 3)
                start = cue["start_ms"] / 1000 - scene_start / SAMPLE_RATE
                end = cue["end_ms"] / 1000 - scene_start / SAMPLE_RATE
                filters.append(_draw(name, x=34, y=550, size=26, enable=f"gte(t,{start:.3f})*lt(t,{end:.3f})"))
            filters.extend([f"fade=t=in:st=0:d=0.15", f"fade=t=out:st={max(0, duration - 0.15):.3f}:d=0.15"])
            _run(common + ["-protocol_whitelist", "file,pipe", "-loop", "1", "-framerate", str(FPS), "-i", "art.png",
                "-vf", ",".join(filters), "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "24", "-pix_fmt", "yuv420p", "-threads", "2", f"scene-{index:02d}.mp4"], folder)
            timeline_scenes.append({"scene_id": scene["scene_id"], "start_ms": round(scene_start * 1000 / SAMPLE_RATE),
                "end_ms": round((scene_start + scene_samples) * 1000 / SAMPLE_RATE), "video_frames": frames,
                "world_id": scene["world_id"], "evidence_state": scene["evidence_state"], "source_ids": scene["source_ids"]})
        duration = len(full_pcm) / (2 * SAMPLE_RATE)
        narration = _wav(bytes(full_pcm))
        (folder / "narration.wav").write_bytes(narration)
        (folder / "scenes.txt").write_text("".join(f"file 'scene-{index:02d}.mp4'\n" for index in range(len(timeline_scenes))), encoding="ascii")
        _run(common + ["-protocol_whitelist", "file,pipe", "-f", "concat", "-safe", "1", "-i", "scenes.txt",
            "-protocol_whitelist", "file,pipe", "-i", "narration.wav", "-stream_loop", "-1", "-i", "music.wav",
            "-filter_complex", "[1:a]volume=1.5[voice];[2:a]volume=0.12[bed];[voice][bed]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:latency=1[audio]",
            "-map", "0:v:0", "-map", "[audio]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-t", f"{duration:.3f}", "-movflags", "+faststart", "episode.mp4"], folder)
        video_path = folder / "episode.mp4"
        if video_path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("rendered episode exceeds file bounds")
        video = _bounded_bytes(video_path.read_bytes())
    timeline = {"schema_version": 1, "kind": "jarvis.episode_timeline", "episode_sha256": episode["episode_sha256"],
        "audience": episode["audience"], "source_visibility": episode["source_visibility"],
        "sample_rate": SAMPLE_RATE, "fps": FPS, "duration_ms": round(duration * 1000),
        "caption_timing": "measured_synthetic_utterances", "scenes": timeline_scenes, "cues": cues}
    transcript = [edition_label(episode), episode["title"], episode["date"], "", episode["fictional_framing"], ""]
    for scene in episode["scenes"]:
        transcript.extend([scene["title"], "Evidence: " + scene["evidence_state"], scene["voiceover"],
                           "Source IDs: " + (", ".join(scene["source_ids"]) or "none"), ""])
    transcript.extend(["Source references (supplied; not authenticated by this renderer):", *[source["title"] + "\n" + source["url"] for source in episode["sources"]]])
    output = {"episode.mp4": video, "narration.wav": narration, "captions.vtt": captions_vtt(cues),
              "transcript.txt": ("\n".join(transcript) + "\n").encode("utf-8"), "timeline.json": _json(timeline)}
    receipt = {"schema_version": 1, "kind": "jarvis.episode_render_receipt", "episode_sha256": episode["episode_sha256"],
        "source_entry_sha256": episode["source_entry_sha256"], "source_context_revision": episode["source_context_revision"],
        "audience": episode["audience"], "source_visibility": episode["source_visibility"], "art": art_info,
        "render_kind": "anime_inspired_motion_comic", "narration_kind": "generic_local_flite_slt",
        "caption_timing": "measured_synthetic_utterances", "character_lipsync": False,
        "duration_ms": timeline["duration_ms"], "fps": FPS, "resolution": [1280, 720],
        "news_status": episode["news_status"], "publication_approval": "not_granted", "external_actions": 0, "model_calls": 0,
        "files": [{"path": name, "bytes": len(content), "sha256": sha256(content).hexdigest()} for name, content in sorted(output.items())]}
    output["render_receipt.json"] = _json(receipt)
    return output


def validate_render_bundle(episode, art, files):
    """Check packet/art/media identity before embedding or packaging a render."""
    episode = validate_episode(episode)
    art_info = inspect_art(art)
    if type(files) is not dict or set(files) != RENDER_FILES | {"render_receipt.json"}:
        raise ValueError("unexpected render file inventory")
    for content in files.values():
        _bounded_bytes(content)
    for name in ("render_receipt.json", "timeline.json"):
        _bounded_bytes(files[name], 65536)
    try:
        receipt = json.loads(files["render_receipt.json"], object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        timeline = json.loads(files["timeline.json"], object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("invalid render metadata") from None
    receipt_keys = {"schema_version", "kind", "episode_sha256", "source_entry_sha256", "source_context_revision",
        "audience", "source_visibility", "art", "render_kind", "narration_kind", "caption_timing", "character_lipsync",
        "duration_ms", "fps", "resolution", "news_status", "publication_approval", "external_actions", "model_calls", "files"}
    timeline_keys = {"schema_version", "kind", "episode_sha256", "audience", "source_visibility", "sample_rate",
        "fps", "duration_ms", "caption_timing", "scenes", "cues"}
    _exact(receipt, receipt_keys)
    _exact(timeline, timeline_keys)
    for record, fixed in ((receipt, {"schema_version": 1, "kind": "jarvis.episode_render_receipt",
        "render_kind": "anime_inspired_motion_comic", "narration_kind": "generic_local_flite_slt",
        "caption_timing": "measured_synthetic_utterances", "character_lipsync": False,
        "fps": FPS, "news_status": episode["news_status"], "publication_approval": "not_granted", "external_actions": 0, "model_calls": 0}),
        (timeline, {"schema_version": 1, "kind": "jarvis.episode_timeline", "sample_rate": SAMPLE_RATE,
        "fps": FPS, "caption_timing": "measured_synthetic_utterances"})):
        for key, expected_value in fixed.items():
            if type(record[key]) is not type(expected_value) or record[key] != expected_value:
                raise ValueError("invalid render metadata semantics")
    if type(receipt["resolution"]) is not list or receipt["resolution"] != [1280, 720] or any(type(n) is not int for n in receipt["resolution"]):
        raise ValueError("invalid render resolution")
    for key in ("episode_sha256", "source_entry_sha256", "source_context_revision", "audience", "source_visibility"):
        if receipt.get(key) != episode[key]:
            raise ValueError("render receipt does not match episode")
    if receipt.get("art") != art_info or receipt.get("kind") != "jarvis.episode_render_receipt":
        raise ValueError("render receipt does not match artwork")
    expected = [{"path": name, "bytes": len(files[name]), "sha256": sha256(files[name]).hexdigest()} for name in sorted(RENDER_FILES)]
    if receipt.get("files") != expected:
        raise ValueError("render receipt file hash mismatch")
    for key in ("episode_sha256", "audience", "source_visibility"):
        if timeline.get(key) != episode[key]:
            raise ValueError("render timeline does not match episode")
    if (type(timeline.get("duration_ms")) is not int or not 0 < timeline["duration_ms"] <= MAX_SECONDS * 1000
            or type(receipt.get("duration_ms")) is not int or receipt.get("duration_ms") != timeline["duration_ms"]):
        raise ValueError("invalid render duration")
    _validate_timeline(episode, timeline, files)
    return receipt


def _exact(value, keys):
    if type(value) is not dict or set(value) != keys:
        raise ValueError("invalid render metadata fields")


def _validate_timeline(episode, timeline, files):
    scenes, cues = timeline["scenes"], timeline["cues"]
    if type(scenes) is not list or len(scenes) != len(episode["scenes"]) or type(cues) is not list:
        raise ValueError("invalid render timeline inventory")
    expected_cues, previous_end = [], 0
    for rendered, source in zip(scenes, episode["scenes"]):
        _exact(rendered, {"scene_id", "start_ms", "end_ms", "video_frames", "world_id", "evidence_state", "source_ids"})
        for key in ("scene_id", "world_id", "evidence_state", "source_ids"):
            if rendered[key] != source[key]:
                raise ValueError("timeline scene differs from episode")
        if (any(type(rendered[key]) is not int for key in ("start_ms", "end_ms", "video_frames"))
                or rendered["start_ms"] != previous_end or not rendered["start_ms"] < rendered["end_ms"] <= timeline["duration_ms"]
                or rendered["end_ms"] % 125 or rendered["video_frames"] * 1000 != (rendered["end_ms"] - rendered["start_ms"]) * FPS):
            raise ValueError("invalid scene frame timing")
        previous_end = rendered["end_ms"]
        expected_cues.extend((rendered, text) for text in utterances(source["voiceover"]))
    if previous_end != timeline["duration_ms"] or len(cues) != len(expected_cues):
        raise ValueError("incomplete render timeline")
    previous_end, previous_scene = 0, None
    for cue, (scene, expected_text) in zip(cues, expected_cues):
        _exact(cue, {"scene_id", "start_ms", "end_ms", "text"})
        if (cue["scene_id"] != scene["scene_id"] or cue["text"] != expected_text
                or any(type(cue[key]) is not int for key in ("start_ms", "end_ms"))
                or not scene["start_ms"] <= cue["start_ms"] < cue["end_ms"] <= scene["end_ms"]
                or cue["start_ms"] < previous_end):
            raise ValueError("caption differs from episode or scene timing")
        expected_start = scene["start_ms"] + 400 if previous_scene != scene["scene_id"] else previous_end + 150
        if cue["start_ms"] != expected_start:
            raise ValueError("caption utterance clock is inconsistent")
        previous_end, previous_scene = cue["end_ms"], scene["scene_id"]
    if files["captions.vtt"] != captions_vtt(cues):
        raise ValueError("VTT differs from measured caption timeline")
    try:
        with wave.open(io.BytesIO(files["narration.wav"]), "rb") as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()) != (1, 2, SAMPLE_RATE, "NONE"):
                raise ValueError("unexpected narration format")
            frames = audio.getnframes()
            if (frames * 1000 != timeline["duration_ms"] * SAMPLE_RATE
                    or len(audio.readframes(frames)) != frames * 2):
                raise ValueError("narration differs from timeline duration")
    except (wave.Error, EOFError):
        raise ValueError("invalid narration audio") from None


def _embed_tag(template, tag, marker, content_type, data):
    pattern = r"<" + tag + r"\b[^>]*\b" + re.escape(marker) + r"(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'))?[^>]*>"
    matches = list(re.finditer(pattern, template, flags=re.IGNORECASE))
    if len(matches) != 1:
        raise ValueError("RPG template must contain one " + marker + " hook")
    original = matches[0].group()
    if re.search(r"\ssrc\s*=", original, re.IGNORECASE):
        raise ValueError("RPG media hook must be empty before packaging")
    attribute = re.compile(re.escape(marker) + r'(?:\s*=\s*(?:"([^"]*)"|\'([^\']*)\'))?', re.IGNORECASE)
    hook = attribute.search(original)
    if hook is None or any(value for value in hook.groups() if value is not None):
        raise ValueError("RPG media hook must be empty before packaging")
    uri = "data:" + content_type + ";base64," + base64.b64encode(data).decode("ascii")
    # The trusted page accepts these data attributes and sets native src, poster
    # and empty-player state together. It owns visibility and caption controls.
    replacement = attribute.sub(lambda match: marker + '="' + uri + '"', original)
    return template[:matches[0].start()] + replacement + template[matches[0].end():]


def build_companion(episode, art, files, template):
    """Embed supplied assets into the trusted repository RPG page, without fetches."""
    validate_render_bundle(episode, art, files)
    if type(template) is not str or not 0 < len(template.encode("utf-8")) < 2 * 1024 * 1024:
        raise ValueError("invalid RPG template")
    pattern = r'(<script type="application/json" id="episode-data">)[\s\S]*?(</script>)'
    if len(re.findall(pattern, template)) != 1:
        raise ValueError("RPG template requires exactly one episode payload")
    safe_json = canonical(episode).decode("utf-8").replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    template = re.sub(pattern, lambda match: match[1] + safe_json + match[2], template)
    for tag, marker, content_type, data in (
        ("img", "data-jarvis-inline-art", "image/png", art),
        ("video", "data-jarvis-inline-video", "video/mp4", files["episode.mp4"]),
        ("track", "data-jarvis-inline-captions", "text/vtt", files["captions.vtt"]),
    ):
        template = _embed_tag(template, tag, marker, content_type, data)
    return _bounded_bytes(template.encode("utf-8"))


def bundle_episode(episode, art, files, template):
    """Package a fixed inventory; no filesystem traversal or external retrieval."""
    validate_render_bundle(episode, art, files)
    companion = build_companion(episode, art, files, template)
    output = io.BytesIO()
    inventory = {**files, "episode.json": _json(episode), "art.png": art, "watch-and-play.html": companion}
    inventory["READ-ME.txt"] = (edition_label(episode) + "\n\nOpen watch-and-play.html in a browser, or play episode.mp4.\n"
        "The video includes burned-in captions; captions.vtt is also supplied.\n"
        "RPG choices and notes live only in this open page. Export progress before closing.\n"
        "Exploration is separate from real project completion.\n"
        "The artwork is a supplied still illustration. Camera movement is animated; characters are not lip-synced.\n"
        "Speech uses a generic local synthetic voice; music is a simple original oscillator score.\n"
        "This project pilot contains no current-news segment. No publication approval is granted.\n").encode("utf-8")
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in sorted(inventory.items()):
            archive.writestr(name, content)
    return _bounded_bytes(output.getvalue())
