"""Durable local draft handoffs. No model calls, credentials, network or dispatch.

Local review labels and matching hashes are not identity authentication. Returned
packets remain unverified evidence for a person to review, never executable work.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from control_tower.network_contract import (PROJECTS, TARGETS, canonical, digest, require_digest,
    require_identifier, validate_draft, validate_return)
from control_tower.swarm_factory import validate_swarm
from control_tower.handoff_context import validate_context
from control_tower.connections import connector_report

MAX_HANDOFFS = 1000
MAX_SWARMS = 100


def _now():
    return datetime.now(timezone.utc).isoformat()


class HandoffLedger:
    """Single local SQLite ledger; opaque IDs are never used as filenames."""

    def __init__(self, path, *, read_only=False):
        if type(read_only) is not bool:
            raise ValueError("read-only option must be boolean")
        self.read_only = read_only
        path = Path(path)
        if not read_only:
            path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro" if read_only else path,
                                 uri=read_only, timeout=2, isolation_level=None)
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
            if read_only:
                if version != 2:
                    raise ValueError("read-only inspection requires an existing version-2 ledger; migration is separate")
                return
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
        self.db.execute("BEGIN" if self.read_only else "BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self.db.rollback()
            raise
        else:
            self.db.commit()

    def _swarm(self, swarm_id):
        require_identifier(swarm_id, "swarm ID")
        row = self.db.execute("SELECT * FROM swarms WHERE id=?", (swarm_id,)).fetchone()
        if row is None:
            raise ValueError("unknown stored swarm")
        try:
            manifest = validate_swarm(json.loads(row["body"]))
        except (ValueError, TypeError, RecursionError):
            raise ValueError("stored swarm configuration is invalid") from None
        if row["id"] != manifest["swarm_id"] or row["digest"] != manifest["manifest_sha256"]:
            raise ValueError("stored swarm identity or digest mismatch")
        return manifest

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
        if (type(body["schema_version"]) is not int or body["schema_version"] != 1
            or body["kind"] != "jarvis.handoff" or body["mode"] != "manual_export_only"
            or type(body["external_actions"]) is not int or body["external_actions"] != 0):
            raise ValueError("stored handoff contract requires version 1, manual mode and zero external actions")
        if digest(body) != row["digest"] or body["handoff_id"] != row["id"] or body["assistant_id"] != row["assistant_id"] or body["swarm_id"] != row["swarm_id"]:
            raise ValueError("stored handoff integrity mismatch")
        manifest = self._swarm(body["swarm_id"])
        draft = validate_draft(body["draft"])
        if (body["manifest_sha256"] != manifest["manifest_sha256"]
            or body["source_revision"] != manifest["source_revision"]
            or body["assistant_id"] not in {a["assistant_id"] for a in manifest["assistants"]}
            or draft["project_id"] != manifest["project_id"] or draft["target"] not in manifest["targets"]):
            raise ValueError("stored handoff is outside its registered swarm scope")
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
                self._require_export_active(parent_id)
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
            if self.db.execute("SELECT 1 FROM handoff_contexts WHERE handoff_id=?", (handoff_id,)).fetchone():
                if self._context(handoff_id)[1]["schema_version"] == 3:
                    raise ValueError("destination-bound handoff requires context envelope export")
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
        with self._transaction():
            rows = self.db.execute("SELECT id FROM handoffs ORDER BY created_at,id").fetchall()
            return {"mode": "local_ledger", "handoffs": [self._summary(self._handoff(r["id"])[0]) for r in rows],
                    "swarm_count": self.db.execute("SELECT count(*) FROM swarms").fetchone()[0],
                    "return_count": self.db.execute("SELECT count(*) FROM returns").fetchone()[0],
                    "model_calls": 0, "external_actions": 0}

    def destination_status(self, *, project_id, platform, destination_id):
        """Selective private metadata discovery, never connection/dispatch proof."""
        if not isinstance(project_id, str) or project_id not in PROJECTS:
            raise ValueError("unknown project")
        if not isinstance(platform, str) or platform not in TARGETS:
            raise ValueError("unknown platform")
        require_identifier(destination_id, "destination ID")
        with self._transaction():
            matches = []
            rows = self.db.execute("SELECT handoff_id FROM handoff_contexts ORDER BY handoff_id").fetchall()
            for item in rows:
                row, profile = self._context(item["handoff_id"])
                if (profile["schema_version"] != 3 or profile["project_id"] != project_id
                    or profile["platform"] != platform or profile["destination_id"] != destination_id):
                    continue
                original, _ = self._handoff(item["handoff_id"])
                matches.append({"handoff_id": item["handoff_id"], "mission_id": profile["mission_id"],
                    "asset_id": profile["asset_id"], "source_revision": profile["source_revision"],
                    "memory_revision": profile["memory_revision"], "context_revision": row["revision"],
                    "context_sha256": row["digest"], "handoff_state": original["state"],
                    "execution_state": profile["execution"]["state"], "control_state": profile["control"]["state"],
                    "review_state": "locally_reviewed" if row["reviewed_digest"] == row["digest"] else "proposed"})
            return {"schema_version": 1, "kind": "jarvis.destination_status", "project_id": project_id,
                    "platform": platform, "destination_id": destination_id, "records": matches,
                    "visibility": "owner_private", "sender_authentication": "not_established",
                    "dispatch_authorized": False, "external_actions": 0}

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

    def _lineage(self, handoff_id):
        # Factory contracts permit depth at most two: self plus two ancestors.
        # Validate every ancestor even when the leaf has no context of its own.
        current, seen, records = handoff_id, set(), []
        while current is not None:
            require_identifier(current, "ancestor handoff ID")
            if current in seen or len(seen) >= 3:
                raise ValueError("invalid or excessive handoff ancestry")
            seen.add(current)
            row, body = self._handoff(current)
            records.append((row, body))
            current = body["parent_id"]
        return records

    def _require_export_active(self, handoff_id):
        for row, body in self._lineage(handoff_id):
            current = row["id"]
            if self.db.execute("SELECT 1 FROM handoff_contexts WHERE handoff_id=?", (current,)).fetchone():
                context, profile = self._context(current)
                if profile["execution"]["state"] == "outcome_unknown":
                    raise ValueError("unknown outcome requires reconciliation before export")
                if profile["schema_version"] >= 2:
                    if profile["control"]["state"] != "active":
                        raise ValueError("handoff export is paused or cancelled")
                    if context["reviewed_digest"] != context["digest"]:
                        raise ValueError("controlled export requires fresh context review")

    def inspect_recovery(self, handoff_id, *, expected_sha256, expected_source_revision,
                         expected_memory_revision):
        """Private metadata snapshot for reconciliation; never releases or retries.

        The expected digest binds the selected context. Ancestor context/return
        bindings are captured together in the same SQLite transaction. Free text,
        reference URLs and provider-return contents are deliberately omitted.
        """
        require_digest(expected_sha256)
        if type(expected_memory_revision) is not int:
            raise ValueError("invalid expected memory revision")
        with self._transaction():
            selected, profile = self._context(handoff_id)
            if (selected["digest"] != expected_sha256
                or profile["source_revision"] != expected_source_revision
                or profile["memory_revision"] != expected_memory_revision):
                raise ValueError("recovery inspection context or revision mismatch")
            lineage = []
            for row, body in self._lineage(handoff_id):
                item = {"handoff_id": row["id"], "handoff_sha256": row["digest"],
                        "parent_id": body["parent_id"], "source_revision": body["source_revision"],
                        "project_id": body["draft"]["project_id"], "asset_id": body["assistant_id"],
                        "platform": body["draft"]["target"], "handoff_state": row["state"],
                        "handoff_review_current": row["reviewed_digest"] == row["digest"],
                        "context": None, "returned_evidence": None, "holds": []}
                if self.db.execute("SELECT 1 FROM handoff_contexts WHERE handoff_id=?", (row["id"],)).fetchone():
                    context, saved = self._context(row["id"])
                    execution = saved["execution"]
                    control = saved["control"]["state"] if saved["schema_version"] >= 2 else "legacy_uncontrolled"
                    reviewed = context["reviewed_digest"] == context["digest"]
                    item["context"] = {"schema_version": saved["schema_version"],
                        "revision": context["revision"], "context_sha256": context["digest"],
                        "mission_id": saved["mission_id"], "memory_revision": saved["memory_revision"],
                        "configuration_version": saved["configuration_version"],
                        "visibility": saved["visibility"], "review_current": reviewed,
                        "execution_state": execution["state"], "context_id": execution["context_id"],
                        "attempts": execution["attempts"],
                        "checkpoint_present": execution["checkpoint_ref"] is not None,
                        "control_state": control}
                    if execution["state"] == "outcome_unknown":
                        item["holds"].append("outcome_unknown")
                    if control in ("paused", "cancelled"):
                        item["holds"].append(control)
                    if saved["schema_version"] >= 2 and not reviewed:
                        item["holds"].append("context_review_required")
                returned = self.db.execute("SELECT id,digest FROM returns WHERE handoff_id=?", (row["id"],)).fetchone()
                if returned:
                    item["returned_evidence"] = {"return_id": returned["id"], "return_sha256": returned["digest"],
                                                  "state": "returned_unverified"}
                lineage.append(item)
            result = {"schema_version": 1, "kind": "jarvis.recovery_inspection",
                      "handoff_id": handoff_id, "visibility": "owner_private", "lineage": lineage,
                      "mode": "inspection_only", "retry_authorized": False,
                      "sender_authentication": "not_established", "external_actions": 0}
            return {**result, "inspection_sha256": digest(result)}

    def check_recovery(self, handoff_id, *, expected_inspection_sha256, expected_sha256,
                       expected_source_revision, expected_memory_revision):
        """Check a previously inspected snapshot, without authorizing any action.

        Valid only at the observation point, not a lease or a future release gate.
        Ancestor changes and late returns invalidate the complete snapshot even
        when the selected context digest and memory revision remain unchanged.
        """
        require_digest(expected_inspection_sha256)
        current = self.inspect_recovery(handoff_id, expected_sha256=expected_sha256,
            expected_source_revision=expected_source_revision, expected_memory_revision=expected_memory_revision)
        if current["inspection_sha256"] != expected_inspection_sha256:
            raise ValueError("recovery inspection is stale; inspect current evidence again")
        return {"handoff_id": handoff_id, "inspection_sha256": expected_inspection_sha256,
                "state": "current_local_observation_only", "visibility": "owner_private",
                "retry_authorized": False, "sender_authentication": "not_established", "external_actions": 0}

    def prepare_reconciliation(self, handoff_id, *, expected_inspection_sha256, expected_sha256,
                               expected_source_revision, expected_memory_revision):
        """Prepare private review evidence, never resolve or release an outcome.

        Read selected context first, then bind it to a fresh exact snapshot.
        No state-changing decision follows this observation; a future authenticated
        resolution write must recheck its expected snapshot atomically.
        """
        require_digest(expected_inspection_sha256)
        loaded = self.load_context(handoff_id, expected_source_revision=expected_source_revision,
                                   expected_memory_revision=expected_memory_revision)
        profile = loaded["profile"]
        inspection = self.inspect_recovery(handoff_id, expected_sha256=expected_sha256,
            expected_source_revision=expected_source_revision, expected_memory_revision=expected_memory_revision)
        if (loaded["context_sha256"] != expected_sha256
            or inspection["inspection_sha256"] != expected_inspection_sha256):
            raise ValueError("reconciliation requires the current context and inspection")
        if profile["execution"]["state"] != "outcome_unknown" or not profile["evidence_refs"]:
            raise ValueError("reconciliation proposal requires an unknown outcome and saved evidence references")
        fields = ("project_id", "mission_id", "asset_id", "platform", "source_revision", "memory_revision",
                  "configuration_version", "allowed_actions", "budget", "execution", "evidence_refs")
        result = {key: profile[key] for key in fields}
        result.update(schema_version=1, kind="jarvis.reconciliation_proposal", handoff_id=handoff_id,
            handoff_sha256=profile["handoff_sha256"], context_sha256=expected_sha256,
            context_revision=inspection["lineage"][0]["context"]["revision"],
            inspection_sha256=expected_inspection_sha256, visibility="owner_private",
            control_state=profile.get("control", {"state": "legacy_uncontrolled"})["state"],
            review_state="proposed_unverified", proposed_resolution="retain_hold",
            evidence_verification="not_established", retry_authorized=False, external_actions=0)
        if profile["schema_version"] == 3:
            # Keep strict version-1 proposals unchanged for older contexts.
            result.update(schema_version=2, destination_id=profile["destination_id"])
        return {**result, "proposal_sha256": digest(result)}

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
            original, handoff = self._handoff(profile.get("handoff_id"))
            profile = validate_context(profile, handoff)
            existing = self.db.execute("SELECT * FROM handoff_contexts WHERE handoff_id=?",
                                       (profile["handoff_id"],)).fetchone()
            revision = existing["revision"] if existing else 0
            if revision != expected_revision:
                raise ValueError("context revision mismatch")
            checksum = digest(profile)
            if (profile["schema_version"] == 3 and (not existing or self._context(profile["handoff_id"])[1]["schema_version"] < 3)
                and original["state"] != "pending_review"):
                raise ValueError("destination binding must precede the original handoff review")
            if existing:
                _, old = self._context(profile["handoff_id"])
                if old["execution"]["state"] == "outcome_unknown":
                    if any(profile["execution"][field] != old["execution"][field]
                           for field in ("state", "attempts", "context_id")):
                        raise ValueError("unknown outcome cannot be cleared or retried by context edit")
                if old["schema_version"] == 3 and profile.get("destination_id") != old["destination_id"]:
                    raise ValueError("bound destination cannot change or be removed")
                if old["schema_version"] >= 2:
                    if profile["schema_version"] < old["schema_version"]:
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

    def bind_destination_observation(self, handoff_id, observation, *, expected_sha256,
                                     expected_source_revision, expected_memory_revision, now=None):
        """Bind supplied read metadata to exact destination context; no authority."""
        require_digest(expected_sha256)
        report = connector_report([observation], now=now)
        loaded = self.load_context(handoff_id, expected_source_revision=expected_source_revision,
                                   expected_memory_revision=expected_memory_revision)
        profile = loaded["profile"]
        if (profile["schema_version"] != 3 or loaded["context_sha256"] != expected_sha256
            or observation["connector"] != profile["platform"]
            or observation["source_revision"] != profile["source_revision"]):
            raise ValueError("observation requires the exact destination context, provider and source revision")
        fields = ("project_id", "mission_id", "asset_id", "platform", "destination_id",
                  "source_revision", "memory_revision", "configuration_version")
        result = {key: profile[key] for key in fields}
        result.update(schema_version=1, kind="jarvis.destination_observation", handoff_id=handoff_id,
            handoff_sha256=profile["handoff_sha256"], context_revision=loaded["revision"],
            context_sha256=expected_sha256, observation=dict(observation), visibility="owner_private",
            review_state=loaded["review_state"], observation_status=report[profile["platform"]]["status"],
            observation_verification="integrity_only", runtime_available="unknown",
            dispatch_authorized=False, external_actions=0)
        return {**result, "receipt_sha256": digest(result)}

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
