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
import stat
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from control_tower.handoffs import HandoffLedger
from control_tower.connections import verify_github_commit_response, validate_destination_registry
from control_tower.network_contract import MAX_PACKET_BYTES, PROJECTS, TARGETS, canonical, load_packet, digest, require_digest, require_identifier, require_text
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


def _response_bytes(path):
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags), "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("response input must be a regular file")
        content = handle.read(MAX_PACKET_BYTES + 1)
    if len(content) > MAX_PACKET_BYTES:
        raise ValueError("response input exceeds 64 KiB")
    return content


def _write(path, record, *, packet_output=False):
    content = canonical(record) + b"\n"
    if packet_output and len(content) > MAX_PACKET_BYTES:
        raise ValueError("output exceeds packet limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent,
                                         prefix=".jarvis-write-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        # A hard link publishes the complete same-filesystem file atomically and
        # fails if the final name already exists. It never replaces old evidence.
        os.link(temporary, path)
        if os.name == "posix":
            # Flush publication before acknowledging success. A failure here
            # leaves a complete output to reconcile, never an overwrite retry.
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _set_context_control(ledger, *, handoff_id, state, actor_id, reason,
                         expected_sha256, expected_source_revision, expected_memory_revision):
    """Narrow local pause/cancel edit through existing context CAS, not authority."""
    require_digest(expected_sha256)
    require_identifier(actor_id, "local controller label")
    require_text(reason)
    if state not in {"paused", "cancelled"}:
        raise ValueError("control command permits only pause or cancel")
    selected = ledger.load_context(handoff_id, expected_source_revision=expected_source_revision,
        expected_memory_revision=expected_memory_revision, audience="owner_private")
    if selected["context_sha256"] != expected_sha256:
        raise ValueError("context digest mismatch")
    profile = selected["profile"]
    if profile["schema_version"] < 2:
        raise ValueError("control command requires an explicitly saved version-2 or version-3 profile")
    if profile["visibility"] != "owner_private":
        raise ValueError("control command requires owner-private context")
    control = {"state": state, "actor_id": actor_id, "reason": reason}
    if profile["control"] != control:
        profile["control"] = control
        profile["memory_revision"] += 1
    result = ledger.save_context(profile, expected_revision=selected["revision"])
    return {**result, "handoff_id": handoff_id, "control_state": state,
            "memory_revision": profile["memory_revision"],
            "execution_state": profile["execution"]["state"], "visibility": "owner_private",
            "authority": "local_record_only_not_identity_authentication",
            "retry_authorized": False, "dispatch_authorized": False, "external_actions": 0}


def _check_backup_scopes(ledger):
    """Check saved Fabric scopes and bounded Hermes dependency chains."""
    for row in ledger.db.execute("SELECT id FROM swarms"):
        ledger._swarm(row["id"])
    for row in ledger.db.execute("SELECT id FROM handoffs"):
        ledger._lineage(row["id"])


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
            version = destination.execute("PRAGMA user_version").fetchone()[0]
            if version not in (2, 3):
                raise ValueError("backup requires a version-2 or version-3 ledger; retain legacy backups before migration")
            if destination.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("backup SQLite integrity check failed")
            if destination.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ValueError("backup foreign key check failed")
        with HandoffLedger(temporary) as checked:
            _check_backup_scopes(checked)
            status = checked.status()  # Validates stored handoff and return bindings.
            contexts = checked.db.execute("SELECT handoff_id FROM handoff_contexts").fetchall()
            for row in contexts:
                checked._context(row["handoff_id"])
            if version == 3:
                for row in checked.db.execute("SELECT handoff_id,revision FROM context_checkpoints").fetchall():
                    checked._checkpoint(row["handoff_id"], row["revision"])
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
        return {"backup_sha256": checksum.hexdigest(), "bytes": size, "schema_version": version,
                "handoff_count": len(status["handoffs"]), "context_count": len(contexts),
                "return_count": status["return_count"], "visibility": "owner_private",
                "external_actions": 0}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _initialize_ledger(path):
    """Explicit empty-ledger bootstrap; checked atomic publication never replaces."""
    if path.exists():
        raise ValueError("ledger already exists; initialization refuses overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=path.parent, prefix=".jarvis-init-") as directory:
        with HandoffLedger(Path(directory) / "empty.sqlite3") as ledger:
            receipt = _backup(ledger.db, path)
    return {"mode": "initialized_empty_ledger", "schema_version": receipt["schema_version"],
            "ledger_sha256": receipt["backup_sha256"], "visibility": "owner_private",
            "external_actions": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--database", default="reports/jarvis-network.sqlite3")
    parser.add_argument("--read-only", action="store_true", help="Inspect an existing version-2/3 ledger without database writes")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-ledger")
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
    control = commands.add_parser("set-context-control", help="Pause/cancel existing controlled context with exact guards")
    control.add_argument("--handoff", required=True)
    control.add_argument("--state", choices=("paused", "cancelled"), required=True)
    control.add_argument("--actor", required=True, help="Local label, not authenticated identity")
    control.add_argument("--reason", required=True)
    control.add_argument("--digest", required=True)
    control.add_argument("--source-revision", required=True)
    control.add_argument("--memory-revision", type=int, required=True)
    checkpoint_capture = commands.add_parser("capture-checkpoint", help="Retain exact current context; opt in to storage version 3")
    checkpoint_capture.add_argument("--handoff", required=True)
    checkpoint_capture.add_argument("--digest", required=True)
    checkpoint_capture.add_argument("--source-revision", required=True)
    checkpoint_capture.add_argument("--memory-revision", type=int, required=True)
    checkpoint_capture.add_argument("--allow-schema-upgrade", action="store_true", required=True,
        help="Explicitly permit opt-in version-3 history storage; required on every capture")
    checkpoint_load = commands.add_parser("load-checkpoint", help="Read one private historical context without database writes")
    checkpoint_load.add_argument("--handoff", required=True)
    checkpoint_load.add_argument("--checkpoint-revision", type=int, required=True)
    checkpoint_load.add_argument("--digest", required=True)
    checkpoint_load.add_argument("--source-revision", required=True)
    checkpoint_load.add_argument("--memory-revision", type=int, required=True)
    checkpoint_load.add_argument("--out", required=True)
    checkpoint_index = commands.add_parser("list-checkpoints", help="Read one handoff's private history index without context text")
    checkpoint_index.add_argument("--handoff", required=True)
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
    reconciliation = commands.add_parser("prepare-reconciliation")
    reconciliation.add_argument("--handoff", required=True)
    reconciliation.add_argument("--inspection-digest", required=True)
    reconciliation.add_argument("--digest", required=True)
    reconciliation.add_argument("--source-revision", required=True)
    reconciliation.add_argument("--memory-revision", type=int, required=True)
    reconciliation.add_argument("--out", required=True)
    backup = commands.add_parser("backup-ledger")
    backup.add_argument("--out", required=True)
    commands.add_parser("status")
    queue = commands.add_parser("queue-report")
    queue.add_argument("--project", choices=sorted(PROJECTS), required=True)
    queue.add_argument("--out", help="Save private report to a fresh file instead of printing its contents")
    destination_status = commands.add_parser("destination-status")
    destination_status.add_argument("--project", choices=sorted(PROJECTS), required=True)
    destination_status.add_argument("--platform", choices=sorted(TARGETS), required=True)
    destination_status.add_argument("--destination", required=True)
    destination_status.add_argument("--out", help="Save private report to a fresh file instead of printing its contents")
    observation = commands.add_parser("bind-observation")
    observation.add_argument("--handoff", required=True)
    observation.add_argument("--file", required=True)
    observation.add_argument("--response-file", help="Optional retained raw response, at most 64 KiB; compare exact bytes with observation hash")
    observation.add_argument("--github-commit-repository", help="Optional owner/repo identity check for a Git-data commit response; requires --response-file")
    observation.add_argument("--registry-file", help="Private proposed destination configuration; requires response file, registry digest and revision")
    observation.add_argument("--registry-digest")
    observation.add_argument("--registry-revision", type=int)
    observation.add_argument("--digest", required=True)
    observation.add_argument("--source-revision", required=True)
    observation.add_argument("--memory-revision", type=int, required=True)
    observation.add_argument("--out", required=True)
    demo = commands.add_parser("demo")
    demo.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.read_only and args.command not in {"status", "load-context", "inspect-recovery",
            "check-recovery", "prepare-reconciliation", "destination-status", "bind-observation", "backup-ledger", "queue-report", "load-checkpoint", "list-checkpoints"}:
            raise ValueError("read-only mode permits inspection and backup commands only")
        root = Path(args.root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("root must be an existing directory")
        output = _local(root, args.out) if getattr(args, "out", None) is not None else None
        if output and output.exists():
            raise ValueError("output already exists; use a fresh filename")
        if args.command == "factory":
            result = build_swarm(args.project, args.targets.split(","), swarm_id=args.swarm,
                                 source_revision=args.source_revision)
        elif args.command == "catalog":
            result = {"projects": PROJECTS, "providers": provider_catalog(), "external_actions": 0}
        elif args.command == "demo":
            result = demonstrate_network()
        elif args.command == "init-ledger":
            result = _initialize_ledger(_local(root, args.database))
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
            observation_packet = load_packet(_local(root, args.file)) if args.command == "bind-observation" else None
            registry = None
            if args.command == "bind-observation" and any(value is not None for value in
                    (args.registry_file, args.registry_digest, args.registry_revision)):
                if (args.registry_file is None or args.registry_digest is None or args.registry_revision is None
                    or not args.response_file):
                    raise ValueError("registry check requires --registry-file, --registry-digest, --registry-revision and --response-file")
                if args.github_commit_repository is not None:
                    raise ValueError("registry mapping cannot be combined with a declared repository override")
                registry = validate_destination_registry(load_packet(_local(root, args.registry_file)))
                require_digest(args.registry_digest)
                if digest(registry) != args.registry_digest or registry["revision"] != args.registry_revision:
                    raise ValueError("registry digest or revision mismatch")
            if args.command == "bind-observation" and args.response_file:
                response = _response_bytes(_local(root, args.response_file))
                if hashlib.sha256(response).hexdigest() != observation_packet.get("response_sha256"):
                    raise ValueError("retained response digest does not match observation")
            if args.command == "bind-observation" and args.github_commit_repository is not None:
                if not args.response_file:
                    raise ValueError("GitHub commit identity check requires --response-file")
                verify_github_commit_response(response, observation_packet, args.github_commit_repository)
            database = _local(root, args.database)
            if args.command != "stage" and not database.is_file():
                raise ValueError("operation requires an existing ledger; use stage to create a new ledger")
            with HandoffLedger(database, read_only=args.read_only or registry is not None or args.command in {"load-checkpoint", "list-checkpoints"}) as ledger:
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
                elif args.command == "set-context-control":
                    result = _set_context_control(ledger, handoff_id=args.handoff, state=args.state,
                        actor_id=args.actor, reason=args.reason, expected_sha256=args.digest,
                        expected_source_revision=args.source_revision, expected_memory_revision=args.memory_revision)
                elif args.command == "load-context":
                    result = ledger.load_context(args.handoff, expected_source_revision=args.source_revision,
                                                 expected_memory_revision=args.memory_revision,
                                                 audience="owner_private")
                elif args.command == "capture-checkpoint":
                    result = ledger.checkpoint_context(args.handoff, expected_sha256=args.digest,
                        expected_source_revision=args.source_revision, expected_memory_revision=args.memory_revision)
                elif args.command == "list-checkpoints":
                    result = ledger.list_checkpoints(args.handoff)
                elif args.command == "load-checkpoint":
                    result = ledger.load_checkpoint(args.handoff, args.checkpoint_revision, expected_sha256=args.digest,
                        expected_source_revision=args.source_revision, expected_memory_revision=args.memory_revision)
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
                elif args.command == "prepare-reconciliation":
                    result = ledger.prepare_reconciliation(args.handoff, expected_inspection_sha256=args.inspection_digest,
                        expected_sha256=args.digest, expected_source_revision=args.source_revision,
                        expected_memory_revision=args.memory_revision)
                elif args.command == "queue-report":
                    result = ledger.queue_report(project_id=args.project)
                elif args.command == "destination-status":
                    result = ledger.destination_status(project_id=args.project, platform=args.platform,
                                                       destination_id=args.destination)
                elif args.command == "bind-observation":
                    guards = dict(expected_sha256=args.digest, expected_source_revision=args.source_revision,
                                  expected_memory_revision=args.memory_revision)
                    if registry is not None:
                        result = ledger.bind_configured_github_observation(args.handoff, observation_packet,
                            response, registry, expected_registry_sha256=args.registry_digest,
                            expected_registry_revision=args.registry_revision, **guards)
                    else:
                        result = ledger.bind_destination_observation(args.handoff, observation_packet, **guards)
                else:
                    result = ledger.status()
        if output:
            # Only factory emits an input packet. Reports and combined envelopes
            # may contain several independently bounded records; do not truncate.
            _write(output, result, packet_output=args.command == "factory")
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
