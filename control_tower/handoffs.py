"""Durable local draft handoffs. No model calls, credentials, network or dispatch.

Local review labels and matching hashes are not identity authentication. Returned
packets remain unverified evidence for a person to review, never executable work.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from control_tower.network_contract import (canonical, digest, require_digest,
    require_identifier, validate_draft, validate_return)
from control_tower.swarm_factory import validate_swarm
from control_tower.handoff_context import validate_context

MAX_HANDOFFS = 1000
MAX_SWARMS = 100


def _now():
    return datetime.now(timezone.utc).isoformat()


class HandoffLedger:
    """Single local SQLite ledger; opaque IDs are never used as filenames."""

    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=2, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        try:
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            legacy_tables = {"swarms", "handoffs", "returns"}
            if (version not in (0, 1, 2) or (version == 0 and tables)
                or (version == 1 and tables != legacy_tables)
                or (version == 2 and tables != legacy_tables | {"handoff_contexts"})):
                raise ValueError("unsupported or unrelated ledger database")
            with self._transaction():
                self.db.execute("CREATE TABLE IF NOT EXISTS swarms (id TEXT PRIMARY KEY, digest TEXT NOT NULL, body TEXT NOT NULL)")
                self.db.execute("""CREATE TABLE IF NOT EXISTS handoffs (
                    id TEXT PRIMARY KEY, swarm_id TEXT NOT NULL REFERENCES swarms(id),
                    assistant_id TEXT NOT NULL, digest TEXT NOT NULL, body TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('pending_review','reviewed','export_prepared','returned_unverified')),
                    reviewer_id TEXT, reviewed_digest TEXT, created_at TEXT NOT NULL,
                    reviewed_at TEXT, exported_at TEXT)""")
                self.db.execute("""CREATE TABLE IF NOT EXISTS returns (
                    id TEXT PRIMARY KEY, handoff_id TEXT NOT NULL UNIQUE REFERENCES handoffs(id),
                    digest TEXT NOT NULL, body TEXT NOT NULL, received_at TEXT NOT NULL)""")
                self.db.execute("""CREATE TABLE IF NOT EXISTS handoff_contexts (
                    handoff_id TEXT PRIMARY KEY REFERENCES handoffs(id),
                    revision INTEGER NOT NULL, digest TEXT NOT NULL, body TEXT NOT NULL,
                    reviewer_id TEXT, reviewed_digest TEXT)""")
                self.db.execute("PRAGMA user_version=2")
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def _transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self.db.rollback()
            raise
        else:
            self.db.commit()

    def _handoff(self, handoff_id):
        require_identifier(handoff_id, "handoff ID")
        row = self.db.execute("SELECT * FROM handoffs WHERE id=?", (handoff_id,)).fetchone()
        if row is None:
            raise ValueError("unknown handoff")
        try:
            body = json.loads(row["body"])
        except (ValueError, TypeError, RecursionError):
            raise ValueError("stored handoff is invalid") from None
        keys = {"schema_version", "kind", "handoff_id", "assistant_id", "swarm_id", "manifest_sha256",
                "source_revision", "draft", "parent_id", "depth", "mode", "external_actions"}
        if not isinstance(body, dict) or set(body) != keys:
            raise ValueError("stored handoff structure mismatch")
        if digest(body) != row["digest"] or body["handoff_id"] != row["id"] or body["assistant_id"] != row["assistant_id"] or body["swarm_id"] != row["swarm_id"]:
            raise ValueError("stored handoff integrity mismatch")
        self._check_stored_return(row, body)
        return row, body

    def _check_stored_return(self, row, body):
        stored = self.db.execute("SELECT * FROM returns WHERE handoff_id=?", (row["id"],)).fetchone()
        if (stored is not None) != (row["state"] == "returned_unverified"):
            raise ValueError("stored return state mismatch")
        if stored is None:
            return
        try:
            packet = validate_return(json.loads(stored["body"]))
        except (ValueError, TypeError, RecursionError):
            raise ValueError("stored return is invalid") from None
        if (digest(packet) != stored["digest"] or packet["return_id"] != stored["id"]
            or packet["handoff_id"] != row["id"] or packet["handoff_sha256"] != row["digest"]
            or packet["source_provider"] != body["draft"]["target"]):
            raise ValueError("stored return integrity or binding mismatch")

    @staticmethod
    def _summary(row, *, duplicate=False):
        return {"handoff_id": row["id"], "handoff_sha256": row["digest"],
                "state": row["state"], "duplicate": duplicate,
                "external_actions": 0, "sender_authentication": "not_established"}

    def stage(self, draft, swarm, *, assistant_id, handoff_id, parent_id=None):
        draft = validate_draft(draft)
        swarm = validate_swarm(swarm)
        require_identifier(assistant_id, "assistant ID")
        require_identifier(handoff_id, "handoff ID")
        assistant = next((a for a in swarm["assistants"] if a["assistant_id"] == assistant_id), None)
        if assistant is None or draft["project_id"] != swarm["project_id"] or draft["target"] not in swarm["targets"]:
            raise ValueError("draft or assistant is outside the swarm scope")
        if parent_id is not None:
            require_identifier(parent_id, "parent ID")
        with self._transaction():
            depth = 0
            if parent_id is not None:
                parent, parent_body = self._handoff(parent_id)
                if parent["state"] != "returned_unverified" or parent_body["manifest_sha256"] != swarm["manifest_sha256"]:
                    raise ValueError("parent requires a returned packet in the same swarm")
                depth = parent_body["depth"] + 1
            if depth > swarm["max_depth"]:
                raise ValueError("handoff depth budget reached")
            body = {"schema_version": 1, "kind": "jarvis.handoff", "handoff_id": handoff_id,
                    "assistant_id": assistant_id, "swarm_id": swarm["swarm_id"],
                    "manifest_sha256": swarm["manifest_sha256"], "source_revision": swarm["source_revision"],
                    "draft": draft, "parent_id": parent_id, "depth": depth,
                    "mode": "manual_export_only", "external_actions": 0}
            body_digest = digest(body)
            existing = self.db.execute("SELECT id FROM handoffs WHERE id=?", (handoff_id,)).fetchone()
            if existing:
                old, _ = self._handoff(handoff_id)
                if old["digest"] != body_digest:
                    raise ValueError("handoff ID conflicts with existing content")
                return self._summary(old, duplicate=True)
            registered = self.db.execute("SELECT * FROM swarms WHERE id=?", (swarm["swarm_id"],)).fetchone()
            serialized_swarm = canonical(swarm).decode()
            if registered and (registered["digest"] != swarm["manifest_sha256"] or registered["body"] != serialized_swarm):
                raise ValueError("swarm ID conflicts with its registered specification")
            if not registered:
                if self.db.execute("SELECT count(*) FROM swarms").fetchone()[0] >= MAX_SWARMS:
                    raise ValueError("ledger swarm limit reached")
                self.db.execute("INSERT INTO swarms VALUES (?,?,?)", (swarm["swarm_id"], swarm["manifest_sha256"], serialized_swarm))
            if self.db.execute("SELECT count(*) FROM handoffs").fetchone()[0] >= MAX_HANDOFFS:
                raise ValueError("ledger handoff limit reached")
            consumed = self.db.execute("SELECT count(*) FROM handoffs WHERE swarm_id=? AND assistant_id=?", (swarm["swarm_id"], assistant_id)).fetchone()[0]
            if consumed >= assistant["max_handoffs"]:
                raise ValueError("durable assistant handoff budget reached")
            self.db.execute("INSERT INTO handoffs (id,swarm_id,assistant_id,digest,body,state,created_at) VALUES (?,?,?,?,?,'pending_review',?)",
                            (handoff_id, swarm["swarm_id"], assistant_id, body_digest, canonical(body).decode(), _now()))
            row, _ = self._handoff(handoff_id)
            return self._summary(row)

    def review(self, handoff_id, *, reviewer_id, expected_sha256):
        require_identifier(reviewer_id, "reviewer label")
        require_digest(expected_sha256)
        with self._transaction():
            row, _ = self._handoff(handoff_id)
            if row["digest"] != expected_sha256:
                raise ValueError("review digest does not match the draft")
            if reviewer_id == row["assistant_id"]:
                raise ValueError("reviewer label must differ from the drafting assistant")
            if row["state"] != "pending_review":
                if row["reviewer_id"] == reviewer_id and row["reviewed_digest"] == expected_sha256:
                    return self._summary(row, duplicate=True)
                raise ValueError("handoff already has a different review record")
            self.db.execute("UPDATE handoffs SET state='reviewed',reviewer_id=?,reviewed_digest=?,reviewed_at=? WHERE id=?",
                            (reviewer_id, expected_sha256, _now(), handoff_id))
            row, _ = self._handoff(handoff_id)
            return self._summary(row)

    def export(self, handoff_id, *, expected_sha256):
        require_digest(expected_sha256)
        with self._transaction():
            row, body = self._handoff(handoff_id)
            self._require_export_active(handoff_id)
            if row["digest"] != expected_sha256 or row["reviewed_digest"] != expected_sha256 or row["state"] == "pending_review":
                raise ValueError("export requires local review of this exact draft")
            if row["state"] == "reviewed":
                self.db.execute("UPDATE handoffs SET state='export_prepared',exported_at=? WHERE id=?", (_now(), handoff_id))
            return {"schema_version": 1, "mode": "manual_handoff", "handoff": body,
                    "handoff_sha256": expected_sha256,
                    "review": {"reviewer_label": row["reviewer_id"], "reviewed_sha256": row["reviewed_digest"],
                               "authority": "local_record_only_not_identity_authentication"},
                    "external_actions": 0}

    def import_return(self, packet):
        packet = validate_return(packet)
        packet_digest = digest(packet)
        with self._transaction():
            row, body = self._handoff(packet["handoff_id"])
            if row["state"] not in {"export_prepared", "returned_unverified"}:
                raise ValueError("return requires a previously exported handoff")
            if packet["handoff_sha256"] != row["digest"] or packet["source_provider"] != body["draft"]["target"]:
                raise ValueError("return does not match its intended handoff and target")
            existing = self.db.execute("SELECT * FROM returns WHERE id=? OR handoff_id=?", (packet["return_id"], packet["handoff_id"])).fetchone()
            duplicate = existing is not None
            if existing:
                if existing["id"] != packet["return_id"] or existing["handoff_id"] != packet["handoff_id"] or existing["digest"] != packet_digest or existing["body"] != canonical(packet).decode():
                    raise ValueError("return conflicts with previously accepted content")
            else:
                self.db.execute("INSERT INTO returns VALUES (?,?,?,?,?)", (packet["return_id"], packet["handoff_id"], packet_digest, canonical(packet).decode(), _now()))
                self.db.execute("UPDATE handoffs SET state='returned_unverified' WHERE id=?", (packet["handoff_id"],))
            return {"return_id": packet["return_id"], "handoff_id": packet["handoff_id"],
                    "return_sha256": packet_digest, "state": "returned_unverified", "duplicate": duplicate,
                    "sender_authentication": "not_established", "external_actions": 0}

    def status(self):
        """Return metadata only; draft and imported text remain in the local ledger."""
        rows = self.db.execute("SELECT id FROM handoffs ORDER BY created_at,id").fetchall()
        return {"mode": "local_ledger", "handoffs": [self._summary(self._handoff(r["id"])[0]) for r in rows],
                "swarm_count": self.db.execute("SELECT count(*) FROM swarms").fetchone()[0],
                "return_count": self.db.execute("SELECT count(*) FROM returns").fetchone()[0],
                "model_calls": 0, "external_actions": 0}

    def _context(self, handoff_id):
        _, handoff = self._handoff(handoff_id)
        row = self.db.execute("SELECT * FROM handoff_contexts WHERE handoff_id=?", (handoff_id,)).fetchone()
        if row is None:
            raise ValueError("handoff has no context")
        try:
            profile = validate_context(json.loads(row["body"]), handoff)
        except (ValueError, TypeError, RecursionError):
            raise ValueError("stored context is invalid") from None
        if digest(profile) != row["digest"] or type(row["revision"]) is not int or row["revision"] < 1:
            raise ValueError("stored context integrity mismatch")
        return row, profile

    def _require_export_active(self, handoff_id):
        # A corrupt stored context must fail closed, including on the legacy path.
        if self.db.execute("SELECT 1 FROM handoff_contexts WHERE handoff_id=?", (handoff_id,)).fetchone():
            _, profile = self._context(handoff_id)
            if profile["schema_version"] == 2 and profile["control"]["state"] != "active":
                raise ValueError("handoff export is paused or cancelled")

    def save_context(self, profile, *, expected_revision):
        """CAS write of proposed context; never alters the version-1 handoff.

        Callers authenticate outside this local ledger. No action is dispatched.
        Every changed profile clears its separate local review record.
        """
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("invalid expected context revision")
        if not isinstance(profile, dict):
            raise ValueError("context must be a record")
        with self._transaction():
            _, handoff = self._handoff(profile.get("handoff_id"))
            profile = validate_context(profile, handoff)
            existing = self.db.execute("SELECT * FROM handoff_contexts WHERE handoff_id=?",
                                       (profile["handoff_id"],)).fetchone()
            revision = existing["revision"] if existing else 0
            if revision != expected_revision:
                raise ValueError("context revision mismatch")
            checksum = digest(profile)
            if existing:
                _, old = self._context(profile["handoff_id"])
                if old["schema_version"] == 2:
                    if profile["schema_version"] != 2:
                        raise ValueError("controlled context cannot downgrade to version 1")
                    if old["control"]["state"] == "cancelled" and profile["control"]["state"] != "cancelled":
                        raise ValueError("cancelled handoff cannot resume")
                if (profile["mission_id"] != old["mission_id"]
                    or profile["memory_revision"] < old["memory_revision"]
                    or profile["execution"]["attempts"] < old["execution"]["attempts"]):
                    raise ValueError("mission identity or recovery history cannot regress")
                if checksum == existing["digest"]:
                    return {"revision": revision, "context_sha256": checksum, "duplicate": True}
            self.db.execute("""INSERT INTO handoff_contexts VALUES (?,?,?,?,NULL,NULL)
                ON CONFLICT(handoff_id) DO UPDATE SET revision=excluded.revision,
                digest=excluded.digest,body=excluded.body,reviewer_id=NULL,reviewed_digest=NULL""",
                (profile["handoff_id"], revision + 1, checksum, canonical(profile).decode()))
            return {"revision": revision + 1, "context_sha256": checksum, "duplicate": False}

    def load_context(self, handoff_id, *, expected_source_revision, expected_memory_revision,
                     audience="owner_private"):
        """Selective local retrieval, not an authenticated provider endpoint."""
        if audience not in ("owner_private", "public_candidate"):
            raise ValueError("unknown context audience")
        if type(expected_memory_revision) is not int:
            raise ValueError("invalid expected memory revision")
        with self._transaction():
            row, profile = self._context(handoff_id)
            if (profile["source_revision"] != expected_source_revision
                or profile["memory_revision"] != expected_memory_revision):
                raise ValueError("source or memory revision mismatch")
            if audience == "public_candidate" and profile["visibility"] != "public_candidate":
                raise ValueError("private context cannot enter a public bundle")
            return {"revision": row["revision"], "context_sha256": row["digest"],
                    "profile": profile, "review_state": "locally_reviewed" if row["reviewed_digest"] == row["digest"] else "proposed",
                    "sender_authentication": "not_established", "external_actions": 0}

    def review_context(self, handoff_id, *, reviewer_id, expected_sha256):
        require_identifier(reviewer_id, "reviewer label")
        require_digest(expected_sha256)
        with self._transaction():
            row, profile = self._context(handoff_id)
            if row["digest"] != expected_sha256 or reviewer_id == profile["asset_id"]:
                raise ValueError("context review requires exact content and a distinct label")
            self.db.execute("UPDATE handoff_contexts SET reviewer_id=?,reviewed_digest=? WHERE handoff_id=?",
                            (reviewer_id, expected_sha256, handoff_id))

    def export_context(self, handoff_id, *, expected_sha256, expected_source_revision,
                       expected_memory_revision, audience="owner_private"):
        """Export a compatible envelope only after both exact local reviews.

        This does not authenticate a reviewer, authorize release or send a packet.
        Blocked/unknown execution is retained unchanged, never retried here.
        """
        require_digest(expected_sha256)
        if audience not in ("owner_private", "public_candidate") or type(expected_memory_revision) is not int:
            raise ValueError("invalid export audience or memory revision")
        with self._transaction():
            row, profile = self._context(handoff_id)
            self._require_export_active(handoff_id)
            original, handoff = self._handoff(handoff_id)
            if (row["digest"] != expected_sha256 or row["reviewed_digest"] != expected_sha256
                or original["reviewed_digest"] != original["digest"]
                or original["state"] == "pending_review"):
                raise ValueError("envelope requires exact handoff and context reviews")
            if (profile["source_revision"] != expected_source_revision
                or profile["memory_revision"] != expected_memory_revision):
                raise ValueError("source or memory revision mismatch")
            # V1 drafts have no visibility metadata. Never declassify their text.
            if audience != "owner_private":
                raise ValueError("public envelope export requires a separate reviewed draft policy")
            if original["state"] == "reviewed":
                self.db.execute("UPDATE handoffs SET state='export_prepared',exported_at=? WHERE id=?", (_now(), handoff_id))
            return {"schema_version": 1, "kind": "jarvis.context_envelope", "handoff": handoff,
                    "handoff_sha256": original["digest"], "context": profile,
                    "context_revision": row["revision"], "context_sha256": row["digest"],
                    "review": {"reviewer_label": row["reviewer_id"],
                               "authority": "local_record_only_not_identity_authentication"},
                    "external_actions": 0}
