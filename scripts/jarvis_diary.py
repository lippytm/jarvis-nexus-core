"""Validate/store diary entries, compile daily briefings and export local media packs."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from control_tower.diary import build_diary_briefing, diary_entry_digest, validate_diary_entry
from control_tower.diary_store import DiaryStore
from control_tower.media import build_media_files, bundle_media
from control_tower.network_contract import canonical, load_packet
from scripts.jarvis_portfolio import _local, _resolve


def _database_path(root, locator):
    # Keep the original components so DiaryStore can reject symlink files and
    # parents. Resolving first would erase that safety boundary.
    path = Path(locator)
    if (not locator or path.is_absolute() or not path.parts or ".." in path.parts
            or locator == ":memory:" or locator.startswith("file:")):
        raise ValueError("database path must be a relative workspace path without parent traversal")
    return root / path


def _write_bytes(path, content):
    if not isinstance(content, bytes) or len(content) > 50 * 1024 * 1024:
        raise ValueError("output exceeds local artifact bounds")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=".jarvis-diary-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--db", default="reports/diary/diary.sqlite3")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--entry-file", required=True)
    save = commands.add_parser("save")
    save.add_argument("--entry-file", required=True)
    save.add_argument("--expected-sha256")
    show = commands.add_parser("export-entry")
    show.add_argument("--entry-id", required=True)
    show.add_argument("--out", required=True)
    commands.add_parser("list")
    history = commands.add_parser("history")
    history.add_argument("--entry-id", required=True)
    brief = commands.add_parser("briefing")
    brief.add_argument("--date", required=True)
    brief.add_argument("--audience", choices=("public", "owner"), default="public")
    brief.add_argument("--entry-file")
    brief.add_argument("--out", required=True)
    pack = commands.add_parser("pack")
    pack.add_argument("--entry-file", required=True)
    pack.add_argument("--product", required=True)
    pack.add_argument("--source-revision", required=True)
    pack.add_argument("--target", default="chatgpt")
    pack.add_argument("--duration", type=int, default=30)
    pack.add_argument("--edition-timestamp")
    pack.add_argument("--render-preview", action="store_true")
    pack.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        root = _resolve(Path(args.root), strict=True)
        if not root.is_dir():
            raise ValueError("root must be an existing directory")
        output = _local(root, args.out) if hasattr(args, "out") else None
        if output is not None:
            if output.exists():
                raise ValueError("output already exists; choose a fresh filename")
            suffix = ".zip" if args.command == "pack" else ".json"
            if output.suffix != suffix:
                raise ValueError("unexpected output file extension")
        entry = None
        if getattr(args, "entry_file", None):
            entry = validate_diary_entry(load_packet(_local(root, args.entry_file)))
        if args.command == "validate":
            result = {"entry_id": entry["entry_id"], "sha256": diary_entry_digest(entry), "valid": True}
        elif args.command == "pack":
            parameters = {"product_id": args.product, "source_revision": args.source_revision, "duration_seconds": args.duration, "edition_timestamp": args.edition_timestamp}
            files = build_media_files(entry, target=args.target, **parameters)
            previews = None
            if args.render_preview:
                from control_tower.media_render import render_previews
                # Reuse the actual edition timestamp from the first compilation.
                parameters["edition_timestamp"] = json.loads(files["manifest.json"])["edition_timestamp"]
                previews = render_previews(entry, **parameters)
            content = bundle_media(files, previews=previews)
            _write_bytes(output, content)
            result = {"saved": str(output.relative_to(root)), "sha256": sha256(content).hexdigest(),
                      "files": len(files) + (len(previews) if previews else 0), "preview_rendered": previews is not None}
        elif args.command == "briefing" and entry is not None:
            record = build_diary_briefing([entry], diary_date=args.date, audience=args.audience)
            _write_bytes(output, canonical(record) + b"\n")
            result = {"saved": str(output.relative_to(root)), "entry_count": record["entry_count"], "audience": args.audience}
        else:
            with DiaryStore(_database_path(root, args.db)) as ledger:
                if args.command == "save":
                    result = ledger.save(entry, expected_sha256=args.expected_sha256)
                elif args.command == "list":
                    result = {"entries": ledger.list_metadata()}
                elif args.command == "history":
                    result = {"history": ledger.history(args.entry_id)}
                elif args.command == "export-entry":
                    record = ledger.get(args.entry_id)
                    if record is None:
                        raise ValueError("unknown diary entry")
                    _write_bytes(output, canonical(record) + b"\n")
                    result = {"saved": str(output.relative_to(root)), "sha256": diary_entry_digest(record)}
                else:
                    record = build_diary_briefing(ledger.entries_for_date(args.date), diary_date=args.date, audience=args.audience)
                    _write_bytes(output, canonical(record) + b"\n")
                    result = {"saved": str(output.relative_to(root)), "entry_count": record["entry_count"], "audience": args.audience}
        print(json.dumps({**result, "external_actions": 0, "model_calls": 0}))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc) if type(exc) is ValueError else type(exc).__name__, "external_actions": 0}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
