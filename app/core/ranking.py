from __future__ import annotations

from datetime import datetime, timezone

from app.memory.models import Capsule, CapsuleKind

WEIGHTS = {
    "semantic": 0.24,
    "graph": 0.08,
    "recency": 0.07,
    "importance": 0.1,
    "trust": 0.08,
    "identity_relevance": 0.1,
    "workspace_relevance": 0.1,
    "session_relevance": 0.08,
    "sync_provenance_confidence": 0.07,
    "duplicate_penalty": -0.05,
    "policy_allowance": 0.13,
}


def recency_score(c: Capsule) -> float:
    d = (datetime.now(timezone.utc) - c.updated_at).total_seconds() / 86400
    return max(0.0, 1 - d / 30)


def identity_relevance(c: Capsule, q: str) -> float:
    if c.kind != CapsuleKind.identity:
        return 0.0
    return 0.7 if any(tok in c.text.lower() for tok in q.lower().split()) else 0.0


def workspace_relevance(c: Capsule, context: dict) -> float:
    ws = context.get("workspace_id")
    return 1.0 if ws and ws in c.workspace_ids else 0.0


def session_relevance(c: Capsule, context: dict) -> float:
    sid = context.get("session_id")
    return 1.0 if sid and c.metadata.get("session_id") == sid else 0.0


def sync_provenance_confidence(c: Capsule) -> float:
    return 0.6 if c.sync_state != "local" else 1.0


def duplicate_penalty(c: Capsule, seen: set[str]) -> float:
    key = c.summary.lower().strip()
    if key in seen:
        return 1.0
    seen.add(key)
    return 0.0
