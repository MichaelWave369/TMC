"""SQLite store for v0.5 entities."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from app.memory.models import (
    AgentSession,
    ApprovalItem,
    Attachment,
    AuditLog,
    Capsule,
    ConflictRecord,
    DeviceIdentity,
    Profile,
    ProjectRecord,
    NextAction,
    NextActionEvent,
    FocusSession,
    FocusSessionEvent,
    Snapshot,
    SyncSession,
    Vault,
)


class SQLiteStore:
    def __init__(self, db_path: str = "data/tmc.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
                CREATE TABLE IF NOT EXISTS capsules (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS next_actions (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS next_action_events (id TEXT PRIMARY KEY, action_id TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS focus_sessions (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS focus_session_events (id TEXT PRIMARY KEY, session_id TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS attachments (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS conflicts (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS vaults (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS profiles (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS devices (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS sync_sessions (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS audit_logs (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS agent_sessions (id TEXT PRIMARY KEY, payload TEXT);
                """
            )

    def _upsert(self, table: str, id_: str, payload: dict):
        with self._connect() as conn:
            conn.execute(f"INSERT OR REPLACE INTO {table} VALUES (?,?)", (id_, json.dumps(payload)))

    def _all(self, table: str):
        with self._connect() as conn:
            rows = conn.execute(f"SELECT payload FROM {table}").fetchall()
        return [json.loads(r[0]) for r in rows]

    def _get(self, table: str, id_: str):
        with self._connect() as conn:
            r = conn.execute(f"SELECT payload FROM {table} WHERE id=?", (id_,)).fetchone()
        return json.loads(r[0]) if r else None

    def _delete(self, table: str, id_: str):
        with self._connect() as conn:
            conn.execute(f"DELETE FROM {table} WHERE id=?", (id_,))

    def upsert_capsule(self, c: Capsule): self._upsert("capsules", c.id, c.model_dump(mode="json"))
    def get_capsules(self): return [Capsule.model_validate(x) for x in self._all("capsules")]
    def get_capsule(self, id_: str):
        x = self._get("capsules", id_)
        return Capsule.model_validate(x) if x else None
    def delete_capsule(self, id_: str): self._delete("capsules", id_)

    def upsert_project(self, x: ProjectRecord): self._upsert("projects", x.id, x.model_dump(mode="json"))
    def get_projects(self): return [ProjectRecord.model_validate(x) for x in self._all("projects")]

    def get_next_actions(self) -> list[NextAction]:
        return [NextAction.model_validate(x) for x in self._all("next_actions")]

    def get_next_action(self, action_id: str) -> NextAction | None:
        record = self._get("next_actions", action_id)
        return NextAction.model_validate(record) if record else None

    def get_next_action_events(self, action_id: str) -> list[NextActionEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM next_action_events WHERE action_id=? ORDER BY rowid",
                (action_id,),
            ).fetchall()
        return [NextActionEvent.model_validate(json.loads(r[0])) for r in rows]

    def save_next_action_transition(
        self, action: NextAction, event: NextActionEvent, *,
        expected_status: str | None,
    ) -> None:
        """Atomically update action and append a separate event row.

        Local SQLite rows are not tamper-proof or digitally signed. The
        expected-status guard prevents accidental competing transitions.
        """
        if action.id != event.action_id or action.profile_id != event.profile_id:
            raise ValueError("Mismatched action transition")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT payload FROM next_actions WHERE id=?", (action.id,)
            ).fetchone()
            if expected_status is None:
                if existing is not None:
                    raise ValueError("Next action already exists")
            elif existing is None or (
                json.loads(existing[0]).get("status") != expected_status
            ):
                raise ValueError("Stale or missing action state")
            conn.execute(
                "INSERT OR REPLACE INTO next_actions(id, payload) VALUES (?,?)",
                (action.id, json.dumps(action.model_dump(mode="json"))),
            )
            conn.execute(
                "INSERT INTO next_action_events(id, action_id, payload) VALUES (?,?,?)",
                (event.id, event.action_id, json.dumps(event.model_dump(mode="json"))),
            )

    def get_focus_sessions(self) -> list[FocusSession]:
        return [FocusSession.model_validate(x) for x in self._all("focus_sessions")]

    def get_focus_session(self, session_id: str) -> FocusSession | None:
        record = self._get("focus_sessions", session_id)
        return FocusSession.model_validate(record) if record else None

    def get_focus_session_events(self, session_id: str) -> list[FocusSessionEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM focus_session_events WHERE session_id=? ORDER BY rowid",
                (session_id,),
            ).fetchall()
        return [FocusSessionEvent.model_validate(json.loads(r[0])) for r in rows]

    def save_focus_transition(
        self, session: FocusSession, event: FocusSessionEvent, *,
        expected_status: str | None,
    ) -> None:
        """Atomically save local operator session and transition event.

        One active focus session per profile is enforced inside the SQLite
        write transaction, including when two operator windows race.
        Records are not signed, immutable, encrypted, or independently verified.
        """
        if session.id != event.session_id or session.profile_id != event.profile_id:
            raise ValueError("Mismatched focus transition")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            old = conn.execute(
                "SELECT payload FROM focus_sessions WHERE id=?", (session.id,)
            ).fetchone()
            if expected_status is None:
                if old is not None or session.status.value != "active" or event.transition != "started":
                    raise ValueError("Invalid focus session creation")
                records = conn.execute("SELECT payload FROM focus_sessions").fetchall()
                if any(
                    (r.get("profile_id") == session.profile_id and r.get("status") == "active")
                    for r in (json.loads(row[0]) for row in records)
                ):
                    raise ValueError("A focus session is already active for this profile")
            else:
                if (old is None or json.loads(old[0]).get("status") != expected_status
                        or expected_status != "active"
                        or session.status.value != "closed" or event.transition != "closed"):
                    raise ValueError("Stale or invalid focus session transition")
            conn.execute(
                "INSERT OR REPLACE INTO focus_sessions(id, payload) VALUES (?, ?)",
                (session.id, json.dumps(session.model_dump(mode="json"))),
            )
            conn.execute(
                "INSERT INTO focus_session_events(id, session_id, payload) VALUES (?, ?, ?)",
                (event.id, event.session_id, json.dumps(event.model_dump(mode="json"))),
            )

    def upsert_attachment(self, x: Attachment): self._upsert("attachments", x.id, x.model_dump(mode="json"))
    def get_attachments(self): return [Attachment.model_validate(x) for x in self._all("attachments")]
    def get_attachment(self, id_: str):
        x = self._get("attachments", id_)
        return Attachment.model_validate(x) if x else None

    def upsert_conflict(self, x: ConflictRecord): self._upsert("conflicts", x.id, x.model_dump(mode="json"))
    def get_conflicts(self): return [ConflictRecord.model_validate(x) for x in self._all("conflicts")]

    def upsert_vault(self, x: Vault): self._upsert("vaults", x.vault_id, x.model_dump(mode="json"))
    def get_vaults(self): return [Vault.model_validate(x) for x in self._all("vaults")]
    def get_vault(self, id_: str):
        x = self._get("vaults", id_)
        return Vault.model_validate(x) if x else None

    def upsert_profile(self, x: Profile): self._upsert("profiles", x.profile_id, x.model_dump(mode="json"))
    def get_profiles(self): return [Profile.model_validate(x) for x in self._all("profiles")]

    def upsert_device(self, x: DeviceIdentity): self._upsert("devices", x.device_id, x.model_dump(mode="json"))
    def get_devices(self): return [DeviceIdentity.model_validate(x) for x in self._all("devices")]

    def upsert_sync_session(self, x: SyncSession): self._upsert("sync_sessions", x.id, x.model_dump(mode="json"))
    def get_sync_sessions(self): return [SyncSession.model_validate(x) for x in self._all("sync_sessions")]

    def upsert_snapshot(self, x: Snapshot): self._upsert("snapshots", x.id, x.model_dump(mode="json"))
    def get_snapshots(self): return [Snapshot.model_validate(x) for x in self._all("snapshots")]

    def append_audit(self, x: AuditLog): self._upsert("audit_logs", x.id, x.model_dump(mode="json"))
    def get_audits(self): return sorted([AuditLog.model_validate(x) for x in self._all("audit_logs")], key=lambda a: a.created_at)

    def upsert_approval(self, x: ApprovalItem): self._upsert("approvals", x.id, x.model_dump(mode="json"))
    def get_approvals(self): return [ApprovalItem.model_validate(x) for x in self._all("approvals")]
    def get_approval(self, id_: str):
        x = self._get("approvals", id_)
        return ApprovalItem.model_validate(x) if x else None

    def upsert_agent_session(self, x: AgentSession): self._upsert("agent_sessions", x.id, x.model_dump(mode="json"))
    def get_agent_session(self, id_: str):
        x = self._get("agent_sessions", id_)
        return AgentSession.model_validate(x) if x else None

    def set_kv(self, k: str, v: str):
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (k, v))

    def get_kv(self, k: str, default: str = "") -> str:
        with self._connect() as conn:
            r = conn.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return r[0] if r else default

    def load_legacy_seed(self, payload: dict):
        if isinstance(payload, list):
            payload = {"capsules": payload}
        for c in payload.get("capsules", []):
            self.upsert_capsule(Capsule.model_validate(c))
        for p in payload.get("projects", []):
            self.upsert_project(ProjectRecord.model_validate(p))
        for a in payload.get("attachments", []):
            self.upsert_attachment(Attachment.model_validate(a))
