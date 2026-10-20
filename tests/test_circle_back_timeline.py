"""Circle-Back R6 offline visual timeline privacy and fidelity tests."""
from __future__ import annotations

from copy import deepcopy
from html.parser import HTMLParser
import os
from pathlib import Path
import stat

import pytest

from app.memory.review_timeline import (
    build_review_timeline, render_review_timeline_html,
)
from app.tools.circle_back_delta import save_private_json
from app.tools.circle_back_timeline import build_parser, create_offline_timeline


def snap(hour=12):
    return {
        "format": "tmc.circle_back.snapshot.v1",
        "profile_id": "operator-local",
        "generated_at": f"2026-10-19T{hour:02d}:00:00-07:00",
        "automatic_actions": False,
        "independently_verified": False,
        "total_projects": 1,
        "projects_considered": 1,
        "coverage_complete": True,
        "cards_truncated": False,
        "projects": [{
            "project_id": "project-fixture",
            "workspace_id": "workspace-fixture",
            "project_name": "Synthetic home project",
            "review_signal": "operator_decision_needed",
            "visible_evidence_count": 1,
            "uncertain_visible_record_count": 0,
            "operator_action_count": 1,
            "operator_actions_truncated": False,
            "operator_actions": [{
                "action_id": "next-fixture",
                "status": "proposed",
                "evidence_review": "consistent_with_local_snapshot",
            }],
        }],
    }


class TagReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attributes = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)


def test_three_sessions_show_two_chronological_intervals_and_changes():
    s1, s2, s3 = snap(12), snap(13), snap(14)
    s2["projects"][0]["operator_actions"][0]["status"] = "approved"
    s3["projects"][0]["operator_actions"][0]["status"] = "approved"
    s3["projects"][0]["operator_actions"][0]["evidence_review"] = "operator_recheck_required"
    s3["projects"][0]["review_signal"] = "evidence_recheck_required"
    timeline = build_review_timeline([s1, s2, s3])
    assert timeline["interval_count"] == 2
    assert timeline["snapshot_count"] == 3
    html = render_review_timeline_html(timeline)
    assert "Change timeline" in html or "change timeline" in html
    assert html.index("12:00:00") < html.index("13:00:00") < html.index("14:00:00")
    assert "approved" in html
    assert "operator recheck required" in html
    assert "Synthetic home project" in html
    assert "next-fixture" in html
    assert "No scripts, HTTP server" in html


def test_identical_snapshots_make_no_fake_progress_statements():
    s1, s2 = snap(12), snap(13)
    html = render_review_timeline_html(build_review_timeline([s1, s2]))
    assert "No comparable changes observed" in html
    assert "does not prove work was completed" in html
    assert "Snapshots" in html


def test_partial_project_coverage_is_prominent_and_suppresses_entries():
    a, b = snap(12), snap(13)
    a["total_projects"] = 101
    a["coverage_complete"] = False
    b["projects"][0]["project_id"] = "different-fixture"
    timeline = build_review_timeline([a, b])
    delta = timeline["intervals"][0]
    assert delta["project_entry_exit_comparison"] == "suppressed_due_to_incomplete_project_coverage"
    assert delta["newly_listed_projects"] == []
    html = render_review_timeline_html(timeline)
    assert "Partial coverage" in html
    assert "Newly listed project IDs" not in html
    assert "No longer listed project IDs" not in html


def test_action_preview_truncation_does_not_make_fake_action_changes():
    a, b = snap(12), snap(13)
    a["projects"][0]["operator_action_count"] = 2
    a["projects"][0]["operator_actions_truncated"] = True
    b["projects"][0]["operator_actions"][0]["status"] = "approved"
    delta = build_review_timeline([a, b])["intervals"][0]
    assert delta["project_deltas"][0]["action_changes"] == []
    html = render_review_timeline_html(build_review_timeline([a, b]))
    assert "Detailed action comparison suppressed" in html
    assert "one of the local action previews was incomplete" in html


