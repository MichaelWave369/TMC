"""R8: privacy-scoped Focus Sessions on offline Circle-Back project cards."""
from __future__ import annotations

from copy import deepcopy
from html.parser import HTMLParser

import pytest

from app.core.service import MemoryService
from app.memory.focus_board import build_focus_overlay, checked_focus_overlay
from app.memory.review_html import render_review_board_html
from app.memory.review_delta import snapshot_from_review_board
from app.tools.circle_back_html import build_parser


def setup(tmp_path):
    service = MemoryService(str(tmp_path / "focus-board.db"))
    project = service.create_project("focus-card-workspace", "Synthetic Focus Card")
    return service, project


def get_board_and_overlay(service, limit=20):
    board = service.circle_back_review_board(limit=limit)
    return board, service.circle_back_focus_overlay(board)


def find_project(overlay, project):
    return next(row for row in overlay["projects"] if row["project_id"] == project.id)


def test_active_focus_appears_without_operator_notes_or_intent(tmp_path):
    svc, project = setup(tmp_path)
    focus = svc.start_focus_session(project.id, "PRIVATE_INTENT_SENTINEL")
    board, overlay = get_board_and_overlay(svc)
    row = find_project(overlay, project)
    assert row["total_sessions"] == 1
    assert row["recent_sessions"][0]["session_id"] == focus["id"]
    assert row["recent_sessions"][0]["status"] == "active"
    assert row["recent_sessions"][0]["decision"] is None
    html = render_review_board_html(board, focus_overlay=overlay)
    assert "Synthetic Focus Card" in html
    assert "Focus sessions" in html
    assert focus["id"] in html
    assert "PRIVATE_INTENT_SENTINEL" not in str(overlay)
    assert "PRIVATE_INTENT_SENTINEL" not in html
    assert "No task completion is verified" in html
    assert overlay["completion_verified"] is False
    assert overlay["automatic_actions"] is False


def test_closed_focus_decisions_display_without_raw_review_notes(tmp_path):
    svc, project = setup(tmp_path)
    focus = svc.start_focus_session(project.id, "PRIVATE_FOCUS_INTENT")
    svc.close_focus_session(focus["id"], "needs_evidence", "PRIVATE_REVIEW_NOTE")
    board, overlay = get_board_and_overlay(svc)
    html = render_review_board_html(board, focus_overlay=overlay)
    assert "Needs evidence" in html
    assert "Human review decision" in html
    assert "PRIVATE_FOCUS_INTENT" not in html
    assert "PRIVATE_REVIEW_NOTE" not in html
    assert "PRIVATE_REVIEW_NOTE" not in str(overlay)
    assert find_project(overlay, project)["recent_sessions"][0]["status"] == "closed"


def test_approved_task_link_is_not_exported_or_approved_by_read(tmp_path):
    svc, project = setup(tmp_path)
    act = svc.propose_next_action(project.id, "PRIVATE_ACTION_TITLE")
    focus = svc.start_focus_session(project.id, "Look at action")
    svc.close_focus_session(focus["id"], "next_action_identified", "PRIVATE_NOTE", act["id"])
    old = svc.store.get_next_action(act["id"]).model_dump(mode="json")
    board, overlay = get_board_and_overlay(svc)
    html = render_review_board_html(board, focus_overlay=overlay)
    assert "Next action identified" in html
    assert "PRIVATE_ACTION_TITLE" not in html
    assert "PRIVATE_NOTE" not in html
    assert "linked_action_id" not in html
    assert svc.store.get_next_action(act["id"]).model_dump(mode="json") == old


def test_three_recent_sessions_and_truncated_warning(tmp_path):
    svc, project = setup(tmp_path)
    ids = []
    for n in range(5):
        session = svc.start_focus_session(project.id, f"Private intent {n}")
        ids.append(session["id"])
        svc.close_focus_session(session["id"], "revisit_later", f"Private note {n}")
    board, overlay = get_board_and_overlay(svc)
    row = find_project(overlay, project)
    assert row["total_sessions"] == 5
    assert row["sessions_truncated"] is True
    assert len(row["recent_sessions"]) == 3
    html = render_review_board_html(board, focus_overlay=overlay)
    for sid in ids[-3:]:
        assert sid in html
    for sid in ids[:2]:
        assert sid not in html
    assert "Older focus sessions omitted" in html


