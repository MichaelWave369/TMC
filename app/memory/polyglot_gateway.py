"""Φ Memory Polyglot R1: offline, approval-bound, one-use read capabilities.

Not an HTTP server, encryption facility, or hardened process boundary.
Only a trusted local operator process may hold the signing key or source store.
"""
from __future__ import annotations

import base64
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3
import time
from typing import Any

from app.memory.models import ApprovalStatus
from app.memory.polyglot import READERS, ReaderGrant, project_capsule, source_fingerprint

SCHEMA = "phi.memory.polyglot.capability.r1"
_APPROVAL_ACTION = "memory.polyglot.read"
_DENIED = "memory polyglot gateway: access denied"
_MAX_TTL_SECONDS = 300
_MAX_TOKEN_LENGTH = 4096
_URLSAFE = re.compile(r"^[A-Za-z0-9_-]+$")


def _serialize(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    if not value or not _URLSAFE.fullmatch(value):
        raise ValueError("invalid encoding")
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if _b64(raw) != value:
        raise ValueError("noncanonical encoding")
    return raw


def _scope(grant: ReaderGrant) -> dict[str, Any]:
    if (grant.reader not in READERS or not grant.profile_id or not grant.vault_id
            or not grant.workspace_ids
            or not all(isinstance(s, str) and s for s in grant.workspace_ids)):
        raise PermissionError(_DENIED)
    return {
        "reader": grant.reader,
        "profile_id": grant.profile_id,
        "vault_id": grant.vault_id,
        "workspace_ids": sorted(grant.workspace_ids),
    }


def _approval_matches(approval: Any, grant: ReaderGrant, capsule_id: str) -> bool:
    if (approval is None or approval.status != ApprovalStatus.approved
            or approval.action_type != _APPROVAL_ACTION):
        return False
    expected = {"capsule_id": capsule_id, **_scope(grant)}
    return approval.payload == expected


class LocalCapabilityGateway:
    """A trust-boundary helper for an already-authenticated local operator process.

    TMC store must support get_capsule(id) and get_approval(id). Reuse the same
    private persistent ledger path, or replay/revocation protection is lost.
    """

    def __init__(self, *, store: Any, secret_key: bytes, ledger_path: str | Path) -> None:
        if not isinstance(secret_key, bytes) or len(secret_key) < 32:
            raise ValueError("a separately provisioned 32+ byte secret key is required")
        if str(ledger_path) == ":memory:" or not Path(ledger_path).parent.is_dir():
            raise ValueError("a persistent ledger in a preexisting private directory is required")
        self._store = store
        self._key = secret_key
        self._ledger_path = str(ledger_path)
        # Caller must enforce private filesystem permissions and key handling.
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS used_tokens (
                    nonce TEXT PRIMARY KEY, used_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS revoked_capsules (
                    capsule_id TEXT PRIMARY KEY, revoked_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS read_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_at INTEGER NOT NULL,
                    reader TEXT NOT NULL,
                    capsule_id TEXT NOT NULL,
                    outcome TEXT NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._ledger_path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _audit(self, *, reader: str, capsule_id: str, outcome: str, now: int) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO read_audit(event_at,reader,capsule_id,outcome) VALUES (?,?,?,?)",
                (now, reader, capsule_id, outcome),
            )

    def issue(
        self, *, capsule_id: str, grant: ReaderGrant, approval_id: str,
        ttl_seconds: int = 120, now: int | None = None,
    ) -> str:
        """Operator-side issuance. Requires a matching approved TMC ApprovalItem."""
        when = int(time.time()) if now is None else now
        if (type(when) is not int or type(ttl_seconds) is not int
                or not 1 <= ttl_seconds <= _MAX_TTL_SECONDS
                or not capsule_id or not approval_id):
            raise PermissionError(_DENIED)
        scope = _scope(grant)
        approval = self._store.get_approval(approval_id)
        capsule = self._store.get_capsule(capsule_id)
        if not _approval_matches(approval, grant, capsule_id) or capsule is None:
            raise PermissionError(_DENIED)
        project_capsule(capsule, reader=grant.reader, grant=grant)
        with self._connect() as db:
            if db.execute("SELECT 1 FROM revoked_capsules WHERE capsule_id=?", (capsule_id,)).fetchone():
                raise PermissionError(_DENIED)
        payload = {
            "schema": SCHEMA,
            "capsule_id": capsule_id,
            "source_sha256": source_fingerprint(capsule),
            "approval_id": approval_id,
            "scope": scope,
            "iat": when,
            "exp": when + ttl_seconds,
            "nonce": secrets.token_hex(16),
        }
        body = _b64(_serialize(payload))
        signature = _b64(hmac.digest(self._key, body.encode("ascii"), "sha256"))
        return body + "." + signature

    def _verify(self, token: str, *, requested_reader: str, now: int) -> tuple[dict[str, Any], ReaderGrant]:
        if (not isinstance(token, str) or len(token) > _MAX_TOKEN_LENGTH
                or token.count(".") != 1 or requested_reader not in READERS):
            raise PermissionError(_DENIED)
        try:
            body, mac = token.split(".")
            signature = _unb64(mac)
            _unb64(body)
            expected = hmac.digest(self._key, body.encode("ascii"), "sha256")
            if not hmac.compare_digest(signature, expected):
                raise ValueError("signature mismatch")
            payload = json.loads(_unb64(body))
            if not isinstance(payload, dict) or set(payload) != {
                "schema", "capsule_id", "source_sha256", "approval_id",
                "scope", "iat", "exp", "nonce",
            }:
                raise ValueError("bad payload")
            if payload["schema"] != SCHEMA:
                raise ValueError("wrong schema")
            scope = payload["scope"]
            if not isinstance(scope, dict) or set(scope) != {
                "reader", "profile_id", "vault_id", "workspace_ids",
            }:
                raise ValueError("bad scope")
            if not isinstance(scope["workspace_ids"], list) or not all(
                isinstance(w, str) and w for w in scope["workspace_ids"]
            ) or len(scope["workspace_ids"]) != len(set(scope["workspace_ids"])):
                raise ValueError("bad workspace")
            grant = ReaderGrant(
                reader=scope["reader"], profile_id=scope["profile_id"],
                vault_id=scope["vault_id"], workspace_ids=frozenset(scope["workspace_ids"]),
            )
            if _scope(grant) != scope or grant.reader != requested_reader:
                raise ValueError("wrong reader")
            if not all(isinstance(payload[k], str) and payload[k] for k in (
                "capsule_id", "source_sha256", "approval_id", "nonce"
            )):
                raise ValueError("missing identifiers")
            if (not re.fullmatch(r"[0-9a-f]{64}", payload["source_sha256"])
                    or not re.fullmatch(r"[0-9a-f]{32}", payload["nonce"])):
                raise ValueError("bad hash or nonce")
            issued, expires = payload["iat"], payload["exp"]
            if (type(issued) is not int or type(expires) is not int
                    or issued > now or expires <= now
                    or not 1 <= expires - issued <= _MAX_TTL_SECONDS):
                raise ValueError("expired capability")
            return payload, grant
        except (ValueError, TypeError, KeyError, UnicodeDecodeError, OverflowError) as exc:
            raise PermissionError(_DENIED) from exc

    def read(self, *, token: str, reader: str, now: int | None = None) -> dict[str, Any]:
        """Redeem a one-use capability for an R0 read-only projection."""
        when = int(time.time()) if now is None else now
        if type(when) is not int:
            raise PermissionError(_DENIED)
        try:
            payload, grant = self._verify(token, requested_reader=reader, now=when)
        except PermissionError:
            self._audit(reader="unknown", capsule_id="unknown", outcome="denied", now=when)
            raise
        capsule_id = payload["capsule_id"]
        try:
            approval = self._store.get_approval(payload["approval_id"])
            capsule = self._store.get_capsule(capsule_id)
            if not _approval_matches(approval, grant, capsule_id) or capsule is None:
                raise PermissionError(_DENIED)
            if not hmac.compare_digest(payload["source_sha256"], source_fingerprint(capsule)):
                raise PermissionError(_DENIED)
            projection = project_capsule(capsule, reader=reader, grant=grant)
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                if db.execute("SELECT 1 FROM revoked_capsules WHERE capsule_id=?", (capsule_id,)).fetchone():
                    raise PermissionError(_DENIED)
                try:
                    db.execute("INSERT INTO used_tokens(nonce,used_at) VALUES(?,?)", (payload["nonce"], when))
                except sqlite3.IntegrityError as exc:
                    raise PermissionError(_DENIED) from exc
                db.execute(
                    "INSERT INTO read_audit(event_at,reader,capsule_id,outcome) VALUES (?,?,?,?)",
                    (when, reader, capsule_id, "allowed"),
                )
            return projection
        except PermissionError:
            self._audit(reader=reader, capsule_id=capsule_id, outcome="denied", now=when)
            raise

    def revoke_capsule(self, capsule_id: str, *, now: int | None = None) -> None:
        """Deny outstanding and future capabilities for a capsule in this ledger."""
        if not capsule_id:
            raise ValueError("capsule_id required")
        when = int(time.time()) if now is None else now
        with self._connect() as db:
            db.execute("INSERT OR IGNORE INTO revoked_capsules(capsule_id,revoked_at) VALUES (?,?)", (capsule_id, when))

    def audit_records(self) -> list[dict[str, Any]]:
        """Local operator diagnostics; IDs can be sensitive and must remain private."""
        with self._connect() as db:
            rows = db.execute("SELECT event_at,reader,capsule_id,outcome FROM read_audit ORDER BY id").fetchall()
        return [dict(zip(("event_at", "reader", "capsule_id", "outcome"), row)) for row in rows]