def test_valid_project_listing_is_a_qualified_observation_not_creation():
    a, b = snap(12), snap(13)
    b["projects"][0]["project_id"] = "new-fixture"
    html = render_review_timeline_html(build_review_timeline([a, b]))
    assert "Newly listed project IDs" in html
    assert "No longer listed project IDs" in html
    assert "not proof of creation or deletion" in html


def test_attack_strings_are_html_escaped_and_no_script_resource_tags():
    a, b = snap(12), snap(13)
    bad = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
    a["projects"][0]["project_name"] = bad
    b["projects"][0]["project_name"] = bad + " updated"
    b["projects"][0]["operator_actions"][0]["status"] = "approved"
    b["projects"][0]["project_id"] = a["projects"][0]["project_id"]
    text = render_review_timeline_html(build_review_timeline([a, b]))
    parser = TagReader()
    parser.feed(text)
    assert bad not in text
    assert "&lt;img" in text
    assert "&lt;script&gt;" in text
    for tag in ("img", "script", "iframe", "link", "form", "object", "embed"):
        assert tag not in parser.tags
    assert not any(name in ("src", "href", "action") or name.startswith("on")
                   for name, value in parser.attributes)


def test_static_csp_blocks_js_network_fonts_forms():
    doc = render_review_timeline_html(build_review_timeline([snap(12), snap(13)]))
    for marker in ("default-src 'none'", "connect-src 'none'",
                   "script-src 'none'", "font-src 'none'", "form-action 'none'",
                   "base-uri 'none'", "referrer"):
        assert marker in doc
    assert '<details>' not in doc or '<summary>' in doc


def test_snapshot_unknown_sensitive_fields_never_rendered():
    a, b = snap(12), snap(13)
    for snapshot in (a, b):
        snapshot["untrusted_note"] = "DO_NOT_SHOW_SNAPSHOT_NOTE"
        snapshot["projects"][0]["raw_capsule_text"] = "DO_NOT_SHOW_CAPSULE_BODY"
        snapshot["projects"][0]["operator_actions"][0]["operator_note"] = "DO_NOT_SHOW_OPERATOR_NOTE"
        snapshot["projects"][0]["operator_actions"][0]["source_capsule_ids"] = ["DO_NOT_SHOW_SOURCE_ID"]
        snapshot["projects"][0]["operator_actions"][0]["source_snapshots"] = {"secret": "DO_NOT_SHOW_HASH"}
    b["projects"][0]["review_signal"] = "approved_followup_needed"
    doc = render_review_timeline_html(build_review_timeline([a, b]))
    for marker in ("DO_NOT_SHOW_SNAPSHOT_NOTE", "DO_NOT_SHOW_CAPSULE_BODY",
                   "DO_NOT_SHOW_OPERATOR_NOTE", "DO_NOT_SHOW_SOURCE_ID",
                   "DO_NOT_SHOW_HASH"):
        assert marker not in doc


def test_cross_profile_rejected_before_any_output_file_created(tmp_path):
    a, b = snap(12), snap(13)
    b["profile_id"] = "other-profile"
    p1 = save_private_json(a, tmp_path / "a.json")
    p2 = save_private_json(b, tmp_path / "b.json")
    out = tmp_path / "result.html"
    with pytest.raises(ValueError, match="different profiles"):
        create_offline_timeline([p1, p2], out)
    assert not out.exists()


@pytest.mark.parametrize("clock_list", [
    [snap(13), snap(12)],
    [snap(12), snap(12)],
])
def test_nonincreasing_snapshot_times_rejected(clock_list):
    with pytest.raises(ValueError, match="strictly increasing"):
        build_review_timeline(clock_list)


def test_reject_unbounded_snapshot_count():
    with pytest.raises(ValueError, match="2 through 12"):
        build_review_timeline([snap(12)])
    with pytest.raises(ValueError, match="2 through 12"):
        build_review_timeline([snap(12)] * 13)