def test_sessions_for_undisplayed_projects_not_exported(tmp_path):
    svc, shown = setup(tmp_path)
    unseen = svc.create_project("outside-visible-scope", "HIDDEN_PROJECT_NAME")
    s = svc.start_focus_session(unseen.id, "SENSITIVE_INTENT")
    board = svc.circle_back_review_board(limit=1)
    assert len(board["cards"]) == 1
    # Pick the display-selected project from the board; only it can have
    # metadata in the overlay, never a project beyond the selected cards.
    visible_ids = {c["project_id"] for c in board["cards"]}
    if unseen.id in visible_ids:
        # Force the desired exclusion by selecting a known, distinct card.
        board["cards"] = [{
            **board["cards"][0],
            "project_id": shown.id, "workspace_id": shown.workspace_id,
        }]
    overlay = svc.circle_back_focus_overlay(board)
    assert unseen.id not in str(overlay)
    assert s["id"] not in str(overlay)
    assert "SENSITIVE_INTENT" not in str(overlay)


def test_cross_profile_focus_rows_are_not_exported(tmp_path):
    svc, project = setup(tmp_path)
    before = svc.start_focus_session(project.id, "OLDER_PRIVATE_INTENT")
    profile = svc.create_profile("Secondary", "vault-default")
    svc.switch_profile(profile.profile_id)
    new_project = svc.create_project("secondary-focus-workspace", "Secondary Synthetic")
    newer = svc.start_focus_session(new_project.id, "OTHER_PRIVATE_INTENT")
    board, overlay = get_board_and_overlay(svc)
    assert before["id"] not in str(overlay)
    assert newer["id"] in str(overlay)
    assert "OLDER_PRIVATE_INTENT" not in str(overlay)
    assert overlay["profile_id"] == profile.profile_id


def test_overlay_rejects_cross_profile_board_scope(tmp_path):
    svc, project = setup(tmp_path)
    board = svc.circle_back_review_board()
    board["profile_id"] = "someone-else"
    with pytest.raises(ValueError, match="does not match"):
        svc.circle_back_focus_overlay(board)


def test_renderer_rejects_injected_cross_profile_or_hidden_project(tmp_path):
    svc, project = setup(tmp_path)
    board, overlay = get_board_and_overlay(svc)
    other = deepcopy(overlay)
    other["profile_id"] = "someone-else"
    with pytest.raises(ValueError, match="scope"):
        render_review_board_html(board, focus_overlay=other)
    injected = deepcopy(overlay)
    injected["projects"][0]["project_id"] = "UNLISTED_PRIVATE_PROJECT"
    with pytest.raises(ValueError, match="hidden focus project"):
        render_review_board_html(board, focus_overlay=injected)


@pytest.mark.parametrize("field,value", [
    ("automatic_actions", True),
    ("completion_verified", True),
    ("format", "remote_auto_focus"),
])
def test_renderer_rejects_unsupported_focus_claims(tmp_path, field, value):
    svc, _ = setup(tmp_path)
    board, overlay = get_board_and_overlay(svc)
    overlay[field] = value
    with pytest.raises(ValueError, match="claim"):
        render_review_board_html(board, focus_overlay=overlay)


def test_unsafe_focus_status_and_decision_labels_rejected(tmp_path):
    svc, project = setup(tmp_path)
    sess = svc.start_focus_session(project.id, "Synthetic intent")
    board, overlay = get_board_and_overlay(svc)
    found = find_project(overlay, project)
    found["recent_sessions"][0]["status"] = "verified"
    with pytest.raises(ValueError, match="Unsupported focus state"):
        render_review_board_html(board, focus_overlay=overlay)
    found["recent_sessions"][0]["status"] = "active"
    found["recent_sessions"][0]["decision"] = "completed"
    with pytest.raises(ValueError, match="Active focus"):
        render_review_board_html(board, focus_overlay=overlay)
    assert sess["id"]


