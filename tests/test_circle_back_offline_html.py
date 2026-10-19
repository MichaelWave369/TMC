"""Circle-Back R4 offline HTML rendering / file privacy controls."""
from __future__ import annotations

import os
import stat
from pathlib import Path
from html.parser import HTMLParser

import pytest

from app.core.service import MemoryService
from app.memory.models import IngestRequest, PolicyMode
from app.memory.review_html import render_review_board_html
from app.tools.circle_back_html import build_parser, save_new_local_report


def fake_board():
    return {
        "mode": "local_read_only_review_board",
        "profile_id": "default",
        "generated_at": "2035-01-01T00:00:00Z",
        "auto_actions": False,
        "independent_verification": False,
        "total_projects": 3,
        "projects_considered": 2,
        "coverage_complete": False,
        "cards_truncated": True,
        "cards": [{
            "project_id": "proj-1", "workspace_id": "workspace-1",
            "project_name": "Synthetic work", "review_signal": "operator_decision_needed",
            "suggested_operator_step": "Review the proposal",
            "visible_evidence_count": 2, "uncertain_visible_record_count": 1,
            "operator_action_count": 1, "days_since_visible_activity": 30,
            "operator_actions_truncated": False,
            "operator_actions": [{
                "status": "proposed", "action_id": "next-1",
                "evidence_review": "consistent_with_local_snapshot",
                "updated_at": "2035-01-01T00:00:00Z",
            }],
        }],
    }


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attrs = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(attrs)


def test_html_contains_approved_local_board_fields_and_coverage_warning():
    html = render_review_board_html(fake_board())
    assert html.startswith("<!doctype html>")
    assert "Synthetic work" in html
    assert "Review the proposal" in html
    assert "Coverage incomplete" in html
    assert "Result limit reached" in html
    assert "next-1" in html
    assert "independently verified completion" in html
    assert "network-backed assets" in html


def test_xss_is_encoded_even_in_names_step_and_action_id():
    board = fake_board()
    attack = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
    board["cards"][0]["project_name"] = attack
    board["cards"][0]["suggested_operator_step"] = attack
    board["cards"][0]["operator_actions"][0]["action_id"] = attack
    html = render_review_board_html(board)
    assert attack not in html
    assert "&lt;img" in html and "&lt;script&gt;" in html
    parsed = Tags()
    parsed.feed(html)
    assert "img" not in parsed.tags and "script" not in parsed.tags
    assert "iframe" not in parsed.tags and "form" not in parsed.tags
    assert not any(a.lower().startswith("on") for a, _ in parsed.attrs)


def test_no_external_network_resources_or_executable_scripts():
    html = render_review_board_html(fake_board())
    parser = Tags()
    parser.feed(html)
    assert "script" not in parser.tags
    assert "link" not in parser.tags
    assert "iframe" not in parser.tags
    assert "form" not in parser.tags
    assert "default-src 'none'" in html
    assert "connect-src 'none'" in html
    assert "script-src 'none'" in html
    assert "form-action 'none'" in html
    assert not any(a in {"href", "src", "action"} for a, _ in parser.attrs)


def test_ignore_surplus_sensitive_fields_in_render_input():
    board = fake_board()
    board["secret"] = "DONOTEXPORT"
    card = board["cards"][0]
    card["capsule_text"] = "PRIVATE_CAPSULE_TEXT"
    card["source_capsule_ids"] = ["HIDDEN_CAPSULE_ID"]
    card["completion_status"] = "not_independently_verified"
    action = card["operator_actions"][0]
    action["operator_note"] = "TOP_SECRET_NOTE"
    action["title"] = "PRIVATE_ACTION_TITLE"
    action["source_snapshots"] = {"secret": "PRIVATE_DIGEST"}
    html = render_review_board_html(board)
    for marker in ("DONOTEXPORT", "PRIVATE_CAPSULE_TEXT", "HIDDEN_CAPSULE_ID",
                   "TOP_SECRET_NOTE", "PRIVATE_ACTION_TITLE", "PRIVATE_DIGEST"):
        assert marker not in html


