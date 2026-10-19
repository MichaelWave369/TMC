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
