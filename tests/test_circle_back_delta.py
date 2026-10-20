"""Circle-Back R5: cautious local before/after review comparisons."""
from __future__ import annotations

from copy import deepcopy
import json
import os
import stat
from pathlib import Path

import pytest

from app.core.service import MemoryService
from app.memory.models import IngestRequest
from app.memory.review_delta import snapshot_from_review_board, compare_review_snapshots
from app.tools.circle_back_delta import (
    build_parser, save_private_json, load_private_snapshot,
)


def snapshot():
    return {
        "format": "tmc.circle_back.snapshot.v1",
        "profile_id": "default",
        "generated_at": "2026-10-19T12:00:00-07:00",
        "automatic_actions": False,
        "independently_verified": False,
        "total_projects": 1,
        "projects_considered": 1,
        "coverage_complete": True,
        "cards_truncated": False,
        "projects": [{
            "project_id": "synthetic-id",
            "workspace_id": "synthetic-workspace",
            "project_name": "Synthetic Example",
            "review_signal": "operator_decision_needed",
            "visible_evidence_count": 1,
            "uncertain_visible_record_count": 0,
            "operator_action_count": 1,
            "operator_actions_truncated": False,
            "operator_actions": [{
                "action_id": "synthetic-action-id",
                "status": "proposed",
                "evidence_review": "consistent_with_local_snapshot",
            }],
        }],
    }


def test_exact_duplicate_has_no_observed_changes_or_false_claims():
    original = snapshot()
    later = deepcopy(original)
    later["generated_at"] = "2026-10-19T13:00:00-07:00"
    out = compare_review_snapshots(original, later)
    assert out["project_deltas"] == []
    assert out["compared_projects"] == 1
    assert out["newly_listed_projects"] == []
    assert out["no_longer_listed_projects"] == []
    assert out["independently_verified"] is False
    assert out["automatic_actions"] is False
    assert "not independently verified" in out["interpretation"]


def test_operator_decision_and_evidence_warning_are_detected_without_truth_claim():
    original = snapshot()
    later = deepcopy(original)
    later["projects"][0]["operator_actions"][0]["status"] = "approved"
    later["projects"][0]["operator_actions"][0]["evidence_review"] = "operator_recheck_required"
    later["projects"][0]["review_signal"] = "evidence_recheck_required"
    result = compare_review_snapshots(original, later)
    delta = result["project_deltas"][0]
    assert delta["changes"]["review_signal"]["after"] == "evidence_recheck_required"
    a = delta["action_changes"][0]
    assert a["changes"]["status"] == {"before": "proposed", "after": "approved"}
    assert a["changes"]["evidence_review"]["after"] == "operator_recheck_required"
    assert "completed" not in str(result)


def test_added_and_no_longer_listed_are_observations_only_with_full_coverage():
    first = snapshot()
    second = deepcopy(first)
    second["projects"][0]["project_id"] = "new-id"
    assert compare_review_snapshots(first, second)["newly_listed_projects"] == ["new-id"]
    out = compare_review_snapshots(first, second)
    assert out["no_longer_listed_projects"] == ["synthetic-id"]
    assert out["project_entry_exit_comparison"] == "complete_for_visible_profile"


@pytest.mark.parametrize("which", ["before", "after"])
def test_project_entry_exit_suppressed_when_either_side_is_incomplete(which):
    a, b = snapshot(), snapshot()
    chosen = a if which == "before" else b
    chosen["total_projects"] = 101
    chosen["projects_considered"] = 1
    chosen["coverage_complete"] = False
    b["projects"][0]["project_id"] = "different-visible-project"
    out = compare_review_snapshots(a, b)
    assert out["project_entry_exit_comparison"] == "suppressed_due_to_incomplete_project_coverage"
    assert out["newly_listed_projects"] == []
    assert out["no_longer_listed_projects"] == []


def test_action_deltas_suppressed_if_a_preview_is_truncated():
    a, b = snapshot(), snapshot()
    a["projects"][0]["operator_action_count"] = 2
    a["projects"][0]["operator_actions_truncated"] = True
    b["projects"][0]["operator_actions"][0]["status"] = "approved"
    out = compare_review_snapshots(a, b)
    assert out["project_deltas"][0]["action_comparison"] == "suppressed_due_to_action_preview_limit"
    assert out["project_deltas"][0]["action_changes"] == []


