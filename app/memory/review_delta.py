"""Circle-Back R5: compact, local-only review snapshots and cautious deltas.

Snapshot records contain project names and local action identifiers, so they
are PRIVATE OPERATOR DATA. No raw capsule content, source IDs, operator notes,
cryptographic digests, external claims, or automated actions are exported.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

FORMAT = "tmc.circle_back.snapshot.v1"
MAX_PROJECTS = 100
MAX_ACTIONS = 8
ALLOWED_REVIEW_SIGNALS = {
    "evidence_recheck_required", "operator_decision_needed",
    "approved_followup_needed", "memory_review_needed",
    "attach_source_review", "stale_context_review",
    "operator_attested_not_verified", "general_project_review",
}
ALLOWED_ACTION_STATUSES = {"proposed", "approved", "rejected", "operator_attested"}
ALLOWED_EVIDENCE_REVIEWS = {
    "operator_recheck_required", "consistent_with_local_snapshot",
    "no_evidence_snapshot",
}
ACTION_FIELDS = ("action_id", "status", "evidence_review")
PROJECT_FIELDS = (
    "project_id", "workspace_id", "project_name", "review_signal",
    "visible_evidence_count", "uncertain_visible_record_count",
    "operator_action_count", "operator_actions_truncated", "operator_actions",
)


def _integer(value: Any, field: str, *, upper: int = 1000000) -> int:
    if type(value) is not int or not 0 <= value <= upper:
        raise ValueError(f"Invalid non-negative count: {field}")
    return value


def _name(value: Any, field: str, *, max_length: int = 300) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise ValueError(f"Invalid {field}")
    return value


def _timestamp(value: Any) -> datetime:
    string = _name(value, "timestamp", max_length=48)
    try:
        result = datetime.fromisoformat(string.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid snapshot timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Snapshot timestamp requires an offset")
    return result


def _check_snapshot(snapshot: dict) -> None:
    if not isinstance(snapshot, dict) or snapshot.get("format") != FORMAT:
        raise ValueError("Unsupported Circle-Back snapshot format")
    if snapshot.get("automatic_actions") is not False:
        raise ValueError("Snapshots cannot claim automatic actions")
    if snapshot.get("independently_verified") is not False:
        raise ValueError("Snapshots cannot claim independently verified work")
    _name(snapshot.get("profile_id"), "profile_id")
    _timestamp(snapshot.get("generated_at"))
    total = _integer(snapshot.get("total_projects"), "total_projects")
    considered = _integer(snapshot.get("projects_considered"), "projects_considered", upper=MAX_PROJECTS)
    complete = snapshot.get("coverage_complete")
    truncated = snapshot.get("cards_truncated")
    if type(complete) is not bool or type(truncated) is not bool or considered > total:
        raise ValueError("Invalid snapshot coverage flags")
    if complete != (total == considered):
        raise ValueError("Coverage flag contradicts project counts")
    rows = snapshot.get("projects")
    if not isinstance(rows, list) or len(rows) > MAX_PROJECTS or len(rows) > considered:
        raise ValueError("Invalid bounded snapshot project list")
    if truncated != (len(rows) < considered):
        raise ValueError("Card truncation flag contradicts included projects")
    seen = set()
    for project in rows:
        if not isinstance(project, dict):
            raise ValueError("Malformed snapshot project")
        for field in ("project_id", "workspace_id", "project_name", "review_signal"):
            _name(project.get(field), field)
        if project["review_signal"] not in ALLOWED_REVIEW_SIGNALS:
            raise ValueError("Unsupported review signal")
        pid = project["project_id"]
        if pid in seen:
            raise ValueError("Duplicate project ID in snapshot")
        seen.add(pid)
        _integer(project.get("visible_evidence_count"), "visible_evidence_count")
        _integer(project.get("uncertain_visible_record_count"), "uncertain_visible_record_count")
        action_total = _integer(project.get("operator_action_count"), "operator_action_count")
        clipped = project.get("operator_actions_truncated")
        actions = project.get("operator_actions")
        if type(clipped) is not bool or not isinstance(actions, list):
            raise ValueError("Invalid action coverage")
        if len(actions) > MAX_ACTIONS or len(actions) > action_total:
            raise ValueError("Action preview is not bounded")
        if clipped != (len(actions) < action_total):
            raise ValueError("Action truncation flag contradicts included actions")
        aids = set()
        for action in actions:
            if not isinstance(action, dict):
                raise ValueError("Malformed action")
            for field in ACTION_FIELDS:
                _name(action.get(field), field)
            if action["status"] not in ALLOWED_ACTION_STATUSES:
                raise ValueError("Unsupported action status")
            if action["evidence_review"] not in ALLOWED_EVIDENCE_REVIEWS:
                raise ValueError("Unsupported evidence review state")
            if action["action_id"] in aids:
                raise ValueError("Duplicate action ID in project")
            aids.add(action["action_id"])


def snapshot_from_review_board(board: dict) -> dict:
    """Whitelist R3 board fields, dropping all extras before saving locally."""
    if not isinstance(board, dict) or board.get("mode") != "local_read_only_review_board":
        raise ValueError("Expected a local read-only review board")
    if board.get("auto_actions") is not False or board.get("independent_verification") is not False:
        raise ValueError("Cannot snapshot automated or verified claims")
    cards = board.get("cards")
    if not isinstance(cards, list) or len(cards) > MAX_PROJECTS:
        raise ValueError("Review board cards are not bounded")
    result = {
        "format": FORMAT,
        "profile_id": board.get("profile_id"),
        "generated_at": board.get("generated_at"),
        "automatic_actions": False,
        "independently_verified": False,
        "total_projects": board.get("total_projects"),
        "projects_considered": board.get("projects_considered"),
        "coverage_complete": board.get("coverage_complete"),
        "cards_truncated": board.get("cards_truncated"),
        "projects": [],
    }
    for card in cards:
        if not isinstance(card, dict):
            raise ValueError("Malformed board card")
        row = {field: card.get(field) for field in PROJECT_FIELDS if field != "operator_actions"}
        actions = card.get("operator_actions")
        if not isinstance(actions, list):
            raise ValueError("Malformed action preview")
        row["operator_actions"] = [
            {field: a.get(field) for field in ACTION_FIELDS} for a in actions
            if isinstance(a, dict)
        ]
        if len(row["operator_actions"]) != len(actions):
            raise ValueError("Malformed action preview item")
        result["projects"].append(row)
    _check_snapshot(result)
    return result


def compare_review_snapshots(before: dict, after: dict) -> dict:
    """Compare two same-profile local snapshots, not real-world truth.

    New/missing project observations are suppressed if either project view
    is truncated or incomplete. Per-action comparisons are suppressed when
    either snapshot truncated the action list for the relevant project.
    """
    _check_snapshot(before)
    _check_snapshot(after)
    if before["profile_id"] != after["profile_id"]:
        raise ValueError("Cannot compare different profiles")
    if _timestamp(after["generated_at"]) < _timestamp(before["generated_at"]):
        raise ValueError("Comparison snapshots are out of chronological order")

    prev = {p["project_id"]: p for p in before["projects"]}
    curr = {p["project_id"]: p for p in after["projects"]}
    full_project_view = all(
        s["coverage_complete"] and not s["cards_truncated"]
        for s in (before, after)
    )
    changes = []
    for pid in sorted(prev.keys() & curr.keys()):
        a, b = prev[pid], curr[pid]
        fields = (
            "project_name", "review_signal", "visible_evidence_count",
            "uncertain_visible_record_count", "operator_action_count",
        )
        changed = {key: {"before": a[key], "after": b[key]}
                   for key in fields if a[key] != b[key]}
        # Distinct workspace IDs under one project ID are treated as a scope
        # inconsistency, not as comparable historical state.
        if a["workspace_id"] != b["workspace_id"]:
            raise ValueError("Project workspace scope changed between snapshots")

        actions_comparable = not (
            a["operator_actions_truncated"] or b["operator_actions_truncated"]
        )
        action_changes = []
        if actions_comparable:
            old_actions = {x["action_id"]: x for x in a["operator_actions"]}
            new_actions = {x["action_id"]: x for x in b["operator_actions"]}
            for aid in sorted(old_actions.keys() & new_actions.keys()):
                old, new = old_actions[aid], new_actions[aid]
                action_diff = {f: {"before": old[f], "after": new[f]}
                               for f in ("status", "evidence_review")
                               if old[f] != new[f]}
                if action_diff:
                    action_changes.append({"action_id": aid, "changes": action_diff})
            for aid in sorted(new_actions.keys() - old_actions.keys()):
                action_changes.append({"action_id": aid, "observation": "newly_listed"})
            for aid in sorted(old_actions.keys() - new_actions.keys()):
                action_changes.append({"action_id": aid, "observation": "no_longer_listed"})
        if changed or action_changes or not actions_comparable:
            changes.append({
                "project_id": pid,
                "project_name": b["project_name"],
                "changes": changed,
                "action_changes": action_changes,
                "action_comparison": (
                    "complete_for_listed_actions" if actions_comparable
                    else "suppressed_due_to_action_preview_limit"
                ),
            })
    return {
        "format": "tmc.circle_back.delta.v1",
        "profile_id": before["profile_id"],
        "before_generated_at": before["generated_at"],
        "after_generated_at": after["generated_at"],
        "automatic_actions": False,
        "independently_verified": False,
        "project_entry_exit_comparison": (
            "complete_for_visible_profile" if full_project_view
            else "suppressed_due_to_incomplete_project_coverage"
        ),
        "newly_listed_projects": sorted(curr.keys() - prev.keys()) if full_project_view else [],
        "no_longer_listed_projects": sorted(prev.keys() - curr.keys()) if full_project_view else [],
        "compared_projects": len(prev.keys() & curr.keys()),
        "projects_with_observed_changes_or_limited_actions": len(changes),
        "project_deltas": changes,
        "interpretation": (
            "Changes describe locally stored review state and visibility, "
            "not independently verified progress, resolution, or deletion."
        ),
    }