def test_private_unapproved_fields_never_leak_into_html(tmp_path):
    svc, project = setup(tmp_path)
    session = svc.start_focus_session(project.id, "Synthetic")
    board, overlay = get_board_and_overlay(svc)
    entry = find_project(overlay, project)
    entry["secret"] = "UNEXPECTED_PRIVATE_PROJECT_FIELD"
    entry["recent_sessions"][0]["intent"] = "SECRET_INTENT"
    entry["recent_sessions"][0]["operator_note"] = "SECRET_OPERATOR_NOTE"
    entry["recent_sessions"][0]["linked_action_id"] = "SECRET_LINKED_ACTION"
    overlay["other"] = "SECRET_OVERLAY"
    html = render_review_board_html(board, focus_overlay=overlay)
    for token in ("UNEXPECTED_PRIVATE_PROJECT_FIELD", "SECRET_INTENT",
                  "SECRET_OPERATOR_NOTE", "SECRET_LINKED_ACTION", "SECRET_OVERLAY"):
        assert token not in html
    assert session["id"] in html


class ScanTags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attributes = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)


def test_focus_id_escaping_never_creates_executable_tags(tmp_path):
    svc, project = setup(tmp_path)
    session = svc.start_focus_session(project.id, "Synthetic")
    board, overlay = get_board_and_overlay(svc)
    find_project(overlay, project)["recent_sessions"][0]["session_id"] = '<img src=x onerror="alert(1)">'
    html = render_review_board_html(board, focus_overlay=overlay)
    tags = ScanTags()
    tags.feed(html)
    assert "<img src=x" not in html
    assert "&lt;img" in html
    for bad in ("img", "script", "iframe", "form", "link"):
        assert bad not in tags.tags
    assert not any(k in ("href", "src", "action") or k.startswith("on")
                   for k, _ in tags.attributes)
    assert "script-src 'none'" in html
    assert "connect-src 'none'" in html
    assert session["id"]


def test_r5_snapshot_format_is_unmodified_by_focus_overlay(tmp_path):
    svc, project = setup(tmp_path)
    svc.start_focus_session(project.id, "NEVER_IN_A_SNAPSHOT")
    board, overlay = get_board_and_overlay(svc)
    before = snapshot_from_review_board(board)
    _ = render_review_board_html(board, focus_overlay=overlay)
    after = snapshot_from_review_board(board)
    assert before == after
    assert "focus_sessions" not in str(after)
    assert "recent_sessions" not in str(after)
    assert "NEVER_IN_A_SNAPSHOT" not in str(after)


def test_focus_overlay_read_does_not_write_state_or_events(tmp_path):
    svc, project = setup(tmp_path)
    session = svc.start_focus_session(project.id, "Leave alone")
    before = len(svc.store.get_focus_session_events(session["id"]))
    audits = len(svc.store.get_audits())
    board, overlay = get_board_and_overlay(svc)
    assert overlay == svc.circle_back_focus_overlay(board)
    assert len(svc.store.get_focus_session_events(session["id"])) == before
    assert len(svc.store.get_audits()) == audits
    assert svc.store.get_focus_session(session["id"]).status.value == "active"


def test_without_focus_preserves_legacy_renderer_behavior(tmp_path):
    svc, project = setup(tmp_path)
    session = svc.start_focus_session(project.id, "Should not appear")
    board = svc.circle_back_review_board()
    html = render_review_board_html(board)
    assert session["id"] not in html
    assert "Focus sessions" not in html
    args = build_parser().parse_args(["--without-focus"])
    assert args.without_focus is True


def test_empty_board_accepts_empty_focus_project_list(tmp_path):
    svc, project = setup(tmp_path)
    board = svc.circle_back_review_board()
    board["cards"] = []
    overlay = svc.circle_back_focus_overlay(board)
    assert overlay["projects"] == []
    html = render_review_board_html(board, focus_overlay=overlay)
    assert "No project cards available" in html


def test_checked_focus_overlay_rejects_misleading_truncation(tmp_path):
    svc, project = setup(tmp_path)
    svc.start_focus_session(project.id, "A")
    board, overlay = get_board_and_overlay(svc)
    find_project(overlay, project)["sessions_truncated"] = True
    with pytest.raises(ValueError, match="coverage"):
        checked_focus_overlay(board, overlay)