def test_visible_source_counts_can_change_but_no_hidden_source_identifiers():
    a, b = snapshot(), snapshot()
    b["projects"][0]["visible_evidence_count"] = 2
    out = compare_review_snapshots(a, b)
    assert out["project_deltas"][0]["changes"]["visible_evidence_count"] == {
        "before": 1, "after": 2,
    }
    assert "source_capsule_ids" not in str(out)


def test_renamed_projects_record_a_local_display_change():
    a, b = snapshot(), snapshot()
    b["projects"][0]["project_name"] = "New synthetic name"
    d = compare_review_snapshots(a, b)["project_deltas"][0]
    assert d["changes"]["project_name"]["before"] == "Synthetic Example"


def test_extra_sensitive_board_fields_are_stripped():
    svc_board = {
        "mode": "local_read_only_review_board",
        "profile_id": "default",
        "generated_at": "2026-10-19T12:00:00-07:00",
        "auto_actions": False,
        "independent_verification": False,
        "total_projects": 1,
        "projects_considered": 1,
        "coverage_complete": True,
        "cards_truncated": False,
        "cards": [{
            **snapshot()["projects"][0],
            "memory_text": "DO_NOT_EXPORT_MEMORY",
            "operator_note": "DO_NOT_EXPORT_NOTES",
            "secret_hash": "DO_NOT_EXPORT_HASH",
            "source_capsule_ids": ["DO_NOT_EXPORT_SOURCE"],
        }],
        "other_secret": "DO_NOT_EXPORT_OTHER",
    }
    svc_board["cards"][0]["operator_actions"][0]["title"] = "DO_NOT_EXPORT_TITLE"
    result = snapshot_from_review_board(svc_board)
    for sensitive in ("DO_NOT_EXPORT_MEMORY", "DO_NOT_EXPORT_NOTES",
                      "DO_NOT_EXPORT_HASH", "DO_NOT_EXPORT_SOURCE",
                      "DO_NOT_EXPORT_OTHER", "DO_NOT_EXPORT_TITLE"):
        assert sensitive not in str(result)
    assert result["projects"][0]["operator_actions"][0]["status"] == "proposed"


def test_real_memory_service_board_can_be_snapshotted_without_mutation(tmp_path):
    svc = MemoryService(str(tmp_path / "r5.db"))
    project = svc.create_project("snapshot-demo", "Synthetic snapshot demo")
    capsule = svc.ingest_text(IngestRequest(
        source_type="unit_test", source_ref="SHOULD_NOT_EXPORT_REF",
        text="SHOULD_NOT_EXPORT_CAPSULE_TEXT",
        workspace_ids=[project.workspace_id],
    ))[0]
    act = svc.propose_next_action(project.id, "SHOULD_NOT_EXPORT_TITLE", source_capsule_ids=[capsule.id])
    before = len(svc.store.get_next_action_events(act["id"]))
    a = snapshot_from_review_board(svc.circle_back_review_board(limit=100))
    b = snapshot_from_review_board(svc.circle_back_review_board(limit=100))
    assert compare_review_snapshots(a, b)["project_deltas"] == []
    assert len(svc.store.get_next_action_events(act["id"])) == before
    for secret in ("SHOULD_NOT_EXPORT_REF", "SHOULD_NOT_EXPORT_CAPSULE_TEXT",
                   "SHOULD_NOT_EXPORT_TITLE", capsule.id):
        assert secret not in str(a)
    assert act["id"] in str(a)


@pytest.mark.parametrize("field,value,message", [
    ("review_signal", "independently_verified", "Unsupported review signal"),
    ("status", "verified", "Unsupported action status"),
    ("evidence_review", "truth_certified", "Unsupported evidence review state"),
])
def test_untrusted_snapshots_cannot_invent_verification_states(field, value, message):
    a, b = snapshot(), snapshot()
    if field == "review_signal":
        b["projects"][0][field] = value
    else:
        b["projects"][0]["operator_actions"][0][field] = value
    with pytest.raises(ValueError, match=message):
        compare_review_snapshots(a, b)


def test_out_of_order_timestamps_rejected():
    a, b = snapshot(), snapshot()
    a["generated_at"] = "2026-10-20T12:00:00+00:00"
    with pytest.raises(ValueError, match="chronological"):
        compare_review_snapshots(a, b)


