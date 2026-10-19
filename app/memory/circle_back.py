"""Deterministic, read-only Circle-Back recommendations from existing TMC memory.

This module does not infer task completion, verify the truth of memories, invoke
models, write to storage, perform sync, or bypass retrieval policies.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.memory.models import Capsule, CapsuleStatus, PolicyMode, ProjectRecord
from app.memory.policies import PolicyEngine

REVIEW_STATUSES = {
    CapsuleStatus.conflicting,
    CapsuleStatus.uncertain,
    CapsuleStatus.pending_review,
}
IGNORED_STATUSES = {CapsuleStatus.archived, CapsuleStatus.superseded}


def circle_back_snapshot(
    *,
    projects: list[ProjectRecord],
    capsules: list[Capsule],
    active_profile_id: str,
    unlocked_vault_ids: set[str],
    policy: PolicyEngine,
    as_of: datetime | None = None,
    limit: int = 20,
    stale_days: int = 30,
) -> dict:
    """Return traceable, operator-review-only cards for an active local profile.

    Deliberately conservative: v0 uses persistent, non-private capsules only.
    It never returns raw memory text, source paths or hidden-record counts.
    Source capsule IDs are lookup hints, not cryptographic receipts.
    """
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    if type(stale_days) is not int or not 1 <= stale_days <= 3650:
        raise ValueError("stale_days must be an integer between 1 and 3650")

    now = as_of if as_of is not None else datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("as_of must be a timezone-aware datetime")
    now = now.astimezone(timezone.utc)

    visible: list[Capsule] = []
    context = {"profile_id": active_profile_id, "allow_private": False}
    for c in capsules:
        if c.profile_id != active_profile_id:
            continue
        if c.policy != PolicyMode.persistent:
            continue
        if c.status in IGNORED_STATUSES:
            continue
        if c.vault_id not in unlocked_vault_ids:
            continue
        allowed, _reason = policy.allow_retrieval(c, context)
        if allowed:
            visible.append(c)

    candidates = []
    for p in projects:
        if p.profile_id != active_profile_id:
            continue
        linked = [c for c in visible if p.workspace_id in c.workspace_ids]
        linked.sort(key=lambda c: (c.updated_at, c.id), reverse=True)
        reviews = sum(1 for c in linked if c.status in REVIEW_STATUSES)
        last = max([p.updated_at, *(c.updated_at for c in linked)])
        age_days = max(0, (now - last.astimezone(timezone.utc)).days)

        if reviews:
            signal, weight, action = (
                "review_uncertain_sources", 4,
                "Review conflicting or uncertain memory records before choosing a next task",
            )
            reasons = ["linked_records_need_review"]
        elif not linked:
            signal, weight, action = (
                "needs_visible_evidence", 3,
                "Attach a non-sensitive source record and capture a concrete next action",
            )
            reasons = ["no_policy_visible_linked_records"]
        elif age_days >= stale_days:
            signal, weight, action = (
                "stale_context", 2,
                "Recheck the latest source and decide whether the project still needs attention",
            )
            reasons = ["last_visible_activity_is_old"]
        else:
            signal, weight, action = (
                "ready_for_operator_review", 1,
                "Review linked records and choose the next action yourself",
            )
            reasons = ["policy_visible_records_available"]

        candidates.append({
            "project_id": p.id,
            "workspace_id": p.workspace_id,
            "project_name": p.name,
            "signal": signal,
            "reasons": reasons,
            "suggested_next_step": action,
            "visible_evidence_count": len(linked),
            "review_record_count": reviews,
            "last_visible_activity": last.isoformat(),
            "days_since_visible_activity": age_days,
            "source_capsule_ids": [c.id for c in linked[:5]],
            "provenance_assessment": "stored_memory_not_independently_verified",
            "completion_status": "not_assessed",
            "_priority": weight,
        })

    candidates.sort(key=lambda x: (
        -x["_priority"],
        -x["days_since_visible_activity"],
        x["project_name"].casefold(),
        x["project_id"],
    ))
    for c in candidates:
        del c["_priority"]

    return {
        "profile_id": active_profile_id,
        "generated_at": now.isoformat(),
        "mode": "local_read_only_suggestions",
        "auto_actions": False,
        "claim_of_verification": False,
        "total_projects": len(candidates),
        "cards": candidates[:limit],
    }
