"""Φ Memory Polyglot R2: bounded, in-process consumer handoffs.

The R1 gateway authenticates an operator-approved capability *before* this
module sees a projection. A returned envelope is not signed, encrypted, or
safe to trust after being copied out of that trusted process. No I/O here.
"""
from __future__ import annotations

import re
from typing import Any

from app.memory.polyglot_gateway import LocalCapabilityGateway

SCHEMA = "phi.memory.polyglot.consumer.r2"
EVIDENCE = "source_claim_not_independently_verified"
RETENTION = "ephemeral_preview_only"
_LIMITS = {"pocketbrain": 1024, "brainc": 4096}
_DENIED = "memory polyglot: unsupported consumer"


def _clip(value: str, limit: int) -> tuple[str, bool]:
    if not isinstance(value, str):
        raise ValueError("invalid memory field")
    return value[:limit], len(value) > limit


def _labels(value: Any) -> tuple[list[str], bool]:
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ValueError("invalid memory labels")
    labels = [x[:64] for x in value[:8]]
    cropped = len(value) > 8 or any(len(x) > 64 for x in value[:8])
    return labels, cropped


def create_consumer_handoff(
    gateway: LocalCapabilityGateway, *, token: str, reader: str,
    now: int | None = None,
) -> dict[str, Any]:
    """Redeem *one* R1 token, then return a bounded, read-only context envelope.

    This function is intended only for the trusted local operator process.
    Do not serialize its result to public files, logs, APIs or browser storage.
    """
    if reader not in _LIMITS:
        raise PermissionError(_DENIED)
    projection = gateway.read(token=token, reader=reader, now=now)
    if (
        projection.get("schema") != "phi.memory.polyglot.r0"
        or projection.get("reader") != reader
        or projection.get("evidence_status") != EVIDENCE
        or not isinstance(projection.get("capsule_id"), str)
        or not projection["capsule_id"]
        or not isinstance(projection.get("source_sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", projection["source_sha256"]) is None
        or not isinstance(projection.get("view"), dict)
    ):
        raise ValueError("unexpected R0 projection")

    view = projection["view"]
    expected = "compact_context" if reader == "pocketbrain" else "semantic_context"
    if view.get("kind") != expected:
        raise ValueError("wrong projection kind")
    text, text_cropped = _clip(view.get("text"), _LIMITS[reader])
    if not text.strip():
        raise ValueError("empty consumer context")
    tags, tags_cropped = _labels(view.get("tags", []))
    payload: dict[str, Any] = {
        "kind": expected,
        "text": text,
        "tags": tags,
        "truncated": text_cropped or tags_cropped,
    }
    if reader == "brainc":
        summary, summary_cropped = _clip(view.get("summary", ""), 512)
        entities, entities_cropped = _labels(view.get("entities", []))
        payload.update(summary=summary, entities=entities)
        payload["truncated"] = payload["truncated"] or summary_cropped or entities_cropped

    return {
        "schema": SCHEMA,
        "reader": reader,
        "capsule_id": projection["capsule_id"],
        "source_sha256": projection["source_sha256"],
        "evidence_status": EVIDENCE,
        "retention": RETENTION,
        "payload": payload,
    }
