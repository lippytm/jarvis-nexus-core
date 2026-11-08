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
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from control_tower.handoffs import HandoffLedger
from control_tower.connections import verify_github_commit_response, validate_destination_registry, inspect_destination_registry
from control_tower.network_contract import MAX_PACKET_BYTES, PROJECTS, TARGETS, canonical, load_packet, digest, require_digest, require_identifier, require_text, _unique_object
from control_tower.validation import json_record_errors
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


def _check_review_files(root, content, *, expected_file_sha256, source_revision, memory_revision,
                        expected_identity=None, verify_git_head=False):
    """Verify selected local file bytes in a pinned prepared receipt, not review."""
    if not isinstance(content, bytes) or len(content) > MAX_PACKET_BYTES:
        raise ValueError("review receipt must be bounded bytes")
    require_digest(expected_file_sha256)
    if hashlib.sha256(content).hexdigest() != expected_file_sha256:
        raise ValueError("review receipt file digest mismatch")
    if not isinstance(source_revision, str) or len(source_revision) != 40 or any(c not in "0123456789abcdef" for c in source_revision):
        raise ValueError("review source requires an exact commit SHA")
    if type(memory_revision) is not int or memory_revision < 1:
        raise ValueError("invalid review memory revision")
    identity_keys = {"project_id", "mission_id", "asset_id", "platform"}
    if expected_identity is not None and (not isinstance(expected_identity, dict)
        or set(expected_identity) != identity_keys
        or any(not isinstance(value, str) or not value for value in expected_identity.values())):
        raise ValueError("complete expected review identity is required")
    try:
        receipt = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError("invalid review receipt JSON") from None
    if json_record_errors(receipt) or not isinstance(receipt, dict):
        raise ValueError("invalid review receipt record")
    manifest = receipt.get("checks", {}).get("source_manifest") if isinstance(receipt.get("checks"), dict) else None
    if (type(receipt.get("schema_version")) is not int or receipt["schema_version"] != 1
        or receipt.get("record_type") != "actual_work_receipt" or receipt.get("visibility") != "owner_private"
        or not isinstance(manifest, dict) or receipt.get("input_revision") != source_revision
        or manifest.get("source_revision") != source_revision
        or type(receipt.get("memory_revision")) is not int or receipt["memory_revision"] != memory_revision
        or type(manifest.get("memory_revision")) is not int or manifest["memory_revision"] != memory_revision):
        raise ValueError("review receipt source, memory or profile mismatch")
    if (not isinstance(receipt.get("project_id"), str) or receipt["project_id"] not in PROJECTS
        or not isinstance(receipt.get("platform"), str) or receipt["platform"] not in TARGETS):
        raise ValueError("invalid review project or platform")
    for key in ("mission_id", "asset_id"):
        require_identifier(receipt.get(key), "review " + key)
    if expected_identity is not None and any(receipt[key] != expected_identity[key] for key in identity_keys):
        raise ValueError("review identity mismatch")
    if type(verify_git_head) is not bool:
        raise ValueError("Git HEAD guard must be boolean")
    if verify_git_head:
        # Local observation only: no checkout, hooks, network, or Git environment overrides.
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        try:
            observed = subprocess.run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                "-C", str(root), "rev-parse", "--show-toplevel", "--verify", "HEAD^{commit}"],
                capture_output=True, text=True, timeout=2, env=environment, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError("Git HEAD verification unavailable") from None
        lines = observed.stdout.splitlines()
        if (observed.returncode != 0 or len(lines) != 2
            or Path(lines[0]).resolve() != root or lines[1] != source_revision):
            raise ValueError("Git HEAD or repository root mismatch")
    sources = manifest.get("source_sha256")
    if not isinstance(sources, dict) or not 1 <= len(sources) <= 32:
        raise ValueError("review manifest requires one to 32 source files")
    paths, seen = [], set()
    for name, checksum in sources.items():
        if not isinstance(name, str) or ".." in Path(name).parts:
            raise ValueError("invalid review source path")
        path = _local(root, name)
        require_digest(checksum)
        if path in seen:
            raise ValueError("duplicate resolved review source")
        seen.add(path)
        paths.append((path, checksum))
    deadline = time.monotonic() + 10
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    for path, expected in paths:
        size, checksum = 0, hashlib.sha256()
        with os.fdopen(os.open(path, flags), "rb") as handle:
            metadata = os.fstat(handle.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 4 * 1024 * 1024:
                raise ValueError("review source must be a regular file of at most 4 MiB")
            while True:
                if time.monotonic() > deadline:
                    raise ValueError("review file time budget exceeded")
                block = handle.read(65536)
                if time.monotonic() > deadline:
                    raise ValueError("review file time budget exceeded")
                size += len(block)
                if size > 4 * 1024 * 1024:
                    raise ValueError("review source exceeds 4 MiB")
                if not block:
                    break
                checksum.update(block)
        if checksum.hexdigest() != expected:
            raise ValueError("review source file digest mismatch")
    return dict(schema_version=2 if verify_git_head else 1, kind="jarvis.review_files_check", project_id=receipt["project_id"],
        mission_id=receipt["mission_id"], asset_id=receipt["asset_id"], platform=receipt["platform"],
        source_revision=source_revision, memory_revision=memory_revision, receipt_file_sha256=expected_file_sha256,
        source_manifest_sha256=digest(manifest), files_checked=len(paths), visibility="owner_private",
        verification="selected_file_bytes_only", repository_revision_verification="local_git_head_only" if verify_git_head else "not_performed",
        independent_review="not_established", release_authorized=False, dispatch_authorized=False, external_actions=0)


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
                         expected_sha256, expected_source_revision, expected_memory_revision,
                         expected_revision=None):
    """Narrow local pause/cancel edit through existing context CAS, not authority."""
    require_digest(expected_sha256)
    require_identifier(actor_id, "local controller label")
    require_text(reason)
    if state not in {"paused", "cancelled"}:
        raise ValueError("control command permits only pause or cancel")
    selected = ledger.load_context(handoff_id, expected_source_revision=expected_source_revision,
        expected_memory_revision=expected_memory_revision, audience="owner_private",
        expected_revision=expected_revision)
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


