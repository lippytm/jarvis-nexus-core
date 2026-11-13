"""Compile an anime/RPG diary episode or render a local watch-and-play ZIP."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from control_tower.episode import build_episode
from control_tower.episode_render import bundle_episode, inspect_art, render_episode
from control_tower.network_contract import canonical, load_packet
from scripts.jarvis_diary import _write_bytes
from scripts.jarvis_portfolio import _local, _resolve


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("compile", "render"):
        command = commands.add_parser(name)
        command.add_argument("--entry-file", required=True)
        command.add_argument("--source-revision", required=True)
        command.add_argument("--episode", required=True)
        command.add_argument("--audience", choices=("public", "owner"), default="public")
        command.add_argument("--out", required=True)
        if name == "render":
            command.add_argument("--art-file", required=True)
    args = parser.parse_args(argv)
    try:
        root = _resolve(Path(args.root), strict=True)
        if not root.is_dir():
            raise ValueError("root must be an existing directory")
        output = _local(root, args.out)
        if output.exists():
            raise ValueError("output already exists; choose a fresh filename")
        if output.suffix != (".json" if args.command == "compile" else ".zip"):
            raise ValueError("unexpected output file extension")
        entry = load_packet(_local(root, args.entry_file))
        episode = build_episode(entry, source_revision=args.source_revision, episode_id=args.episode, audience=args.audience)
        if args.command == "compile":
            content = canonical(episode) + b"\n"
        else:
            art_path = _local(root, args.art_file)
            if not art_path.is_file() or not 0 < art_path.stat().st_size <= 20 * 1024 * 1024:
                raise ValueError("art file is missing or exceeds bounds")
            art = art_path.read_bytes()
            inspect_art(art)
            files = render_episode(episode, art)
            # This is the code-owned template; a caller cannot supply active HTML.
            template = (ROOT / "web" / "jarvis-rpg.html").read_text(encoding="utf-8")
            content = bundle_episode(episode, art, files, template)
        _write_bytes(output, content)
        print(json.dumps({"saved": str(output.relative_to(root)), "sha256": sha256(content).hexdigest(),
            "episode_sha256": episode["episode_sha256"], "audience": episode["audience"],
            "source_visibility": episode["source_visibility"], "rendered": args.command == "render",
            "external_actions": 0, "model_calls": 0}))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc) if type(exc) is ValueError else type(exc).__name__, "external_actions": 0}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
