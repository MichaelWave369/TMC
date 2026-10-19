"""Circle-Back R3: read-only local project/action reconciliation.

No model inference, background processing, private-record enumeration,
automated scheduling, or independent proof is produced by this module.
"""
from __future__ import annotations

from collections import Counter

NEXT_STEPS = {
    "evidence_recheck_required": "Review changed or inaccessible local evidence and make a new decision",
    "operator_decision_needed": "Approve or reject an existing proposal after reviewing its sources",
    "approved_followup_needed": "Check approved work and record evidence if you later attest completion",
    "memory_review_needed": "Review uncertain or conflicting visible memory before making a decision",
    "attach_source_review": "Attach a non-sensitive visible source before deciding the next step",
    "stale_context_review": "Review whether the old visible context still applies",
    "operator_attested_not_verified": "Revisit an operator-attested action if independent confirmation is needed",
    "general_project_review": "Review this project and decide whether a new action is appropriate",
}


def _priority(signal: str, actions: list[dict]) -> tuple[int, str]:
    active = [a for a in actions if a["status"] != "rejected"]
    if any(a["evidence_review"] == "operator_recheck_required" for a in active):
        return 0, "evidence_recheck_required"
    if any(a["status"] == "proposed" for a in active):
        return 1, "operator_decision_needed"
    if any(a["status"] == "approved" for a in active):
        return 2, "approved_followup_needed"
    if signal == "review_uncertain_sources":
        return 3, "memory_review_needed"
    if signal == "needs_visible_evidence":
        return 4, "attach_source_review"
    if signal == "stale_context":
        return 5, "stale_context_review"
    if any(a["status"] == "operator_attested" for a in active):
        return 7, "operator_attested_not_verified"
    return 6, "general_project_review"


def build_review_board(
    *, preview: dict, actions_by_project: dict[tuple[str, str], list[dict]],
    limit: int,
) -> dict:
    """Rank existing project cards by operator review need.

    The input project preview is already active-profile and policy filtered;
    caller supplies only action status and aggregate drift results. Source
    text, action titles, operator notes and individual evidence pointers are
    intentionally not copied into board cards.
    """
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    cards = []
    for p in preview["cards"]:
        actions = sorted(
            actions_by_project.get((p["project_id"], p["workspace_id"]), []),
            key=lambda a: (a["updated_at"], a["action_id"]), reverse=True,
        )
        rank, signal = _priority(p["signal"], actions)
        cards.append({
            "project_id": p["project_id"],
            "workspace_id": p["workspace_id"],
            "project_name": p["project_name"],
            "review_signal": signal,
            "suggested_operator_step": NEXT_STEPS[signal],
            "underlying_memory_signal": p["signal"],
            "days_since_visible_activity": p["days_since_visible_activity"],
            "last_visible_activity": p["last_visible_activity"],
            "visible_evidence_count": p["visible_evidence_count"],
            "uncertain_visible_record_count": p["review_record_count"],
            "operator_action_count": len(actions),
            "operator_actions": actions[:8],
            "operator_actions_truncated": len(actions) > 8,
            "completion_status": "not_independently_verified",
            "_rank": rank,
        })
    cards.sort(key=lambda c: (
        c["_rank"], -c["days_since_visible_activity"],
        c["project_name"].casefold(), c["project_id"],
    ))
    for c in cards:
        del c["_rank"]
    counts = Counter(c["review_signal"] for c in cards)
    considered = len(preview["cards"])
    return {
        "profile_id": preview["profile_id"],
        "generated_at": preview["generated_at"],
        "mode": "local_read_only_review_board",
        "auto_actions": False,
        "independent_verification": False,
        "total_projects": preview["total_projects"],
        "projects_considered": considered,
        "coverage_complete": considered == preview["total_projects"],
        "signals_in_considered_projects": dict(sorted(counts.items())),
        "cards": cards[:limit],
        "cards_truncated": len(cards) > limit,
    }
