"""R8: read-only, profile-scoped Focus Session summaries for the offline board.

These summaries deliberately exclude review intent, notes, action links,
session history and evidence. The format is separate from R5/R6 snapshots.
No mutations, network operations, model inference or verification claims.
"""
from __future__ import annotations

from app.memory.models import FocusSession, FocusSessionStatus

FOCUS_FORMAT = "local_read_only_focus_overlay"
MAX_RECENT = 3
ALLOWED_DECISIONS = {"revisit_later", "needs_evidence", "next_action_identified"}


def build_focus_overlay(*, board: dict, sessions: list[FocusSession], profile_id: str) -> dict:
    """Aggregate only projects actually DISPLAYED in this profile's board."""
    if (
        not isinstance(board, dict)
        or board.get("mode") != "local_read_only_review_board"
        or board.get("profile_id") != profile_id
        or board.get("auto_actions") is not False
        or board.get("independent_verification") is not False
    ):
        raise ValueError("Board does not match the active local operator profile")
    cards = board.get("cards")
    if not isinstance(cards, list) or len(cards) > 100:
        raise ValueError("Invalid bounded review board cards")
    scopes = []
    for card in cards:
        if not isinstance(card, dict):
            raise ValueError("Invalid review board card")
        key = (card.get("project_id"), card.get("workspace_id"))
        if not all(isinstance(v, str) and v for v in key) or key in scopes:
            raise ValueError("Invalid or duplicate displayed project scope")
        scopes.append(key)
    groups = {key: [] for key in scopes}
    for session in sessions:
        if session.profile_id != profile_id:
            continue
        key = (session.project_id, session.workspace_id)
        if key in groups:
            groups[key].append(session)
    output = []
    for pid, workspace in scopes:
        rows = sorted(
            groups[(pid, workspace)],
            key=lambda s: (s.started_at, s.id), reverse=True,
        )
        visible = []
        for s in rows[:MAX_RECENT]:
            # This is NOT a source of verified completion. Closed focus merely
            # means an operator finished a review, never the underlying work.
            visible.append({
                "session_id": s.id,
                "status": s.status.value,
                "decision": s.decision.value if s.decision is not None else None,
                "started_at": s.started_at.isoformat(),
                "closed_at": s.closed_at.isoformat() if s.closed_at else None,
            })
        output.append({
            "project_id": pid,
            "workspace_id": workspace,
            "total_sessions": len(rows),
            "sessions_truncated": len(rows) > MAX_RECENT,
            "recent_sessions": visible,
        })
    return {
        "format": FOCUS_FORMAT,
        "profile_id": profile_id,
        "automatic_actions": False,
        "completion_verified": False,
        "projects": output,
    }


def checked_focus_overlay(board: dict, overlay: dict) -> dict[tuple[str, str], dict]:
    """Fail closed on unrelated/invalid overlays, with no untrusted HTML fields."""
    if (
        not isinstance(overlay, dict)
        or overlay.get("format") != FOCUS_FORMAT
        or overlay.get("profile_id") != board.get("profile_id")
        or overlay.get("automatic_actions") is not False
        or overlay.get("completion_verified") is not False
    ):
        raise ValueError("Focus overlay scope or verification claim invalid")
    entries = overlay.get("projects")
    cards = board.get("cards")
    if not isinstance(entries, list) or not isinstance(cards, list) or len(entries) > 100:
        raise ValueError("Focus project preview invalid")
    expected = {(c.get("project_id"), c.get("workspace_id")) for c in cards}
    if len(expected) != len(cards):
        raise ValueError("Duplicate board project scope")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Focus project entry invalid")
        key = (entry.get("project_id"), entry.get("workspace_id"))
        if key not in expected or key in result:
            raise ValueError("Unexpected, duplicate or hidden focus project")
        count = entry.get("total_sessions")
        recent = entry.get("recent_sessions")
        truncated = entry.get("sessions_truncated")
        if (
            type(count) is not int or count < 0
            or not isinstance(recent, list) or len(recent) > MAX_RECENT
            or len(recent) > count
            or type(truncated) is not bool
            or truncated != (len(recent) < count)
        ):
            raise ValueError("Inconsistent focus session coverage")
        seen = set()
        for session in recent:
            if not isinstance(session, dict):
                raise ValueError("Malformed focus session summary")
            sid = session.get("session_id")
            status = session.get("status")
            decision = session.get("decision")
            if not isinstance(sid, str) or not sid or len(sid) > 128 or sid in seen:
                raise ValueError("Invalid focus session ID")
            seen.add(sid)
            if status not in {"active", "closed"}:
                raise ValueError("Unsupported focus state")
            if status == "active" and decision is not None:
                raise ValueError("Active focus cannot claim a review decision")
            if status == "closed" and decision not in ALLOWED_DECISIONS:
                raise ValueError("Closed focus requires a supported human decision")
            for field in ("started_at", "closed_at"):
                date = session.get(field)
                if date is not None and (not isinstance(date, str) or len(date) > 48):
                    raise ValueError("Invalid local focus timestamp")
        result[key] = entry
    if set(result) != expected:
        raise ValueError("Focus overlay is missing displayed projects")
    return result