def _check_backup_digest(path, expected_sha256):
    """Compare bounded file bytes only; never open SQLite or authorize restore."""
    require_digest(expected_sha256)
    limit = 128 * 1024 * 1024
    deadline = time.monotonic() + 10
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    checksum, size = hashlib.sha256(), 0
    with os.fdopen(os.open(path, flags), "rb") as handle:
        metadata = os.fstat(handle.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("backup digest input must be a regular file")
        if metadata.st_size > limit:
            raise ValueError("backup digest input exceeds 128 MiB")
        while True:
            if time.monotonic() > deadline:
                raise ValueError("backup digest time budget exceeded")
            block = handle.read(65536)
            if time.monotonic() > deadline:
                raise ValueError("backup digest time budget exceeded")
            if not block:
                break
            size += len(block)
            if size > limit:
                raise ValueError("backup digest input exceeds 128 MiB")
            checksum.update(block)
    actual = checksum.hexdigest()
    if actual != expected_sha256:
        raise ValueError("backup file digest mismatch")
    return {"schema_version": 1, "kind": "jarvis.backup_digest_check",
            "backup_sha256": actual, "bytes": size, "visibility": "owner_private",
            "verification": "file_bytes_only", "ledger_validation": "not_performed",
            "sender_authentication": "not_established", "restore_authorized": False,
            "retry_authorized": False, "external_actions": 0}


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
    context_load.add_argument("--digest", help="Require the exact current context content digest")
    context_load.add_argument("--context-revision", type=int, help="Require the exact stored context revision")
    context_load.add_argument("--out", required=True)
    control = commands.add_parser("set-context-control", help="Pause/cancel existing controlled context with exact guards")
    control.add_argument("--handoff", required=True)
    control.add_argument("--state", choices=("paused", "cancelled"), required=True)
    control.add_argument("--actor", required=True, help="Local label, not authenticated identity")
    control.add_argument("--reason", required=True)
    control.add_argument("--digest", required=True)
    control.add_argument("--source-revision", required=True)
    control.add_argument("--memory-revision", type=int, required=True)
    control.add_argument("--context-revision", type=int, help="Require the exact selected stored context revision")
    checkpoint_capture = commands.add_parser("capture-checkpoint", help="Retain exact current context; opt in to storage version 3")
    checkpoint_capture.add_argument("--handoff", required=True)
    checkpoint_capture.add_argument("--digest", required=True)
    checkpoint_capture.add_argument("--source-revision", required=True)
    checkpoint_capture.add_argument("--memory-revision", type=int, required=True)
    checkpoint_capture.add_argument("--context-revision", type=int, help="Require the exact current stored context revision")
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
    checkpoint_index.add_argument("--out", help="Save the private index without overwriting an existing file")
    checkpoint_index.add_argument("--include-digest", action="store_true", help="Emit a version-2 history snapshot digest")
    checkpoint_index.add_argument("--expected-report-digest", help="Refuse a changed checkpoint index before output")
    context_review = commands.add_parser("review-context")
    context_review.add_argument("--handoff", required=True)
    context_review.add_argument("--reviewer", required=True)
    context_review.add_argument("--digest", required=True)
    context_review.add_argument("--context-revision", type=int, help="Require the exact stored context revision")
    context_review.add_argument("--include-receipt", action="store_true", help="Return a versioned private review receipt; requires --context-revision")
    context_review.add_argument("--out", help="Save the private receipt to a fresh file; requires --include-receipt and --context-revision")
    receipt_check = commands.add_parser("check-review-receipt", help="Check saved local receipt against current binding without ledger writes")
    receipt_check.add_argument("--handoff", required=True)
    receipt_check.add_argument("--file", required=True)
    receipt_check.add_argument("--receipt-digest", help="Require this exact saved receipt SHA-256 before opening the ledger")
    receipt_check.add_argument("--out", help="Save private check metadata to a fresh file")
    context_export = commands.add_parser("export-context")
    context_export.add_argument("--handoff", required=True)
    context_export.add_argument("--digest", required=True)
    context_export.add_argument("--source-revision", required=True)
    context_export.add_argument("--memory-revision", type=int, required=True)
    context_export.add_argument("--context-revision", type=int, help="Require the exact stored context revision before preparing export")
    context_export.add_argument("--out", required=True)
    recovery = commands.add_parser("inspect-recovery")
    recovery.add_argument("--handoff", required=True)
    recovery.add_argument("--digest", required=True, help="Exact selected context SHA-256")
    recovery.add_argument("--source-revision", required=True)
    recovery.add_argument("--memory-revision", type=int, required=True)
    recovery.add_argument("--context-revision", type=int, help="Require the exact stored context revision")
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
    backup_check = commands.add_parser("check-backup-digest", help="Compare retained file bytes with an independently saved SHA-256; no SQLite open")
    backup_check.add_argument("--file", required=True)
    backup_check.add_argument("--digest", required=True)
    backup_check.add_argument("--out", help="Save private check metadata to a fresh file")
    commands.add_parser("status")
    review_files = commands.add_parser("check-review-files", help="Verify selected local bytes in a pinned prepared review receipt; no evaluation")
    review_files.add_argument("--verify-git-head", action="store_true", help="Require local Git root and HEAD to match the pinned source; version-2 report")
    review_files.add_argument("--file", required=True)
    review_files.add_argument("--file-digest", required=True, help="Exact receipt file-byte SHA-256, including whitespace; not its body checksum")
    review_files.add_argument("--source-revision", required=True)
    review_files.add_argument("--memory-revision", type=int, required=True)
    review_files.add_argument("--project", help="Expected project; supply with --mission, --asset and --platform")
    review_files.add_argument("--mission", help="Expected mission; all four identity guards are required together")
    review_files.add_argument("--asset", help="Expected asset label; does not authenticate the asset")
    review_files.add_argument("--platform", help="Expected portable target; does not establish a connection")
    review_files.add_argument("--out")
    queue = commands.add_parser("queue-report")
    queue.add_argument("--project", choices=sorted(PROJECTS), required=True)
    queue.add_argument("--mission", help="Select one mission's recorded metadata (version-2 report)")
    queue.add_argument("--platform", help="Select one portable target in a version-4 report; may combine with --mission")
    queue.add_argument("--include-review-state", action="store_true", help="Include local exact-review status (version-3 report)")
    queue.add_argument("--expected-report-digest", help="Refuse a changed queue snapshot before saving output")
    queue.add_argument("--out", help="Save private report to a fresh file instead of printing its contents")
    destination_status = commands.add_parser("destination-status")
    destination_status.add_argument("--project", choices=sorted(PROJECTS), required=True)
    destination_status.add_argument("--platform", choices=sorted(TARGETS), required=True)
    destination_status.add_argument("--destination", required=True)
    destination_status.add_argument("--mission", help="Select one mission at this destination (version-3 report)")
    destination_status.add_argument("--include-digest", action="store_true", help="Include a version-2 destination snapshot digest")
    destination_status.add_argument("--include-review-state", action="store_true", help="Include both local exact-review flags (version-4 report)")
    destination_status.add_argument("--expected-report-digest", help="Refuse a changed destination snapshot before saving output")
    destination_status.add_argument("--out", help="Save private report to a fresh file instead of printing its contents")
    registry_inspect = commands.add_parser("inspect-registry", help="Private proposed registry summary without opening a ledger")
    registry_inspect.add_argument("--file", required=True)
    registry_inspect.add_argument("--digest", required=True)
    registry_inspect.add_argument("--registry-revision", type=int, required=True)
    registry_inspect.add_argument("--source-revision", required=True)
    registry_inspect.add_argument("--project", help="Select one known source project in a version-2 summary")
    registry_inspect.add_argument("--platform", help="Select one portable target in a version-3 summary; may combine with --project")
    registry_inspect.add_argument("--destination", help="Select one destination in a version-4 summary; requires --project and --platform")
    registry_inspect.add_argument("--expected-receipt-digest", help="Require the exact selected inspection receipt before output")
    registry_inspect.add_argument("--out", help="Save private summary to a fresh file instead of stdout")
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
    observation.add_argument("--context-revision", type=int, help="Require the exact selected stored context revision")
    observation.add_argument("--out", required=True)
    demo = commands.add_parser("demo")
    demo.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.read_only and args.command not in {"status", "load-context", "inspect-recovery",
            "check-recovery", "prepare-reconciliation", "destination-status", "bind-observation", "backup-ledger", "check-backup-digest", "check-review-files", "queue-report", "load-checkpoint", "list-checkpoints", "inspect-registry", "check-review-receipt"}:
            raise ValueError("read-only mode permits inspection and backup commands only")
        root = Path(args.root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("root must be an existing directory")
        output = _local(root, args.out) if getattr(args, "out", None) is not None else None
        if output and output.exists():
            raise ValueError("output already exists; use a fresh filename")
        if args.command == "review-context" and output and (not args.include_receipt or args.context_revision is None):
            raise ValueError("saved review receipt requires --include-receipt and --context-revision")
        if args.command == "factory":
            result = build_swarm(args.project, args.targets.split(","), swarm_id=args.swarm,
                                 source_revision=args.source_revision)
        elif args.command == "catalog":
            result = {"projects": PROJECTS, "providers": provider_catalog(), "external_actions": 0}
        elif args.command == "check-review-files":
            identity = dict(project_id=args.project, mission_id=args.mission, asset_id=args.asset, platform=args.platform)
            result = _check_review_files(root, _response_bytes(_local(root, args.file)),
                expected_file_sha256=args.file_digest, source_revision=args.source_revision,
                memory_revision=args.memory_revision,
                expected_identity=identity if any(value is not None for value in identity.values()) else None,
                verify_git_head=args.verify_git_head)
        elif args.command == "inspect-registry":
            result = inspect_destination_registry(load_packet(_local(root, args.file)),
                expected_sha256=args.digest, expected_revision=args.registry_revision,
                expected_source_revision=args.source_revision, project_id=args.project, platform=args.platform,
                expected_receipt_sha256=args.expected_receipt_digest, destination_id=args.destination)
        elif args.command == "demo":
            result = demonstrate_network()
        elif args.command == "init-ledger":
            result = _initialize_ledger(_local(root, args.database))
        elif args.command == "check-backup-digest":
            result = _check_backup_digest(_local(root, args.file), args.digest)
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
            review_receipt = load_packet(_local(root, args.file)) if args.command == "check-review-receipt" else None
            if args.command == "check-review-receipt" and args.receipt_digest is not None:
                require_digest(args.receipt_digest)
                if review_receipt.get("receipt_sha256") != args.receipt_digest:
                    raise ValueError("saved review receipt does not match expected digest")
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
            with HandoffLedger(database, read_only=args.read_only or registry is not None or args.command in {"load-checkpoint", "list-checkpoints", "check-review-receipt"}) as ledger:
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
                        expected_source_revision=args.source_revision, expected_memory_revision=args.memory_revision,
                        expected_revision=args.context_revision)
                elif args.command == "load-context":
                    result = ledger.load_context(args.handoff, expected_source_revision=args.source_revision,
                                                 expected_memory_revision=args.memory_revision,
                                                 audience="owner_private", expected_sha256=args.digest,
                                                 expected_revision=args.context_revision)
                elif args.command == "capture-checkpoint":
                    result = ledger.checkpoint_context(args.handoff, expected_sha256=args.digest,
                        expected_source_revision=args.source_revision, expected_memory_revision=args.memory_revision,
                        expected_revision=args.context_revision)
                elif args.command == "list-checkpoints":
                    result = ledger.list_checkpoints(args.handoff, include_digest=args.include_digest,
                        expected_sha256=args.expected_report_digest)
                elif args.command == "load-checkpoint":
                    result = ledger.load_checkpoint(args.handoff, args.checkpoint_revision, expected_sha256=args.digest,
                        expected_source_revision=args.source_revision, expected_memory_revision=args.memory_revision)
                elif args.command == "check-review-receipt":
                    result = ledger.check_context_review_receipt(args.handoff, review_receipt)
                elif args.command == "review-context":
                    receipt = ledger.review_context(args.handoff, reviewer_id=args.reviewer, expected_sha256=args.digest,
                                          expected_revision=args.context_revision, include_receipt=args.include_receipt)
                    result = receipt if args.include_receipt else {"handoff_id": args.handoff, "context_sha256": args.digest,
                              "review_state": "locally_reviewed", "external_actions": 0,
                              "authority": "local_record_only_not_identity_authentication"}
                elif args.command == "export-context":
                    result = ledger.export_context(args.handoff, expected_sha256=args.digest,
                                                   expected_source_revision=args.source_revision,
                                                   expected_memory_revision=args.memory_revision,
                                                   audience="owner_private", expected_revision=args.context_revision)
                elif args.command == "inspect-recovery":
                    result = ledger.inspect_recovery(args.handoff, expected_sha256=args.digest,
                        expected_source_revision=args.source_revision, expected_memory_revision=args.memory_revision,
                        expected_revision=args.context_revision)
                elif args.command == "check-recovery":
                    result = ledger.check_recovery(args.handoff, expected_inspection_sha256=args.inspection_digest,
                        expected_sha256=args.digest, expected_source_revision=args.source_revision,
                        expected_memory_revision=args.memory_revision)
                elif args.command == "prepare-reconciliation":
                    result = ledger.prepare_reconciliation(args.handoff, expected_inspection_sha256=args.inspection_digest,
                        expected_sha256=args.digest, expected_source_revision=args.source_revision,
                        expected_memory_revision=args.memory_revision)
                elif args.command == "queue-report":
                    result = ledger.queue_report(project_id=args.project, mission_id=args.mission,
                        expected_sha256=args.expected_report_digest, include_review_state=args.include_review_state,
                        platform=args.platform)
                elif args.command == "destination-status":
                    result = ledger.destination_status(project_id=args.project, platform=args.platform,
                        destination_id=args.destination, include_digest=args.include_digest,
                        expected_sha256=args.expected_report_digest, mission_id=args.mission,
                        include_review_state=args.include_review_state)
                elif args.command == "bind-observation":
                    guards = dict(expected_sha256=args.digest, expected_source_revision=args.source_revision,
                                  expected_memory_revision=args.memory_revision, expected_revision=args.context_revision)
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
