"""Optional local FFmpeg previews from compiler-owned text/audio, never shell code."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap

from control_tower.media import build_media_files

FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def _run(arguments, directory):
    # Both executable and argument structure are code-owned. Source text lives in
    # generated files; it is never interpolated into a filter or command string.
    try:
        result = subprocess.run(arguments, cwd=directory, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=45, check=False, shell=False)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("local media renderer unavailable or timed out") from None
    if result.returncode:
        raise ValueError("local media renderer failed; no preview committed")


def render_previews(entry, *, product_id, source_revision, duration_seconds=30, edition_timestamp=None):
    """Return actual MP4/WAV bytes and a receipt. Caller owns exclusive output."""
    files = build_media_files(entry, product_id=product_id, source_revision=source_revision,
                              duration_seconds=duration_seconds, edition_timestamp=edition_timestamp)
    executable = shutil.which("ffmpeg")
    if executable is None or not FONT.is_file():
        raise ValueError("local FFmpeg and the documented font are required")
    cues = json.loads(files["trailer_cues.json"])["cues"]
    with tempfile.TemporaryDirectory(prefix="jarvis-media-") as directory:
        folder = Path(directory)
        (folder / "music.wav").write_bytes(files["music_bed.wav"])
        (folder / "narration.txt").write_bytes(files["narration.txt"])
        filters = []
        for index, cue in enumerate(cues):
            # Keep a readable preview excerpt; complete source text remains in the
            # scripts/entry. Fixed safe filenames keep source text out of syntax.
            lines = []
            for line in cue["text"].splitlines():
                lines.extend(textwrap.wrap(line, width=48, break_long_words=True, break_on_hyphens=False))
            rendered = "\n".join(lines[:7])
            if len(lines) > 7:
                rendered += "\n[See full script]"
            name = f"scene-{index:02d}.txt"
            (folder / name).write_text(rendered, encoding="utf-8")
            start, end = cue["start_ms"] / 1000, cue["end_ms"] / 1000
            filters.append(f"drawtext=fontfile={FONT}:textfile={name}:expansion=none:fontcolor=0xeef2ff:fontsize=30:line_spacing=14:x=60:y=120:enable='gte(t,{start})*lt(t,{end})'")
        (folder / "label.txt").write_text("CONCEPT ANIMATIC  |  Text cards + original synthetic music", encoding="utf-8")
        filters.append(f"drawtext=fontfile={FONT}:textfile=label.txt:expansion=none:fontcolor=0xf6c578:fontsize=20:x=60:y=475")
        common = [executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-n"]
        _run(common + ["-f", "lavfi", "-i", f"color=c=0x111b30:s=960x540:r=24:d={duration_seconds}",
            "-protocol_whitelist", "file,pipe", "-i", "music.wav", "-vf", ",".join(filters), "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
            "-t", str(duration_seconds), "-movflags", "+faststart", "preview.mp4"], folder)
        # A generic built-in voice provides a rough local sample. No custom voice
        # model is loaded and no named person's voice is requested or cloned.
        _run(common + ["-f", "lavfi", "-i", "flite=textfile=narration.txt:voice=kal", "-c:a", "pcm_s16le", "narration.wav"], folder)
        output = {}
        for name, limit in (("preview.mp4", 25 * 1024 * 1024), ("narration.wav", 40 * 1024 * 1024)):
            path = folder / name
            if not path.is_file() or not 0 < path.stat().st_size <= limit:
                raise ValueError("local renderer output exceeds bounds")
            output[name] = path.read_bytes()
    receipt = {"schema_version": 1, "kind": "jarvis.media_render_receipt",
        "source_entry_sha256": json.loads(files["manifest.json"])["source_entry_sha256"],
        "source_context_revision": source_revision, "preview_kind": "text_card_concept_animatic",
        "expected_video_duration_seconds": duration_seconds, "narration_kind": "rough_generic_flite_kal_voice",
        "speech_alignment": "not_implemented; storyboard text cues are separate", "external_actions": 0, "model_calls": 0,
        "files": [{"path": name, "bytes": len(value), "sha256": sha256(value).hexdigest()} for name, value in sorted(output.items())]}
    output["render_receipt.json"] = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    return output
