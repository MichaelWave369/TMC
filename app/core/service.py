"""TMC v1.0.0 GA service core for private operator memory workflows."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from app.core.diagnostics import compute_metrics
from app.memory.embeddings import EmbeddingManager
from app.memory.graph_store import MemoryGraph
from app.memory.ingestion import build_attachment, parse_file, to_capsules
from app.memory.models import (
    AgentSession,
    ApprovalItem,
    ApprovalStatus,
    AuditLog,
    Capsule,
    CapsuleKind,
    CapsuleStatus,
    ConflictRecord,
    DeviceIdentity,
    IngestRequest,
    PolicyMode,
    Profile,
    ProjectRecord,
    Snapshot,
    SyncSession,
    TrustStatus,
    Vault,
    VaultStatus,
)
from app.memory.policies import PolicyEngine
from app.memory.retrieval import RetrievalEngine
from app.memory.storage import SQLiteStore
from app.runtime.config import ConfigManager
from app.runtime.integrity import apply_repairs, run_integrity_checks
from app.runtime.jobs import JobSystem
from app.runtime.service_runner import ServiceRunner
from app.runtime.support import export_support_bundle
from app.automation.rules import RuleEngine
from app.connectors.base import ConnectorManager
from app.integrations.apps import AppIntegrationRegistry
from app.platform.event_bus import Event, EventBus
from app.plugins.sdk import PluginManifest, PluginRegistry
from app.tools.actions import ToolExecutor
from app.platform.compat import DEFAULT_FEATURE_FLAGS, compatibility_report
from app.platform.governance import POLICY_TEMPLATES, effective_policy, simulate_policy
from app.platform.migration import upgrade_apply, upgrade_preview
from app.platform.onboarding import onboarding_templates
from app.platform.reporting import memory_quality_report, operational_report
from app.platform.release import performance_baseline, release_readiness, release_validation


def _kdf(passphrase: str, salt: str) -> bytes:
    return hashlib.sha256((passphrase + salt).encode()).digest()


def _xor_cipher(text: bytes, key: bytes) -> bytes:
    return bytes([b ^ key[i % len(key)] for i, b in enumerate(text)])


class MemoryService:
    def __init__(self, db_path: str = "data/tmc.db") -> None:
        self.store = SQLiteStore(db_path)
        self.embeddings = EmbeddingManager("tfidf")
        self.graph = MemoryGraph()
        self.policy = PolicyEngine()
        self.retrieval_engine = RetrievalEngine(self.embeddings, self.graph, self.policy)
        self.active_profile_id = self.store.get_kv("active_profile", "default")
        self._unlock_cache: dict[str, str] = {}
        self.config = ConfigManager()
        self.jobs = JobSystem(self.store)
        self.runner = ServiceRunner()
        self.event_bus = EventBus(max_history=800)
        self.plugins = PluginRegistry(self.store)
        self.connectors = ConnectorManager(self.store, self)
        self.rules = RuleEngine(self.store, self, self.event_bus)
        self.apps = AppIntegrationRegistry(self.store)
        self.tools = ToolExecutor(self)
        self._feature_flags = dict(DEFAULT_FEATURE_FLAGS)
        self.module_catalog = []
        self._bootstrap_defaults()
        self.refresh_indexes()

    def _bootstrap_defaults(self):
        if not self.store.get_profiles():
            self.store.upsert_profile(Profile(profile_id="default", display_name="Default Operator", default_vault_id="vault-default"))
        if not self.store.get_vaults():
            self.store.upsert_vault(Vault(vault_id="vault-default", display_name="Default Vault", status=VaultStatus.unlocked, key_derivation_metadata={"salt": "default"}, storage_path="data/vaults/vault-default"))
        if not self.store.get_devices():
            self.store.upsert_device(DeviceIdentity(device_id="device-local", device_name="Local Device", trust_status=TrustStatus.trusted))
        seed = Path("data/sample_capsules.json")
        if seed.exists() and not self.store.get_capsules():
            self.store.load_legacy_seed(json.loads(seed.read_text()))

    def _audit(self, action: str, payload: dict | None = None, note: str = ""):
        row = payload or {}
        self.store.append_audit(AuditLog(action=action, payload=row, note=note))
        ev = self.event_bus.publish(Event(event_type=action, source="audit", payload=row, profile_id=self.active_profile_id))
        self.rules.handle_event(ev)

    def refresh_indexes(self):
        scoped = [c for c in self.store.get_capsules() if c.profile_id == self.active_profile_id]
        self.embeddings.rebuild([(c.id, c.text) for c in scoped])
        self.graph.rebuild(scoped)

    # Vaults
    def create_vault(self, display_name: str, owner_label: str, passphrase: str) -> Vault:
        salt = hashlib.sha256(display_name.encode()).hexdigest()[:16]
        v = Vault(display_name=display_name, owner_label=owner_label, key_derivation_metadata={"salt": salt}, status=VaultStatus.locked, storage_path=f"data/vaults/{display_name.lower().replace(' ','-')}")
        Path(v.storage_path).mkdir(parents=True, exist_ok=True)
        self.store.upsert_vault(v)
        self._unlock_cache.pop(v.vault_id, None)
        self._audit("vault_create", {"vault_id": v.vault_id})
        return v

    def lock_vault(self, vault_id: str):
        v = self.store.get_vault(vault_id)
        if not v:
            return {"status": "missing"}
        v.status = VaultStatus.locked
        self._unlock_cache.pop(vault_id, None)
        self.store.upsert_vault(v)
        self._audit("vault_lock", {"vault_id": vault_id})
        return {"status": "locked", "vault_id": vault_id}

    def unlock_vault(self, vault_id: str, passphrase: str):
        v = self.store.get_vault(vault_id)
        if not v:
            return {"status": "missing"}
        salt = v.key_derivation_metadata.get("salt", "default")
        self._unlock_cache[vault_id] = base64.b64encode(_kdf(passphrase, salt)).decode()
        v.status = VaultStatus.unlocked
        self.store.upsert_vault(v)
        self._audit("vault_unlock", {"vault_id": vault_id})
        return {"status": "unlocked", "vault_id": vault_id}

    def list_vaults(self):
        return [v.model_dump(mode="json") for v in self.store.get_vaults()]

    # Profiles
    def create_profile(self, display_name: str, default_vault_id: str, default_policy_profile: str = "strict") -> Profile:
        p = Profile(display_name=display_name, default_vault_id=default_vault_id, default_policy_profile=default_policy_profile)
        self.store.upsert_profile(p)
        self._audit("profile_create", {"profile_id": p.profile_id})
        return p

    def list_profiles(self):
        return [p.model_dump(mode="json") for p in self.store.get_profiles()]

    def switch_profile(self, profile_id: str):
        self.active_profile_id = profile_id
        self.store.set_kv("active_profile", profile_id)
        self.refresh_indexes()
        self._audit("profile_switch", {"profile_id": profile_id})
        return {"status": "ok", "active_profile": profile_id}


    def _ingest_request(self, source_type: str, source_ref: str, text: str, profile_id: str | None = None, workspace_ids: list[str] | None = None):
        return IngestRequest(source_type=source_type, source_ref=source_ref, text=text, profile_id=profile_id or self.active_profile_id, workspace_ids=workspace_ids or [])

    # Capsules
    def ingest_text(self, req: IngestRequest):
        req.profile_id = req.profile_id or self.active_profile_id
        caps = to_capsules(req)
        for c in caps:
            c.profile_id = req.profile_id
            self.store.upsert_capsule(c)
        self._detect_conflicts(caps)
        self.refresh_indexes()
        self._audit("ingest", {"count": len(caps), "profile_id": req.profile_id})
        return caps

    def _detect_conflicts(self, new_capsules: list[Capsule]):
        existing = self.store.get_capsules()
        for n in new_capsules:
            for c in existing:
                if c.id == n.id or c.profile_id != n.profile_id:
                    continue
                if set(c.tags) & set(n.tags) and "not " in n.text.lower() and "not " not in c.text.lower():
                    c.status = CapsuleStatus.superseded
                    n.status = CapsuleStatus.conflicting
                    self.store.upsert_capsule(c)
                    self.store.upsert_capsule(n)
                    self.store.upsert_conflict(ConflictRecord(capsule_a=c.id, capsule_b=n.id, conflict_type="sync_or_update_conflict", confidence=0.72, note="contradiction detected"))

    def ingest_file(self, path: str, source_type: str = "file"):
        text = parse_file(path)
        caps = self.ingest_text(IngestRequest(source_type=source_type, source_ref=path, text=text, profile_id=self.active_profile_id))
        att = build_attachment(path, [c.id for c in caps])
        att.vault_id = caps[0].vault_id if caps else "vault-default"
        self.store.upsert_attachment(att)
        return caps

    def retrieve(self, query: str, context: dict, top_k: int = 5):
        scoped = [c for c in self.store.get_capsules() if c.profile_id == context.get("profile_id", self.active_profile_id)]
        results = self.retrieval_engine.retrieve(query, scoped, context, top_k)
        self._audit("retrieve", {"query": query, "count": len(results)})
        return [r.model_dump(mode="json") for r in results]


    # Local capsule lifecycle: all mutations require the active operator profile.
    # These methods do not grant external API authority or verify the truth of a memory.
    def _owned_capsule(self, capsule_id: str) -> Capsule | None:
        capsule = self.store.get_capsule(capsule_id)
        if capsule is None or capsule.profile_id != self.active_profile_id:
            return None
        return capsule

    def _mutable_capsule(self, capsule_id: str) -> Capsule | None:
        capsule = self._owned_capsule(capsule_id)
        if capsule is None or capsule.policy == PolicyMode.locked:
            return None
        vault = self.store.get_vault(capsule.vault_id)
        if vault is None or vault.status != VaultStatus.unlocked:
            return None
        return capsule

    def delete_capsule(self, capsule_id: str) -> bool:
        capsule = self._mutable_capsule(capsule_id)
        if capsule is None or capsule.pinned:
            return False
        self.store.delete_capsule(capsule_id)
        for attachment in self.store.get_attachments():
            if capsule_id in attachment.capsule_ids:
                attachment.capsule_ids = [
                    link for link in attachment.capsule_ids if link != capsule_id
                ]
                self.store.upsert_attachment(attachment)
        self.refresh_indexes()
        self._audit("capsule_delete", {"capsule_id": capsule_id})
        return True

    def set_capsule_state(self, capsule_id: str, action: str) -> Capsule | None:
        if action not in {"lock", "archive"}:
            raise ValueError("Unsupported capsule state action")
        capsule = self._mutable_capsule(capsule_id)
        if capsule is None:
            return None
        if action == "lock":
            capsule.policy = PolicyMode.locked
        else:
            capsule.status = CapsuleStatus.archived
        self.store.upsert_capsule(capsule)
        self.refresh_indexes()
        self._audit("capsule_state", {"capsule_id": capsule_id, "action": action})
        return capsule

    def promote_identity(self, capsule_id: str) -> Capsule | None:
        """Classify a memory as identity; never certify its factual validity."""
        capsule = self._mutable_capsule(capsule_id)
        if capsule is None or capsule.status == CapsuleStatus.archived:
            return None
        capsule.kind = CapsuleKind.identity
        capsule.metadata = {**capsule.metadata, "identity_review": "operator_requested"}
        self.store.upsert_capsule(capsule)
        self.refresh_indexes()
        self._audit("identity_classify", {"capsule_id": capsule_id})
        return capsule

    def create_project(self, workspace_id: str, name: str) -> ProjectRecord:
        if not workspace_id.strip() or not name.strip():
            raise ValueError("Workspace ID and project name are required")
        if any(
            p.profile_id == self.active_profile_id and p.workspace_id == workspace_id
            for p in self.store.get_projects()
        ):
            raise ValueError("Workspace already registered for this profile")
        project = ProjectRecord(
            profile_id=self.active_profile_id, workspace_id=workspace_id, name=name
        )
        self.store.upsert_project(project)
        self._audit("project_create", {"project_id": project.id})
        return project

    def assign_projects(self, capsule_id: str, workspace_ids: list[str]) -> Capsule | None:
        capsule = self._mutable_capsule(capsule_id)
        if capsule is None or capsule.status == CapsuleStatus.archived:
            return None
        registered = {
            p.workspace_id for p in self.store.get_projects()
            if p.profile_id == self.active_profile_id
        }
        if not workspace_ids or any(wid not in registered for wid in workspace_ids):
            raise ValueError("Unknown project workspace or empty assignment")
        capsule.workspace_ids = list(dict.fromkeys(workspace_ids))
        self.store.upsert_capsule(capsule)
        self.refresh_indexes()
        self._audit("project_assign", {"capsule_id": capsule_id, "count": len(capsule.workspace_ids)})
        return capsule

    def export_capsules(self, include_private: bool = False) -> dict:
        """Explicit local JSON export; NOT a safe remote sync or encrypted backup."""
        capsules = [
            c.model_dump(mode="json")
            for c in self.store.get_capsules()
            if c.profile_id == self.active_profile_id
            and c.policy not in {PolicyMode.locked, PolicyMode.session, PolicyMode.ephemeral}
            and c.status != CapsuleStatus.archived
            and (include_private or c.policy != PolicyMode.private_local_only)
            and (v := self.store.get_vault(c.vault_id)) is not None
            and v.status == VaultStatus.unlocked
        ]
        self._audit("capsule_export", {"count": len(capsules), "include_private": include_private})
        return {"capsules": capsules}

    def import_capsules(self, payload: dict) -> dict:
        """Local import into the active profile; never silently overwrite existing IDs."""
        if not isinstance(payload, dict) or not isinstance(payload.get("capsules"), list):
            raise ValueError("Expected capsule bundle")
        incoming = [Capsule.model_validate(item) for item in payload["capsules"]]
        ids = [c.id for c in incoming]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate capsule IDs in bundle")
        new_capsules = []
        for capsule in incoming:
            if capsule.profile_id != self.active_profile_id:
                raise ValueError("Cross-profile import not permitted")
            vault = self.store.get_vault(capsule.vault_id)
            if vault is None or vault.status != VaultStatus.unlocked:
                raise ValueError("Destination vault unavailable or locked")
            prior = self.store.get_capsule(capsule.id)
            if prior is not None:
                # An identical source may already exist after default seed creation.
                # Ignore an idempotent reimport; reject a conflicting collision.
                stable = {"created_at", "updated_at"}
                if prior.model_dump(exclude=stable) != capsule.model_dump(exclude=stable):
                    raise ValueError("Existing capsule ID requires conflict review")
                continue
            new_capsules.append(capsule)
        for capsule in new_capsules:
            self.store.upsert_capsule(capsule)
        self.refresh_indexes()
        self._audit("capsule_import", {"count": len(new_capsules)})
        return {"status": "ok", "count": len(new_capsules)}

    def reingest_attachment(self, attachment_id: str) -> list[Capsule]:
        """Re-extract an unchanged local attachment without duplicating its memories."""
        attachment = self.store.get_attachment(attachment_id)
        if attachment is None or not attachment.capsule_ids:
            return []
        linked = [self._owned_capsule(cid) for cid in attachment.capsule_ids]
        if any(c is None for c in linked):
            return []
        if any(c.policy == PolicyMode.locked for c in linked):
            return []
        vault = self.store.get_vault(attachment.vault_id)
        if vault is None or vault.status != VaultStatus.unlocked:
            return []
        path = Path(attachment.local_path)
        if not path.is_file() or path.suffix.lower() not in {".txt", ".md", ".pdf"}:
            return []
        if hashlib.sha256(path.read_bytes()).hexdigest() != attachment.sha256:
            raise ValueError("Attachment changed; ingest as a new source to preserve lineage")
        attachment.extraction_text = parse_file(str(path))
        attachment.extraction_status = "complete" if attachment.extraction_text else "pending"
        self.store.upsert_attachment(attachment)
        self._audit("attachment_reingest", {"attachment_id": attachment_id})
        return linked

    # Sync peers/sessions
    def register_peer(self, device_name: str, public_key: str, trust_status: str = "pending"):
        d = DeviceIdentity(device_name=device_name, public_key=public_key, trust_status=TrustStatus(trust_status))
        self.store.upsert_device(d)
        self._audit("sync_peer_register", {"device_id": d.device_id})
        return d

    def list_peers(self):
        return [d.model_dump(mode="json") for d in self.store.get_devices()]

    def sync_preview(self, target_device_id: str, include_private: bool = False, include_binaries: bool = False):
        capsules = [c for c in self.store.get_capsules() if c.profile_id == self.active_profile_id]
        filtered = []
        for c in capsules:
            if c.policy == PolicyMode.private_local_only and not include_private:
                continue
            filtered.append(c.model_dump(mode="json"))
        payload = {
            "capsules": filtered,
            "projects": [p.model_dump(mode="json") for p in self.store.get_projects() if p.profile_id == self.active_profile_id],
            "attachments": [a.model_dump(mode="json") for a in self.store.get_attachments()],
            "include_binaries": include_binaries,
        }
        session = SyncSession(source_device_id="device-local", target_device_id=target_device_id, profile_id=self.active_profile_id, preview_payload=payload)
        self.store.upsert_sync_session(session)
        self._audit("sync_preview", {"session_id": session.id, "count": len(filtered)})
        return session

    def sync_apply(self, session_id: str, incoming_payload: dict | None = None):
        s = next((x for x in self.store.get_sync_sessions() if x.id == session_id), None)
        if not s:
            return {"status": "missing"}
        payload = incoming_payload or s.preview_payload
        sensitive = any(c.get("kind") == "identity" for c in payload.get("capsules", []))
        if sensitive:
            ap = ApprovalItem(action_type="sensitive_sync_import", payload={"session_id": session_id})
            self.store.upsert_approval(ap)
            self._audit("sync_apply_queued", {"session_id": session_id, "approval_id": ap.id})
            return {"status": "pending_approval", "approval_id": ap.id}
        self.store.load_legacy_seed(payload)
        s.status = "applied"
        self.store.upsert_sync_session(s)
        self.refresh_indexes()
        self._audit("sync_apply", {"session_id": session_id})
        return {"status": "applied"}

    # approvals
    def list_approvals(self):
        return [a.model_dump(mode="json") for a in self.store.get_approvals()]

    def approval_decide(self, approval_id: str, approve: bool, note: str = ""):
        a = self.store.get_approval(approval_id)
        if not a:
            return {"status": "missing"}
        a.status = ApprovalStatus.approved if approve else ApprovalStatus.rejected
        a.note = note
        self.store.upsert_approval(a)
        self._audit("approval_decide", {"approval_id": approval_id, "status": a.status.value})
        return a.model_dump(mode="json")

    # snapshots/restore
    def create_snapshot(self, vault_id: str, profile_id: str | None = None):
        profile_id = profile_id or self.active_profile_id
        payload = {
            "capsules": [c.model_dump(mode="json") for c in self.store.get_capsules() if c.profile_id == profile_id and c.vault_id == vault_id],
            "projects": [p.model_dump(mode="json") for p in self.store.get_projects() if p.profile_id == profile_id],
            "attachments": [a.model_dump(mode="json") for a in self.store.get_attachments() if a.vault_id == vault_id],
            "conflicts": [c.model_dump(mode="json") for c in self.store.get_conflicts()],
        }
        snap_dir = Path("data/snapshots")
        snap_dir.mkdir(parents=True, exist_ok=True)
        blob = json.dumps(payload).encode()
        checksum = hashlib.sha256(blob).hexdigest()
        path = snap_dir / f"{vault_id}-{profile_id}-{checksum[:8]}.json"
        path.write_bytes(blob)
        s = Snapshot(vault_id=vault_id, profile_id=profile_id, payload_path=str(path), checksum=checksum)
        self.store.upsert_snapshot(s)
        self.store.set_kv("last_snapshot_time", s.created_at.isoformat())
        self._audit("snapshot_create", {"snapshot_id": s.id})
        return s

    def list_snapshots(self):
        return [s.model_dump(mode="json") for s in self.store.get_snapshots()]

    def restore_snapshot(self, snapshot_id: str, dry_run: bool = False, selective: str = "all"):
        s = next((x for x in self.store.get_snapshots() if x.id == snapshot_id), None)
        if not s:
            return {"status": "missing"}
        payload = json.loads(Path(s.payload_path).read_text())
        if dry_run:
            return {"status": "preview", "capsules": len(payload.get("capsules", [])), "selective": selective}
        if selective in {"all", "capsules", "identity_only"}:
            for c in payload.get("capsules", []):
                if selective == "identity_only" and c.get("kind") != "identity":
                    continue
                self.store.upsert_capsule(Capsule.model_validate(c))
        if selective in {"all", "attachments"}:
            for a in payload.get("attachments", []):
                from app.memory.models import Attachment
                self.store.upsert_attachment(Attachment.model_validate(a))
        self.refresh_indexes()
        self.store.set_kv("last_restore_time", str(Path(s.payload_path).stat().st_mtime))
        self._audit("snapshot_restore", {"snapshot_id": snapshot_id, "selective": selective})
        return {"status": "restored", "snapshot_id": snapshot_id}

    # encrypted export/import
    def export_encrypted(self, passphrase: str, include_private: bool = False):
        payload = {
            "capsules": [c.model_dump(mode="json") for c in self.store.get_capsules() if include_private or c.policy != PolicyMode.private_local_only],
            "projects": [p.model_dump(mode="json") for p in self.store.get_projects()],
            "attachments": [a.model_dump(mode="json") for a in self.store.get_attachments()],
        }
        blob = json.dumps(payload).encode()
        key = _kdf(passphrase, "export")
        cipher = base64.b64encode(_xor_cipher(blob, key)).decode()
        self._audit("export_encrypted", {"items": len(payload['capsules'])})
        return {"mode": "xor-kdf", "ciphertext": cipher}

    def import_encrypted(self, passphrase: str, ciphertext: str):
        key = _kdf(passphrase, "export")
        raw = _xor_cipher(base64.b64decode(ciphertext.encode()), key)
        payload = json.loads(raw.decode())
        self.store.load_legacy_seed(payload)
        self.refresh_indexes()
        self._audit("import_encrypted", {"capsules": len(payload.get('capsules', []))})
        return {"status": "ok"}

    # agent runtime
    def agent_session_start(self, profile_id: str, workspace_id: str, task: str):
        s = AgentSession(profile_id=profile_id, workspace_id=workspace_id, task=task)
        self.store.upsert_agent_session(s)
        self._audit("agent_session_start", {"session_id": s.id})
        return s

    def agent_session_append(self, session_id: str, role: str, text: str):
        s = self.store.get_agent_session(session_id)
        if not s:
            return None
        s.messages.append({"role": role, "text": text})
        self.store.upsert_agent_session(s)
        self.ingest_text(IngestRequest(source_type="agent_message", source_ref=session_id, text=text, policy=PolicyMode.session, profile_id=s.profile_id, workspace_ids=[s.workspace_id], metadata={"role": role, "session_id": session_id}))
        return s

    def agent_session_promote(self, session_id: str):
        s = self.store.get_agent_session(session_id)
        if not s:
            return {"status": "missing"}
        txt = "\n".join([f"{m['role']}: {m['text']}" for m in s.messages[-6:]])
        caps = self.ingest_text(IngestRequest(source_type="agent_summary", source_ref=session_id, text=txt, policy=PolicyMode.persistent, profile_id=s.profile_id, workspace_ids=[s.workspace_id], metadata={"promoted_session": True}))
        self._audit("agent_session_promote", {"session_id": session_id})
        return {"status": "ok", "capsules": [c.id for c in caps]}

    def build_context_pack(self, profile_id: str, workspace_id: str, query: str, session_id: str | None = None):
        results = self.retrieve(query, {"profile_id": profile_id, "workspace_id": workspace_id, "session_id": session_id}, top_k=8)
        identity = [c.model_dump(mode="json") for c in self.store.get_capsules() if c.profile_id == profile_id and c.kind == CapsuleKind.identity][:5]
        project = [c.model_dump(mode="json") for c in self.store.get_capsules() if c.profile_id == profile_id and workspace_id in c.workspace_ids][:8]
        recent_session = [c.model_dump(mode="json") for c in self.store.get_capsules() if c.metadata.get("session_id") == session_id][-6:] if session_id else []
        return {
            "context_pack": results,
            "identity_pack": identity,
            "project_pack": project,
            "recent_session_pack": recent_session,
            "explain": {"policy_filtered": True, "profile_id": profile_id, "workspace_id": workspace_id},
        }

    def diagnostics(self):
        caps = self.store.get_capsules()
        base = compute_metrics([c for c in caps if c.profile_id == self.active_profile_id], conflict_count=len(self.store.get_conflicts()), attachment_backlog=sum(1 for a in self.store.get_attachments() if a.extraction_status != "complete"), embedding_provider=self.embeddings.provider_name)
        base.update({
            "locked_vault_count": float(sum(1 for v in self.store.get_vaults() if v.status == VaultStatus.locked)),
            "trusted_device_count": float(sum(1 for d in self.store.get_devices() if d.trust_status == TrustStatus.trusted)),
            "pending_sync_imports": float(sum(1 for s in self.store.get_sync_sessions() if s.status == "preview")),
            "pending_approvals": float(sum(1 for a in self.store.get_approvals() if a.status == ApprovalStatus.pending)),
            "last_snapshot_time": self.store.get_kv("last_snapshot_time", ""),
            "last_restore_time": self.store.get_kv("last_restore_time", ""),
            "per_profile_memory_counts": json.dumps({p.profile_id: sum(1 for c in caps if c.profile_id == p.profile_id) for p in self.store.get_profiles()}),
            "sync_conflict_counts": float(len(self.store.get_conflicts())),
        })
        return base

    # convenience getters
    def list_identity(self):
        return [c.model_dump(mode="json") for c in self.store.get_capsules() if c.profile_id == self.active_profile_id and c.kind == CapsuleKind.identity]
    def list_projects(self):
        return [p.model_dump(mode="json") for p in self.store.get_projects() if p.profile_id == self.active_profile_id]
    def list_attachments(self): return [a.model_dump(mode="json") for a in self.store.get_attachments()]
    def list_conflicts(self): return [c.model_dump(mode="json") for c in self.store.get_conflicts()]
    def list_audit(self): return [a.model_dump(mode="json") for a in self.store.get_audits()]

    def reindex(self):
        self.refresh_indexes()
        self._audit("reindex", {"profile_id": self.active_profile_id})
        return {"status": "ok"}


    # runtime/service/config
    def runtime_status(self):
        cfg = self.config.load()
        return {
            "backend": self.runner.status(),
            "vault_locked_count": sum(1 for v in self.store.get_vaults() if v.status == VaultStatus.locked),
            "indexing_enabled": cfg.get("background_indexing", True),
            "sync_enabled": True,
            "agent_ready": True,
            "active_profile": self.active_profile_id,
        }

    def runtime_start(self):
        self._audit("runtime_start")
        return self.runner.start()

    def runtime_stop(self):
        if self.config.load().get("vault_auto_lock_on_exit", True):
            for v in self.store.get_vaults():
                self.lock_vault(v.vault_id)
        self._audit("runtime_stop")
        return self.runner.stop()

    def runtime_restart(self):
        self._audit("runtime_restart")
        return self.runner.restart()

    def get_config(self):
        return self.config.export_non_secret()

    def validate_config(self, cfg: dict):
        ok, errors = self.config.validate(cfg)
        return {"valid": ok, "errors": errors}

    def onboarding_status(self):
        return {"completed": self.store.get_kv("onboarding_complete", "false") == "true"}

    def onboarding_complete(self):
        self.store.set_kv("onboarding_complete", "true")
        self._audit("onboarding_complete")
        return {"status": "ok"}

    # jobs
    def enqueue_job(self, job_type: str, payload: dict | None = None):
        j = self.jobs.enqueue(job_type, payload)
        self._audit("job_enqueue", {"job_id": j["id"], "job_type": job_type})
        return j

    def list_jobs(self):
        return self.jobs.list_jobs()

    def retry_job(self, job_id: str):
        self.jobs.retry(job_id)
        self._audit("job_retry", {"job_id": job_id})
        return {"status": "queued"}

    def cancel_job(self, job_id: str):
        self.jobs.cancel(job_id)
        self._audit("job_cancel", {"job_id": job_id})
        return {"status": "cancelled"}

    # repair + support
    def repair_check(self):
        out = run_integrity_checks(self)
        self._audit("repair_check", out)
        return out

    def repair_apply(self, preview: bool = True):
        out = apply_repairs(self, {"preview": preview})
        self._audit("repair_apply", {"preview": preview, "status": out.get("status")})
        return out

    def export_support(self, redact: bool = True):
        out = export_support_bundle(self, self.config, redact=redact)
        self._audit("support_export", out)
        return out


    # plugin sdk
    def plugin_install(self, manifest: dict):
        p = self.plugins.install(PluginManifest(**manifest))
        self._audit("plugin_install", {"plugin_id": p["plugin_id"]})
        return p

    def plugin_list(self):
        return self.plugins.list_plugins()

    def plugin_enable(self, plugin_id: str):
        out = self.plugins.enable(plugin_id); self._audit("plugin_enable", {"plugin_id": plugin_id, "status": out.get("status", "ok")}); return out

    def plugin_disable(self, plugin_id: str):
        out = self.plugins.disable(plugin_id); self._audit("plugin_disable", {"plugin_id": plugin_id}); return out

    def plugin_permissions(self, plugin_id: str):
        p = next((x for x in self.plugins.list_plugins() if x["plugin_id"] == plugin_id), None)
        return p or {"status": "missing"}

    def plugin_approve(self, plugin_id: str, permissions: list[str]):
        out = self.plugins.approve(plugin_id, permissions)
        self._audit("plugin_approve", {"plugin_id": plugin_id, "permissions": permissions})
        return out

    # connectors
    def connector_list(self): return self.connectors.list()
    def connector_add(self, connector_type: str, name: str, config: dict):
        out = self.connectors.add(connector_type, name, config); self._audit("connector_add", {"connector_id": out["connector_id"]}); return out
    def connector_sync(self, connector_id: str):
        out = self.connectors.sync(connector_id); self._audit("connector_sync", {"connector_id": connector_id, "status": out.get("status", "ok")}); return out

    # workflows
    def workflow_list(self): return self.rules.list_rules()
    def workflow_create(self, rule: dict):
        out = self.rules.create_rule(rule); self._audit("workflow_create", {"workflow_id": out["id"]}); return out
    def workflow_test(self, rule_id: str, event: dict): return self.rules.test_rule(rule_id, event)

    # events
    def events(self, event_type: str | None = None): return self.event_bus.list_events(event_type=event_type, profile_id=self.active_profile_id)

    # app integrations
    def app_list(self): return self.apps.list()
    def app_register(self, name: str, scopes: list[str]):
        out = self.apps.register(name, scopes); self._audit("app_register", {"app_id": out["app_id"]}); return out
    def app_approve(self, app_id: str):
        out = self.apps.approve(app_id); self._audit("app_approve", {"app_id": app_id}); return out

    # tools
    def tool_invoke(self, tool: str, payload: dict, scopes: list[str]):
        return self.tools.invoke(tool, payload, scopes)

    # routing suggestions
    def routing_suggestions(self, query: str = ""):
        caps = [c for c in self.store.get_capsules() if c.profile_id == self.active_profile_id]
        suggestions = []
        for c in caps[-20:]:
            if c.kind == CapsuleKind.standard and ("prefer" in c.text.lower() or "goal" in c.text.lower()):
                suggestions.append({"capsule_id": c.id, "suggestion": "identity_candidate", "reason": "contains preference/goal-like language"})
            if c.kind == CapsuleKind.standard and c.workspace_ids:
                suggestions.append({"capsule_id": c.id, "suggestion": "project_candidate", "reason": "workspace association present"})
        if query:
            suggestions.append({"query": query, "suggestion": "workspace_route", "reason": "query-driven workspace routing preview"})
        return suggestions[:30]


    # v0.8 ecosystem stability
    def compatibility(self):
        return compatibility_report(self.plugin_list(), self.connector_list(), self.app_list())

    def get_feature_flags(self):
        return dict(self._feature_flags)

    def modules_catalog(self):
        if not self.module_catalog:
            self.module_catalog = [
                {"id": "plug-a", "type": "plugin", "channel": "stable", "source": "internal", "signed": True, "version": "1.0.0", "changelog": ["initial release"], "review_state": "pending"},
                {"id": "connector-folder", "type": "connector", "channel": "stable", "source": "internal", "signed": True, "version": "1.0.0", "changelog": ["folder ingest support"], "review_state": "approved"},
                {"id": "workflow-template-basic", "type": "workflow", "channel": "experimental", "source": "internal", "signed": False, "version": "0.3.0", "changelog": ["staged rollout"], "review_state": "pending"},
            ]
        return self.module_catalog

    def module_review(self, module_id: str, decision: str, note: str = ""):
        for m in self.modules_catalog():
            if m["id"] == module_id:
                m["review_state"] = decision
                m["review_note"] = note
                self._audit("module_review", {"module_id": module_id, "decision": decision})
                return m
        return {"status": "missing"}

    # policy intelligence
    def policy_templates(self):
        return POLICY_TEMPLATES

    def policy_simulate(self, action: str, context: dict, template_name: str = "strict_private"):
        out = simulate_policy(action, context, template_name)
        self._audit("policy_simulate", {"action": action, "allowed": out["allowed"]})
        return out

    def policy_effective(self, context: dict, template_name: str = "strict_private"):
        return effective_policy(context, template_name)

    # reports
    def report_operational(self):
        return operational_report(self)

    def report_memory_quality(self):
        return memory_quality_report(self)

    # upgrade/migration
    def upgrade_preview(self, target_version: str = "1.0.0"):
        out = upgrade_preview(self, target_version)
        self._audit("upgrade_preview", out)
        return out

    def upgrade_apply(self, target_version: str = "1.0.0"):
        out = upgrade_apply(self, target_version)
        self._audit("upgrade_apply", out)
        return out

    # onboarding templates/governance
    def onboarding_templates(self):
        return onboarding_templates()

    def governance_review(self):
        quality = self.report_memory_quality()
        policy_checks = self.policy_simulate("export", {"is_private": True})
        return {
            "quality": quality,
            "policy_simulation": policy_checks,
            "pending_approvals": [a for a in self.list_approvals() if a.get("status") == "pending"],
            "compatibility": self.compatibility(),
        }


    # GA hardening summaries
    def limitations(self):
        return [
            {"id": "no_remote_kms", "severity": "non_blocker", "detail": "Remote KMS integration intentionally out of scope for local-first default."},
            {"id": "optional_network_connectors", "severity": "non_blocker", "detail": "Network connectors remain disabled by default in GA."},
            {"id": "experimental_module_channels", "severity": "non_blocker", "detail": "Beta/experimental channels require explicit module review."},
        ]

    def warnings(self):
        items = []
        comp = self.compatibility()
        for i in comp.get("issues", []):
            items.append({"severity": "warning", "category": i.get("type"), "message": i.get("issue"), "id": i.get("id")})
        for d in comp.get("deprecations", []):
            items.append({"severity": d.get("severity", "warning"), "category": "deprecation", "message": d.get("message"), "id": d.get("id")})
        return items

    def needs_attention(self):
        warn = self.warnings()
        governance = self.governance_review()
        return {
            "warnings": warn[:20],
            "governance_review_needed": governance.get("quality", {}).get("governance_review_needed", 0),
            "pending_approvals": len(governance.get("pending_approvals", [])),
        }

    def runtime_health(self):
        return {
            "version": "1.0.0",
            "runtime": self.runtime_status(),
            "compatibility": self.compatibility().get("healthy", False),
            "queue": {"total": len(self.list_jobs()), "queued": sum(1 for j in self.list_jobs() if j.get("status") == "queued")},
            "sync_health": {"pending": sum(1 for s in self.store.get_sync_sessions() if s.status == "preview")},
            "migration_readiness": self.upgrade_preview("1.0.0").get("safe_to_apply", False),
        }

    def compatibility_summary(self):
        c = self.compatibility()
        return {"healthy": c.get("healthy"), "issue_count": len(c.get("issues", [])), "deprecations": c.get("deprecations", [])}

    def migration_validate(self, target_version: str = "1.0.0"):
        return self.upgrade_preview(target_version)

    def release_validation(self):
        return release_validation(self)

    def release_readiness(self):
        return release_readiness(self)

    def performance_baseline(self):
        return performance_baseline(self)
