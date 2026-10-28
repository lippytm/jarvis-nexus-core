"""Build assistant specifications and exchange reviewed local draft packets.

Every file and database path must stay inside --root. No network call is made.
"""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from control_tower.handoffs import HandoffLedger
from control_tower.network_contract import PROJECTS, TARGETS, load_packet
from control_tower.network_demo import demonstrate_network
from control_tower.provider_catalog import provider_catalog
from control_tower.swarm_factory import build_swarm


def _local(root, value):
    if not value or Path(value).is_absolute():
        raise ValueError("file paths must be relative to the workspace root")
    path = (root / value).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("path leaves the workspace root")
    return path


def _write(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".jarvis-write-", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(record, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # A hard link publishes the complete same-filesystem file atomically and
        # fails if the final name already exists. It never replaces old evidence.
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _backup(connection, path):
    """Publish a checked SQLite online backup, never replace an existing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    deadline = time.monotonic() + 10
    def progress(*_):
        if time.monotonic() > deadline:
            raise ValueError("backup time budget exceeded")
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".jarvis-backup-", delete=False) as handle:
            temporary = Path(handle.name)
        with closing(sqlite3.connect(temporary)) as destination:
            connection.backup(destination, pages=128, progress=progress, sleep=0.01)
            if destination.execute("PRAGMA user_version").fetchone()[0] != 2:
                raise ValueError("backup requires a version-2 ledger; retain legacy backups before migration")
            if destination.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("backup SQLite integrity check failed")
            if destination.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ValueError("backup foreign key check failed")
        with HandoffLedger(temporary) as checked:
            status = checked.status()  # Validates stored handoff and return bindings.
            contexts = checked.db.execute("SELECT handoff_id FROM handoff_contexts").fetchall()
            for row in contexts:
                checked._context(row["handoff_id"])
        checksum = hashlib.sha256()
        with temporary.open("rb") as handle:
            for block in iter(lambda: handle.read(65536), b""):
                checksum.update(block)
            os.fsync(handle.fileno())
        size = temporary.stat().st_size
        os.link(temporary, path)  # Atomic no-clobber publication on the same filesystem.
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return {"backup_sha256": checksum.hexdigest(), "bytes": size, "schema_version": 2,
                "handoff_count": len(status["handoffs"]), "context_count": len(contexts),
                "return_count": status["return_count"], "visibility": "owner_private",
                "external_actions": 0}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--database", default="reports/jarvis-network.sqlite3")
    commands = parser.add_subparsers(dest="command", required=True)
    catalog = commands.add_parser("catalog")
    catalog.add_argument("--out", required=True)
    factory = commands.add_parser("factory")
    factory.add_argument("--project", choices=sorted(PROJECTS), required=True)
    factory.add_argument("--targets", required=True, help="Comma-separated provider IDs")
    factory.add_argument("--swarm", required=True)
    factory.add_argument("--source-revision", required=True)
    factory.add_argument("--out", required=True)
    stage = commands.add_parser("stage")
    stage.add_argument("--manifest", required=True)
    stage.add_argument("--draft", required=True)
    stage.add_argument("--assistant", required=True)
    stage.add_argument("--handoff", required=True)
    stage.add_argument("--parent")
    review = commands.add_parser("review")
    review.add_argument("--handoff", required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--digest", required=True)
    export = commands.add_parser("export")
    export.add_argument("--handoff", required=True)
    export.add_argument("--digest", required=True)
    export.add_argument("--out", required=True)
    returned = commands.add_parser("import-return")
    returned.add_argument("--file", required=True)
    context_save = commands.add_parser("save-context")
    context_save.add_argument("--file", required=True)
    context_save.add_argument("--expected-revision", type=int, required=True)
    context_load = commands.add_parser("load-context")
    context_load.add_argument("--handoff", required=True)
    context_load.add_argument("--source-revision", required=True)
    context_load.add_argument("--memory-revision", type=int, required=True)
    context_load.add_argument("--out", required=True)
    context_review = commands.add_parser("review-context")
    context_review.add_argument("--handoff", required=True)
    context_review.add_argument("--reviewer", required=True)
    context_review.add_argument("--digest", required=True)
    context_export = commands.add_parser("export-context")
    context_export.add_argument("--handoff", required=True)
    context_export.add_argument("--digest", required=True)
    context_export.add_argument("--source-revision", required=True)
    context_export.add_argument("--memory-revision", type=int, required=True)
    context_export.add_argument("--out", required=True)
    recovery = commands.add_parser("inspect-recovery")
    recovery.add_argument("--handoff", required=True)
    recovery.add_argument("--digest", required=True, help="Exact selected context SHA-256")
    recovery.add_argument("--source-revision", required=True)
    recovery.add_argument("--memory-revision", type=int, required=True)
    recovery.add_argument("--out", required=True)
    recovery_check = commands.add_parser("check-recovery")
    recovery_check.add_argument("--handoff", required=True)
    recovery_check.add_argument("--inspection-digest", required=True)
    recovery_check.add_argument("--digest", required=True, help="Exact selected context SHA-256")
    recovery_check.add_argument("--source-revision", required=True)
    recovery_check.add_argument("--memory-revision", type=int, required=True)
    backup = commands.add_parser("backup-ledger")
    backup.add_argument("--out", required=True)
    commands.add_parser("status")
    demo = commands.add_parser("demo")
    demo.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        root = Path(args.root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("root must be an existing directory")
        output = _local(root, args.out) if hasattr(args, "out") else None
        if output and output.exists():
            raise ValueError("output already exists; use a fresh filename")
        if args.command == "factory":
            result = build_swarm(args.project, args.targets.split(","), swarm_id=args.swarm,
                                 source_revision=args.source_revision)
        elif args.command == "catalog":
            result = {"projects": PROJECTS, "providers": provider_catalog(), "external_actions": 0}
        elif args.command == "demo":
            result = demonstrate_network()
        elif args.command == "backup-ledger":
            database = _local(root, args.database)
            if not database.is_file():
                raise ValueError("backup requires an existing ledger")
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=2)) as source:
                result = _backup(source, output)
            output = None  # SQLite output is already published; do not JSON-overwrite it.
            result["saved"] = args.out
        else:
            # Parse user-controlled packets before opening/mutating the ledger.
            draft = load_packet(_local(root, args.draft)) if args.command == "stage" else None
            manifest = load_packet(_local(root, args.manifest)) if args.command == "stage" else None
            returned_packet = load_packet(_local(root, args.file)) if args.command == "import-return" else None
            context_packet = load_packet(_local(root, args.file)) if args.command == "save-context" else None
            with HandoffLedger(_local(root, args.database)) as ledger:
                if args.command == "stage":
                    result = ledger.stage(draft, manifest, assistant_id=args.assistant,
                                          handoff_id=args.handoff, parent_id=args.parent)
                elif args.command == "review":
                    result = ledger.review(args.handoff, reviewer_id=args.reviewer, expected_sha256=args.digest)
                elif args.command == "export":
                    result = ledger.export(args.handoff, expected_sha256=args.digest)
                elif args.command == "import-return":
                    result = ledger.import_return(returned_packet)
                elif args.command == "save-context":
                    result = ledger.save_context(context_packet, expected_revision=args.expected_revision)
                elif args.command == "load-context":
                    result = ledger.load_context(args.handoff, expected_source_revision=args.source_revision,
                                                 expected_memory_revision=args.memory_revision,
                                                 audience="owner_private")
                elif args.command == "review-context":
                    ledger.review_context(args.handoff, reviewer_id=args.reviewer, expected_sha256=args.digest)
                    result = {"handoff_id": args.handoff, "context_sha256": args.digest,
                              "review_state": "locally_reviewed", "external_actions": 0,
                              "authority": "local_record_only_not_identity_authentication"}
                elif args.command == "export-context":
                    result = ledger.export_context(args.handoff, expected_sha256=args.digest,
                                                   expected_source_revision=args.source_revision,
                                                   expected_memory_revision=args.memory_revision,
                                                   audience="owner_private")
                elif args.command == "inspect-recovery":
                    result = ledger.inspect_recovery(args.handoff, expected_sha256=args.digest,
                        expected_source_revision=args.source_revision, expected_memory_revision=args.memory_revision)
                elif args.command == "check-recovery":
                    result = ledger.check_recovery(args.handoff, expected_inspection_sha256=args.inspection_digest,
                        expected_sha256=args.digest, expected_source_revision=args.source_revision,
                        expected_memory_revision=args.memory_revision)
                else:
                    result = ledger.status()
        if output:
            _write(output, result)
            print(json.dumps({"saved": str(output.relative_to(root)), "external_actions": 0}))
        else:
            print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        # Validation messages are fixed code strings; OS/SQLite detail may contain paths or data.
        message = str(exc) if type(exc) is ValueError else type(exc).__name__
        print(json.dumps({"error": message, "external_actions": 0}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
