"""Read-only Φ Memory Polyglot R0: one TMC capsule, three governed projections.

This module is an offline contract experiment, NOT an authentication gateway.
All ReaderGrant records must be supplied by a trusted, authenticated local caller.
Never route untrusted traffic directly to this function or expose raw capsules.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from app.memory.models import Capsule, CapsuleStatus, PolicyMode

SCHEMA = "phi.memory.polyglot.r0"
READERS = frozenset({"pocketbrain", "brainc", "sml"})
_DENIED = "memory polyglot: access denied"


@dataclass(frozen=True, slots=True)
class ReaderGrant:
    """Out-of-band operator decision, not a credential or proof of identity."""

    reader: str
    profile_id: str
    vault_id: str
    workspace_ids: frozenset[str]


def source_fingerprint(capsule: Capsule) -> str:
    """Deterministic change indicator, not a signature or authenticity proof."""
    canonical = json.dumps(
        capsule.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def project_capsule(
    capsule: Capsule, *, reader: str, grant: ReaderGrant | None
) -> dict[str, Any]:
    """Derive one read-only view, with scope checks before any content projection.

    R0 is intentionally stricter than TMC's full policy engine: only active,
    persistent, locally held, explicitly workspace-scoped capsules are eligible.
    No session, private, ephemeral, locked, or pending memories are exported.
    """
    if (
        grant is None
        or reader not in READERS
        or grant.reader != reader
        or not grant.profile_id
        or not grant.vault_id
        or not grant.workspace_ids
        or not capsule.workspace_ids
        or capsule.profile_id != grant.profile_id
        or capsule.vault_id != grant.vault_id
        or not set(capsule.workspace_ids).issubset(grant.workspace_ids)
        or capsule.policy != PolicyMode.persistent
        or capsule.status != CapsuleStatus.active
        or capsule.sync_state != "local"
        or not capsule.source_type
        or not capsule.source_ref
    ):
        raise PermissionError(_DENIED)

    fingerprint = source_fingerprint(capsule)
    if reader == "pocketbrain":
        view: dict[str, Any] = {
            "kind": "compact_context",
            "text": capsule.summary or capsule.text[:160],
            "tags": list(capsule.tags),
        }
    elif reader == "brainc":
        view = {
            "kind": "semantic_context",
            "text": capsule.text,
            "summary": capsule.summary,
            "tags": list(capsule.tags),
            "entities": list(capsule.entities),
            "related_capsule_ids": list(capsule.related_capsule_ids),
        }
    else:
        # SML MemoryPacket-compatible *candidate* fields. Deliberately shadow
        # state, never verified, approved, persisted, or made executable here.
        view = {
            "kind": "governance_candidate",
            "candidate": {
                "payload": capsule.text,
                "author_agent_id": "tmc-polyglot-r0",
                "state": "shadow",
                "collab_state": "local_only",
                "intent_tags": list(capsule.tags),
                "parent_ids": [capsule.id],
            },
            "source": {
                "type": capsule.source_type,
                "ref": capsule.source_ref,
                "provenance": list(capsule.provenance),
            },
            "disposition": "review_only_unverified",
        }

    return {
        "schema": SCHEMA,
        "reader": reader,
        "capsule_id": capsule.id,
        "source_sha256": fingerprint,
        "evidence_status": "source_claim_not_independently_verified",
        "view": view,
    }
