"""Private local SQLite diary storage with bounded, immutable revision records.

This is unencrypted storage for a trusted local OS user. Hashes detect accidental
changes; they do not authenticate an author or defend against that user's code.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from control_tower.diary import _date, _identifier, validate_diary_entry
from control_tower.network_contract import MAX_PACKET_BYTES, canonical, digest


DEFAULT_DIARY_PATH = "reports/diary/diary.sqlite3"
MAX_STORED_ENTRIES = 1000
MAX_REVISIONS_PER_ENTRY = 256
_APPLICATION_ID = 1245991507
_SCHEMA = {
    "diary_revisions": """CREATE TABLE diary_revisions (
        entry_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision >= 1),
        sha256 TEXT NOT NULL, body TEXT NOT NULL, diary_date TEXT NOT NULL,
        visibility TEXT NOT NULL, saved_at TEXT NOT NULL, previous_sha256 TEXT,
        PRIMARY KEY(entry_id, revision))""",
    "diary_entries": """CREATE TABLE diary_entries (
        entry_id TEXT PRIMARY KEY NOT NULL,
        current_revision INTEGER NOT NULL CHECK(current_revision >= 1),
        FOREIGN KEY(entry_id, current_revision)
        REFERENCES diary_revisions(entry_id, revision))""",
    "diary_revisions_no_update": """CREATE TRIGGER diary_revisions_no_update
        BEFORE UPDATE ON diary_revisions BEGIN
        SELECT RAISE(ABORT, 'diary revisions are immutable'); END""",
    "diary_revisions_no_delete": """CREATE TRIGGER diary_revisions_no_delete
        BEFORE DELETE ON diary_revisions BEGIN
        SELECT RAISE(ABORT, 'diary revisions are immutable'); END""",
}


def _sha256(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("invalid diary content hash")


def _private_regular(info):
    return (stat.S_ISREG(info.st_mode) and info.st_nlink == 1
            and info.st_uid == os.getuid() and not info.st_mode & 0o077)


def _open_private_path(value):
    """Walk parents without symlinks and reserve a private regular database file.

    SQLite itself opens a filename. Retained descriptors and identity checks
    detect ordinary replacement, not malicious concurrent changes by the owner.
    """
    parent_fd = file_fd = None
    try:
        raw = os.fspath(value)
        if (type(raw) is not str or not raw or raw == ":memory:" or "\x00" in raw
                or raw.startswith("file:") or not hasattr(os, "O_NOFOLLOW")):
            raise ValueError("invalid diary database path")
        path = Path(os.path.abspath(raw))
        if not path.name:
            raise ValueError("invalid diary database path")
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        parent_fd = os.open(path.anchor, directory_flags)
        for part in path.parent.parts[1:]:
            try:
                child_fd = os.open(part, directory_flags, dir_fd=parent_fd)
            except FileNotFoundError:
                os.mkdir(part, mode=0o700, dir_fd=parent_fd)
                child_fd = os.open(part, directory_flags, dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = child_fd
        parent_info = os.fstat(parent_fd)
        if parent_info.st_uid != os.getuid() or parent_info.st_mode & 0o022:
            raise ValueError("unsafe diary database directory")
        flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
        try:
            file_fd = os.open(path.name, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent_fd)
        except FileExistsError:
            file_fd = os.open(path.name, flags, dir_fd=parent_fd)
        if not _private_regular(os.fstat(file_fd)):
            raise ValueError("unsafe diary database file")
        return path, parent_fd, file_fd
    except (OSError, TypeError, ValueError):
        if file_fd is not None:
            os.close(file_fd)
        if parent_fd is not None:
            os.close(parent_fd)
        raise ValueError("unsafe or unavailable diary database path") from None


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate stored diary key")
        result[key] = value
    return result


def _nonfinite(_value):
    raise ValueError("invalid stored diary number")


class DiaryStore:
    """Bounded local store. Entry identifiers are never used as file paths."""

    def __init__(self, path=DEFAULT_DIARY_PATH):
        self.db = None
        self._parent_fd = self._file_fd = None
        self._closed = False
        try:
            self.path, self._parent_fd, self._file_fd = _open_private_path(path)
            self._guard_path()
            self.db = sqlite3.connect(str(self.path), timeout=2, isolation_level=None)
            # Bound SQLite's row/TEXT materialization before querying a damaged
            # database; the remaining 4 KiB covers fixed revision metadata.
            self.db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_PACKET_BYTES + 4096)
            self.db.row_factory = sqlite3.Row
            self._guard_path()
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.execute("PRAGMA trusted_schema=OFF")
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            application = self.db.execute("PRAGMA application_id").fetchone()[0]
            objects = {row["name"]: " ".join(row["sql"].split()) for row in self.db.execute(
                "SELECT name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
            if version == 0 and application == 0 and not objects:
                with self._transaction():
                    for statement in _SCHEMA.values():
                        self.db.execute(statement)
                    self.db.execute(f"PRAGMA application_id={_APPLICATION_ID}")
                    self.db.execute("PRAGMA user_version=1")
            elif (version != 1 or application != _APPLICATION_ID
                  or objects != {key: " ".join(value.split()) for key, value in _SCHEMA.items()}):
                raise ValueError("unsupported or unrelated diary database")
            if self.db.execute("PRAGMA journal_mode=DELETE").fetchone()[0] != "delete":
                raise ValueError("unsupported diary journal mode")
            self.db.execute("PRAGMA synchronous=FULL")
        except (OSError, sqlite3.Error, TypeError, ValueError):
            self.close()
            raise ValueError("cannot open a safe diary store") from None

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None
        for attribute in ("_file_fd", "_parent_fd"):
            descriptor = getattr(self, attribute, None)
            if descriptor is not None:
                os.close(descriptor)
                setattr(self, attribute, None)
        self._closed = True

    def __enter__(self):
        if self._closed:
            raise ValueError("diary store is closed")
        return self

    def __exit__(self, *_):
        self.close()

    def _guard_path(self):
        if self._closed:
            raise ValueError("diary store is closed")
        try:
            parent = os.stat(self.path.parent, follow_symlinks=False)
            held_parent = os.fstat(self._parent_fd)
            visible = os.stat(self.path, follow_symlinks=False)
            held_file = os.fstat(self._file_fd)
            if (not stat.S_ISDIR(parent.st_mode) or parent.st_mode & 0o022
                    or parent.st_uid != os.getuid()
                    or (parent.st_dev, parent.st_ino) != (held_parent.st_dev, held_parent.st_ino)
                    or not _private_regular(visible)
                    or (visible.st_dev, visible.st_ino) != (held_file.st_dev, held_file.st_ino)):
                raise ValueError("unsafe diary store path")
            for suffix in ("-journal", "-wal", "-shm"):
                try:
                    sidecar = os.stat(self.path.name + suffix, dir_fd=self._parent_fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if not _private_regular(sidecar):
                    raise ValueError("unsafe diary store sidecar")
        except (OSError, TypeError, ValueError):
            raise ValueError("unsafe or unavailable diary store path") from None

    @contextmanager
    def _operation(self):
        self._guard_path()
        try:
            yield
        except sqlite3.Error:
            raise ValueError("diary store operation failed") from None

    @contextmanager
    def _transaction(self, *, write=True):
        self._guard_path()
        self.db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield
            self.db.commit()
        except BaseException:
            if self.db.in_transaction:
                self.db.rollback()
            raise

    @staticmethod
    def _decode_row(row):
        try:
            if type(row["body"]) is not str or len(row["body"].encode("utf-8")) > MAX_PACKET_BYTES:
                raise ValueError("invalid stored body")
            entry = validate_diary_entry(json.loads(row["body"], object_pairs_hook=_pairs,
                                                   parse_constant=_nonfinite))
            _sha256(row["sha256"])
            saved_at = datetime.fromisoformat(row["saved_at"])
            if (saved_at.tzinfo != timezone.utc or saved_at.isoformat() != row["saved_at"]
                    or digest(entry) != row["sha256"] or canonical(entry).decode("utf-8") != row["body"]
                    or entry["entry_id"] != row["entry_id"] or entry["date"] != row["diary_date"]
                    or entry["visibility"] != row["visibility"]):
                raise ValueError("stored binding mismatch")
            return entry
        except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
            raise ValueError("stored diary integrity check failed") from None

    def _chain(self, entry_id):
        head = self.db.execute("SELECT current_revision FROM diary_entries WHERE entry_id=?", (entry_id,)).fetchone()
        rows = self.db.execute("SELECT * FROM diary_revisions WHERE entry_id=? ORDER BY revision LIMIT ?",
                               (entry_id, MAX_REVISIONS_PER_ENTRY + 1)).fetchall()
        if head is None:
            if rows:
                raise ValueError("stored diary integrity check failed")
            return None, []
        if (not rows or len(rows) > MAX_REVISIONS_PER_ENTRY
                or type(head["current_revision"]) is not int or head["current_revision"] != len(rows)):
            raise ValueError("stored diary integrity check failed")
        previous, entry = None, None
        for index, row in enumerate(rows, 1):
            if type(row["revision"]) is not int or row["revision"] != index or row["previous_sha256"] != previous:
                raise ValueError("stored diary integrity check failed")
            entry = self._decode_row(row)
            previous = row["sha256"]
        return entry, rows

    def _all_current(self):
        identifiers = self.db.execute("SELECT entry_id FROM diary_entries ORDER BY entry_id LIMIT ?",
                                      (MAX_STORED_ENTRIES + 1,)).fetchall()
        if len(identifiers) > MAX_STORED_ENTRIES or self.db.execute(
                "SELECT 1 FROM diary_revisions r LEFT JOIN diary_entries e ON e.entry_id=r.entry_id "
                "WHERE e.entry_id IS NULL LIMIT 1").fetchone():
            raise ValueError("stored diary integrity check failed")
        result = []
        for row in identifiers:
            try:
                _identifier(row["entry_id"])
            except ValueError:
                raise ValueError("stored diary integrity check failed") from None
            entry, revisions = self._chain(row["entry_id"])
            result.append((entry, revisions[-1]))
        return result

    @staticmethod
    def _metadata(row):
        return {"entry_id": row["entry_id"], "revision": row["revision"], "sha256": row["sha256"],
                "date": row["diary_date"], "visibility": row["visibility"], "saved_at": row["saved_at"],
                "previous_sha256": row["previous_sha256"]}

    def save(self, entry, expected_sha256=None):
        """Append a revision only after an exact-current-hash update check.

        An identical retry is idempotent even with a stale but well-formed hash.
        An expected hash cannot be supplied when creating a previously absent ID.
        """
        entry = validate_diary_entry(entry)
        if expected_sha256 is not None:
            _sha256(expected_sha256)
        serialized, entry_hash = canonical(entry).decode("utf-8"), digest(entry)
        with self._operation(), self._transaction():
            current, revisions = self._chain(entry["entry_id"])
            if current is not None and revisions[-1]["body"] == serialized:
                return {"entry_id": entry["entry_id"], "revision": len(revisions),
                        "sha256": entry_hash, "status": "unchanged"}
            current_hash = revisions[-1]["sha256"] if revisions else None
            if ((current is None and expected_sha256 is not None)
                    or (current is not None and expected_sha256 != current_hash)):
                raise ValueError("diary update requires the current content hash")
            if len(revisions) >= MAX_REVISIONS_PER_ENTRY:
                raise ValueError("diary revision limit reached")
            if current is None and self.db.execute("SELECT count(*) FROM diary_entries").fetchone()[0] >= MAX_STORED_ENTRIES:
                raise ValueError("diary entry limit reached")
            revision = len(revisions) + 1
            self.db.execute("INSERT INTO diary_revisions VALUES (?,?,?,?,?,?,?,?)",
                            (entry["entry_id"], revision, entry_hash, serialized, entry["date"],
                             entry["visibility"], datetime.now(timezone.utc).isoformat(), current_hash))
            if current is None:
                self.db.execute("INSERT INTO diary_entries VALUES (?,?)", (entry["entry_id"], revision))
            else:
                self.db.execute("UPDATE diary_entries SET current_revision=? WHERE entry_id=?",
                                (revision, entry["entry_id"]))
            return {"entry_id": entry["entry_id"], "revision": revision, "sha256": entry_hash,
                    "status": "created" if current is None else "updated"}

    def get(self, entry_id):
        _identifier(entry_id)
        with self._operation(), self._transaction(write=False):
            entry, _ = self._chain(entry_id)
            return entry

    def entries_for_date(self, date):
        _date(date)
        with self._operation(), self._transaction(write=False):
            return [entry for entry, _ in self._all_current() if entry["date"] == date]

    def history(self, entry_id):
        """Return revision metadata; historical free text stays in the database."""
        _identifier(entry_id)
        with self._operation(), self._transaction(write=False):
            _, revisions = self._chain(entry_id)
            return [self._metadata(row) for row in revisions]

    def list_metadata(self):
        """Owner-local listing: IDs and dates are metadata, not public-safe data."""
        with self._operation(), self._transaction(write=False):
            return [self._metadata(row) for _, row in self._all_current()]