@pytest.mark.parametrize("mode,auto,verified", [
    ("wrong_mode", False, False),
    ("local_read_only_review_board", True, False),
    ("local_read_only_review_board", False, True),
])
def test_reject_unsupported_or_unsafe_board_claims(mode, auto, verified):
    board = fake_board()
    board["mode"] = mode
    board["auto_actions"] = auto
    board["independent_verification"] = verified
    with pytest.raises(ValueError):
        render_review_board_html(board)


def test_empty_board_has_honest_empty_state():
    board = fake_board()
    board["cards"] = []
    board["total_projects"] = 0
    board["projects_considered"] = 0
    board["coverage_complete"] = True
    board["cards_truncated"] = False
    html = render_review_board_html(board)
    assert "No project cards available" in html
    assert "Coverage incomplete" not in html
    assert "Registered projects" in html


def test_reject_overlong_cards_and_action_lists():
    board = fake_board()
    board["cards"] = [dict(board["cards"][0]) for _ in range(101)]
    with pytest.raises(ValueError, match="bounded list"):
        render_review_board_html(board)
    board = fake_board()
    board["cards"][0]["operator_actions"] = [{}] * 9
    with pytest.raises(ValueError, match="bounded"):
        render_review_board_html(board)


def test_generated_file_is_owner_only_and_never_overwritten(tmp_path):
    target = tmp_path / "review.circle-back.html"
    content = render_review_board_html(fake_board())
    result = save_new_local_report(content, target)
    assert result == target
    assert target.read_text(encoding="utf-8") == content
    if os.name == "posix":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        save_new_local_report("overwriting would leak", target)
    assert target.read_text(encoding="utf-8") == content


def test_symlink_destination_is_not_followed(tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("do not replace", encoding="utf-8")
    link = tmp_path / "review.html"
    try:
        link.symlink_to(victim)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable on this platform")
    with pytest.raises(FileExistsError):
        save_new_local_report("bad", link)
    assert victim.read_text(encoding="utf-8") == "do not replace"


def test_default_temp_report_directory_is_private(tmp_path):
    path = save_new_local_report(render_review_board_html(fake_board()))
    try:
        assert path.is_file()
        if os.name == "posix":
            assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
    finally:
        path.unlink()
        path.parent.rmdir()


def test_explicit_repo_destination_is_blocked(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="outside the repository"):
        save_new_local_report("<html></html>", repo / "accidental-report.html")
    assert not (repo / "accidental-report.html").exists()


def test_export_respects_existing_profile_and_evidence_redactions(tmp_path):
    svc = MemoryService(str(tmp_path / "review.db"))
    project = svc.create_project("fixture-r4", "Work-safe demo")
    private = svc.ingest_text(IngestRequest(
        source_type="unit_test", source_ref="SECRET_REF",
        text="HIDDEN_FULL_CAPSULE_TEXT",
        workspace_ids=[project.workspace_id],
        policy=PolicyMode.private_local_only,
    ))[0]
    proposal = svc.propose_next_action(project.id, "PRIVATE_NEXT_ACTION_TITLE")
    html = render_review_board_html(svc.circle_back_review_board())
    assert "Work-safe demo" in html
    for marker in ("SECRET_REF", "HIDDEN_FULL_CAPSULE_TEXT", private.id,
                   "PRIVATE_NEXT_ACTION_TITLE"):
        assert marker not in html
    assert proposal["id"] in html
    assert "automatically" not in html.lower() or "automatic" in html.lower()


def test_cli_parser_options():
    args = build_parser().parse_args([
        "--db", "example.db", "--limit", "5", "--stale-days", "90",
        "--output", "outside-repo.circle-back.html",
    ])
    assert args.db == "example.db"
    assert args.limit == 5
    assert args.stale_days == 90
    assert args.output == Path("outside-repo.circle-back.html")