def test_twelve_snapshots_is_supported():
    snaps = [snap(i) for i in range(12)]
    result = build_review_timeline(snaps)
    assert result["snapshot_count"] == 12
    assert result["interval_count"] == 11


def test_invalid_snapshot_claims_do_not_render():
    a, b = snap(12), snap(13)
    a["independently_verified"] = True
    with pytest.raises(ValueError, match="independently verified"):
        build_review_timeline([a, b])
    a, b = snap(12), snap(13)
    b["projects"][0]["operator_actions"][0]["status"] = "verified"
    with pytest.raises(ValueError, match="Unsupported action status"):
        build_review_timeline([a, b])


def test_untrusted_timeline_claims_and_interval_limits_rejected():
    timeline = build_review_timeline([snap(12), snap(13)])
    hacked = deepcopy(timeline)
    hacked["independently_verified"] = True
    with pytest.raises(ValueError, match="verification"):
        render_review_timeline_html(hacked)
    hacked = deepcopy(timeline)
    hacked["interval_count"] = 99
    with pytest.raises(ValueError, match="lengths"):
        render_review_timeline_html(hacked)
    hacked = deepcopy(timeline)
    hacked["intervals"][0]["project_entry_exit_comparison"] = "unsupported"
    with pytest.raises(ValueError, match="coverage"):
        render_review_timeline_html(hacked)


def test_cli_creates_private_html_and_rejects_existing_destination(tmp_path):
    old = save_private_json(snap(12), tmp_path / "old.json")
    new = save_private_json(snap(13), tmp_path / "new.json")
    output = tmp_path / "timeline.circle-back.html"
    assert create_offline_timeline([old, new], output) == output
    html = output.read_text(encoding="utf-8")
    assert "change timeline" in html
    if os.name == "posix":
        assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        create_offline_timeline([old, new], output)
    assert output.read_text(encoding="utf-8") == html


def test_default_output_in_owner_only_temp_folder(tmp_path):
    a = save_private_json(snap(12), tmp_path / "old.json")
    b = save_private_json(snap(13), tmp_path / "new.json")
    out = create_offline_timeline([a, b])
    try:
        assert out.exists()
        if os.name == "posix":
            assert stat.S_IMODE(out.stat().st_mode) == 0o600
            assert stat.S_IMODE(out.parent.stat().st_mode) == 0o700
    finally:
        out.unlink()
        out.parent.rmdir()


def test_repo_destination_rejected_and_symlink_not_followed(tmp_path):
    a = save_private_json(snap(12), tmp_path / "old.json")
    b = save_private_json(snap(13), tmp_path / "new.json")
    repo_root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="outside the repository"):
        create_offline_timeline([a, b], repo_root / "accidental.circle-back.html")
    victim = tmp_path / "unrelated.txt"
    victim.write_text("KEEP", encoding="utf-8")
    symlink = tmp_path / "timeline.html"
    try:
        symlink.symlink_to(victim)
    except (NotImplementedError, OSError):
        pytest.skip("Symlinks not available")
    with pytest.raises(FileExistsError):
        create_offline_timeline([a, b], symlink)
    assert victim.read_text(encoding="utf-8") == "KEEP"


def test_bad_input_and_repeated_file_rejected(tmp_path):
    a = save_private_json(snap(12), tmp_path / "old.json")
    with pytest.raises(ValueError, match="different file"):
        create_offline_timeline([a, a], tmp_path / "out.html")
    bogus = tmp_path / "bad.json"
    bogus.write_text('{"format":"other"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        create_offline_timeline([a, bogus], tmp_path / "out.html")
    assert not (tmp_path / "out.html").exists()


def test_cli_parses_windows_friendly_paths():
    args = build_parser().parse_args([
        "--snapshot", "C:/local/day-1.json", "--snapshot", "C:/local/day-2.json",
        "--output", "C:/private/timeline.circle-back.html",
    ])
    assert len(args.snapshot) == 2
    assert args.snapshot[0] == Path("C:/local/day-1.json")
    assert args.output == Path("C:/private/timeline.circle-back.html")
