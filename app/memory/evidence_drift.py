"""Read-only content change indicators for stored TMC capsule records.

Digests indicate ordinary record edits only. They are not signed, tamper-proof,
or independent proof of factual accuracy, authorization, or completion.
"""
from __future__ import annotations

import hashlib
import json

from app.memory.models import Capsule


def snapshot_capsule(capsule: Capsule) -> str:
    payload = capsule.model_dump(mode="json")
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def snapshot_status(
    references: list[str],
    stored: dict[str, str],
    current_visible: dict[str, str],
) -> str:
    """Return only aggregated states, not inaccessible reference details."""
    if not references:
        return "not_applicable"
    if any(cid not in current_visible for cid in references):
        return "attention_required"
    if any(cid not in stored for cid in references):
        return "snapshot_unavailable"
    if any(current_visible[cid] != stored[cid] for cid in references):
        return "attention_required"
    return "unchanged_since_snapshot"
