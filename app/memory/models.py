"""TMC v0.5 models for sovereign vaults, sync, profiles and agent runtime."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class PolicyMode(str, Enum):
    persistent = "persistent"
    session = "session"
    ephemeral = "ephemeral"
    locked = "locked"
    private_local_only = "private_local_only"


class CapsuleStatus(str, Enum):
    active = "active"
    archived = "archived"
    superseded = "superseded"
    conflicting = "conflicting"
    uncertain = "uncertain"
    pending_review = "pending_review"


class CapsuleKind(str, Enum):
    standard = "standard"
    identity = "identity"
    project = "project"
    summary_bridge = "summary_bridge"
    session = "session"


class VaultStatus(str, Enum):
    locked = "locked"
    unlocked = "unlocked"


class ApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class TrustStatus(str, Enum):
    pending = "pending"
    trusted = "trusted"
    blocked = "blocked"


class Capsule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_type: str
    source_ref: str
    text: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    importance: float = 0.5
    trust: float = 0.5
    decay_class: str = "normal"
    policy: PolicyMode = PolicyMode.persistent
    status: CapsuleStatus = CapsuleStatus.active
    kind: CapsuleKind = CapsuleKind.standard
    profile_id: str = "default"
    workspace_ids: list[str] = Field(default_factory=list)
    vault_id: str = "vault-default"
    device_id: str = "device-local"
    sync_state: str = "local"
    pinned: bool = False
    retention_weight: float = 1.0
    related_capsule_ids: list[str] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    profile_id: str = "default"
    workspace_id: str
    name: str
    description: str = ""
    rollup_summary: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NextActionStatus(str, Enum):
    proposed = "proposed"
    approved = "approved"
    rejected = "rejected"
    operator_attested = "operator_attested"


class NextAction(BaseModel):
    id: str = Field(default_factory=lambda: f"next-{uuid4()}")
    profile_id: str
    project_id: str
    workspace_id: str
    title: str
    rationale: str = ""
    source_capsule_ids: list[str] = Field(default_factory=list)
    completion_evidence_ids: list[str] = Field(default_factory=list)
    status: NextActionStatus = NextActionStatus.proposed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NextActionEvent(BaseModel):
    id: str = Field(default_factory=lambda: f"next-event-{uuid4()}")
    action_id: str
    profile_id: str
    transition: str
    operator_note: str = ""
    evidence_capsule_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Attachment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    capsule_ids: list[str] = Field(default_factory=list)
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    attachment_type: str = "generic"
    extraction_status: str = "pending"
    extraction_text: str = ""
    local_path: str
    vault_id: str = "vault-default"
    sync_allowed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConflictRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    capsule_a: str
    capsule_b: str
    conflict_type: str
    confidence: float
    note: str
    resolution: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Vault(BaseModel):
    vault_id: str = Field(default_factory=lambda: f"vault-{uuid4()}")
    display_name: str
    owner_label: str = "Local Operator"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    encryption_mode: str = "passphrase-kdf-xor"
    key_derivation_metadata: dict[str, Any] = Field(default_factory=dict)
    status: VaultStatus = VaultStatus.locked
    storage_path: str = "data/vaults/default"


class Profile(BaseModel):
    profile_id: str = Field(default_factory=lambda: f"profile-{uuid4()}")
    display_name: str
    default_vault_id: str = "vault-default"
    default_policy_profile: str = "strict"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeviceIdentity(BaseModel):
    device_id: str = Field(default_factory=lambda: f"device-{uuid4()}")
    device_name: str
    trust_status: TrustStatus = TrustStatus.pending
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    public_key: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SyncSession(BaseModel):
    id: str = Field(default_factory=lambda: f"sync-{uuid4()}")
    source_device_id: str
    target_device_id: str
    profile_id: str
    preview_payload: dict[str, Any] = Field(default_factory=dict)
    status: str = "preview"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Snapshot(BaseModel):
    id: str = Field(default_factory=lambda: f"snap-{uuid4()}")
    vault_id: str
    profile_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload_path: str
    checksum: str


class AuditLog(BaseModel):
    id: str = Field(default_factory=lambda: f"audit-{uuid4()}")
    action: str
    actor: str = "operator"
    note: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalItem(BaseModel):
    id: str = Field(default_factory=lambda: f"approval-{uuid4()}")
    action_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.pending
    note: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentSession(BaseModel):
    id: str = Field(default_factory=lambda: f"agent-session-{uuid4()}")
    profile_id: str
    workspace_id: str
    task: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    messages: list[dict[str, str]] = Field(default_factory=list)


class IngestRequest(BaseModel):
    source_type: str
    source_ref: str
    text: str
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    importance: float = 0.5
    trust: float = 0.5
    decay_class: str = "normal"
    policy: PolicyMode = PolicyMode.persistent
    profile_id: str = "default"
    workspace_ids: list[str] = Field(default_factory=list)
    vault_id: str = "vault-default"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    capsule: Capsule
    final_score: float
    breakdown: dict[str, float]
    policy_reason: str
    selected_why: str = ""
    source_device: str = "device-local"
    synced_provenance_influence: bool = False
    suppressed_count: int = 0