def test_timezone_aware_timestamp_required():
    a, b = snapshot(), snapshot()
    b["generated_at"] = "2026-10-19T12:00:00"
    with pytest.raises(ValueError, match="offset"):
        compare_review_snapshots(a, b)


def test_cross_profile_comparison_refused():
    a, b = snapshot(), snapshot()
    b["profile_id"] = "different"
    with pytest.raises(ValueError, match="different profiles"):
        compare_review_snapshots(a, b)


def test_mismatched_project_workspace_refused():
    a, b = snapshot(), snapshot()
    b["projects"][0]["workspace_id"] = "other-workspace"
    with pytest.raises(ValueError, match="scope changed"):
        compare_review_snapshots(a, b)


def test_duplicate_project_or_action_ids_rejected():
    a, b = snapshot(), snapshot()
    a["projects"].append(deepcopy(a["projects"][0]))
    a["total_projects"] = a["projects_considered"] = 2
    with pytest.raises(ValueError, match="Duplicate project"):
        compare_review_snapshots(a, b)
    a = snapshot()
    a["projects"][0]["operator_actions"].append(deepcopy(a["projects"][0]["operator_actions"][0]))
    a["projects"][0]["operator_action_count"] = 2
    with pytest.raises(ValueError, match="Duplicate action"):
        compare_review_snapshots(a, b)


def test_contradictory_coverage_and_auto_claim_rejected():
    a, b = snapshot(), snapshot()
    a["coverage_complete"] = False
    with pytest.raises(ValueError, match="Coverage flag"):
        compare_review_snapshots(a, b)
    a = snapshot()
    a["automatic_actions"] = True
    with pytest.raises(ValueError, match="automatic"):
        compare_review_snapshots(a, b)
    a = snapshot()
    a["independently_verified"] = True
    with pytest.raises(ValueError, match="independently"):
        compare_review_snapshots(a, b)


def test_owner_only_creation_no_overwrites_and_roundtrip(tmp_path):
    data = snapshot()
    path = tmp_path / "private-r5.json"
    assert save_private_json(data, path) == path
    assert load_private_snapshot(path) == data
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        save_private_json({"overwrite": True}, path)
    assert load_private_snapshot(path) == data


def test_destination_inside_repo_rejected():
    source_root = Path(__file__).resolve().parents[1]
    path = source_root / "do-not-commit-r5.json"
    with pytest.raises(ValueError, match="outside the repository"):
        save_private_json(snapshot(), path)
    assert not path.exists()


def test_symlink_output_rejected_without_overwriting(tmp_path):
    victim = tmp_path / "victim.json"
    victim.write_text("untouched")
    link = tmp_path / "linked.json"
    try:
        link.symlink_to(victim)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable on this platform")
    with pytest.raises((FileExistsError, OSError)):
        save_private_json(snapshot(), link)
    assert victim.read_text() == "untouched"


def test_input_rejects_symlink_duplicate_keys_and_oversize(tmp_path):
    path = tmp_path / "snap.json"
    path.write_text('{"a":1,"a":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate key"):
        load_private_snapshot(path)
    path.write_bytes(b"x" * 2_000_001)
    with pytest.raises(ValueError, match="too large"):
        load_private_snapshot(path)
    path.write_text(json.dumps(snapshot()))
    link = tmp_path / "link.json"
    try:
        link.symlink_to(path)
    except (OSError, NotImplementedError):
        return
    with pytest.raises(ValueError, match="symlinks"):
        load_private_snapshot(link)


def test_default_file_in_private_temp_dir():
    target = save_private_json(snapshot())
    try:
        assert load_private_snapshot(target)["profile_id"] == "default"
        if os.name == "posix":
            assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700
            assert stat.S_IMODE(target.stat().st_mode) == 0o600
    finally:
        target.unlink()
        target.parent.rmdir()


def test_cli_options_parse_without_network_or_job_flags():
    p = build_parser()
    a = p.parse_args(["snapshot", "--db", "dummy.db", "--stale-days", "12"])
    assert a.operation == "snapshot" and a.stale_days == 12
    b = p.parse_args(["compare", "--before", "old.json", "--after", "new.json"])
    assert b.before == Path("old.json") and b.after == Path("new.json")
    assert not hasattr(b, "http_url")
