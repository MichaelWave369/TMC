"""Circle-Back R3: reconciled local review with strict operator claims."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.service import MemoryService
from app.memory.models import (
    CapsuleStatus, IngestRequest, PolicyMode, ProjectRecord,
)
from app.tools.circle_back_actions import build_parser

NOW = datetime(2035, 1, 1, tzinfo=timezone.utc)


def setup(tmp_path):
    svc = MemoryService(str(tmp_path / "r3.db"))
    project = svc.create_project("r3-main-workspace", "R3 example")
    return svc, project


def add(svc, project, text="Publicly safe synthetic source", policy=PolicyMode.persistent):
    return svc.ingest_text(IngestRequest(
        source_type="test", source_ref="fixture-secret-should-not-appear",
        text=text, workspace_ids=[project.workspace_id],
        profile_id=svc.active_profile_id, policy=policy,
    ))[0]


def board(svc):
    return svc.circle_back_review_board(as_of=NOW)


def project_card(svc, project):
    return next(c for c in board(svc)["cards"] if c["project_id"] == project.id)


def test_proposed_action_requires_manual_decision(tmp_path):
    svc, project = setup(tmp_path)
    action = svc.propose_next_action(project.id, "Next action title should not appear")
    row = project_card(svc, project)
    assert row["review_signal"] == "operator_decision_needed"
    assert row["operator_actions"][0]["status"] == "proposed"
    assert row["operator_actions"][0]["action_id"] == action["id"]
    assert "Next action title" not in str(board(svc))
    assert board(svc)["auto_actions"] is False
    assert board(svc)["independent_verification"] is False


def test_approved_action_is_a_followup_not_a_job(tmp_path):
    svc, project = setup(tmp_path)
    action = svc.propose_next_action(project.id, "Review feature")
    svc.decide_next_action(action["id"], True)
    row = project_card(svc, project)
    assert row["review_signal"] == "approved_followup_needed"
    assert row["completion_status"] == "not_independently_verified"
    assert row["operator_actions"][0]["evidence_review"] == "no_evidence_snapshot"


def test_stale_source_raises_review_priority_and_leaks_no_hidden_id(tmp_path):
    svc, project = setup(tmp_path)
    capsule = add(svc, project, "Synthetic current source")
    action = svc.propose_next_action(project.id, "Feature review", source_capsule_ids=[capsule.id])
    svc.decide_next_action(action["id"], True)
    capsule.text = "Updated synthetic source"
    svc.store.upsert_capsule(capsule)
    row = project_card(svc, project)
    assert row["review_signal"] == "evidence_recheck_required"
    assert row["operator_actions"][0]["evidence_review"] == "operator_recheck_required"
    assert capsule.id not in str(board(svc))
    assert "Updated synthetic" not in str(board(svc))
    assert "source_snapshots" not in str(board(svc))


@pytest.mark.parametrize("status", [
    CapsuleStatus.conflicting, CapsuleStatus.uncertain, CapsuleStatus.pending_review,
])
def test_uncertain_visible_capsule_precedes_generic_review(tmp_path, status):
    svc, project = setup(tmp_path)
    capsule = add(svc, project)
    capsule.status = status
    svc.store.upsert_capsule(capsule)
    row = project_card(svc, project)
    assert row["review_signal"] == "memory_review_needed"
    assert row["uncertain_visible_record_count"] >= 1


def test_hidden_policy_not_counted_and_no_title_note_or_source_ref(tmp_path):
    svc, project = setup(tmp_path)
    private = add(svc, project, text="DO-NOT-LEAK", policy=PolicyMode.private_local_only)
    row = project_card(svc, project)
    assert row["review_signal"] == "attach_source_review"
    assert row["visible_evidence_count"] == 0
    assert private.id not in str(board(svc))
    assert "DO-NOT-LEAK" not in str(board(svc))
    assert "fixture-secret-should-not-appear" not in str(board(svc))


def test_locked_vault_evidence_raises_warning_without_revealing_id(tmp_path):
    svc, project = setup(tmp_path)
    cap = add(svc, project)
    action = svc.propose_next_action(project.id, "Review", source_capsule_ids=[cap.id])
    svc.lock_vault(cap.vault_id)
    row = project_card(svc, project)
    assert row["review_signal"] == "evidence_recheck_required"
    assert cap.id not in str(board(svc))
    assert row["operator_actions"][0]["evidence_review"] == "operator_recheck_required"


def test_attested_action_is_explicitly_not_verified(tmp_path):
    svc, project = setup(tmp_path)
    cap = add(svc, project)
    action = svc.propose_next_action(project.id, "Review", source_capsule_ids=[cap.id])
    svc.decide_next_action(action["id"], True)
    svc.attest_next_action_done(action["id"], [cap.id], "Operator says done")
    # Recent context can carry an attestation label; old context must still
    # trigger a staleness review, even when the operator previously said done.
    recent = svc.circle_back_review_board(as_of=NOW, stale_days=3650)
    row = next(c for c in recent["cards"] if c["project_id"] == project.id)
    assert row["review_signal"] == "operator_attested_not_verified"
    assert row["operator_actions"][0]["status"] == "operator_attested"
    assert row["operator_actions"][0]["independent_verification"] is False
    assert "Operator says done" not in str(recent)
    stale_row = project_card(svc, project)
    assert stale_row["review_signal"] == "stale_context_review"
    assert stale_row["completion_status"] == "not_independently_verified"


def test_rejected_action_does_not_trigger_drift_review(tmp_path):
    svc, project = setup(tmp_path)
    cap = add(svc, project)
    action = svc.propose_next_action(project.id, "Reject later", source_capsule_ids=[cap.id])
    svc.decide_next_action(action["id"], False)
    cap.text = "Edited later"
    svc.store.upsert_capsule(cap)
    row = project_card(svc, project)
    assert row["review_signal"] != "evidence_recheck_required"
    assert row["operator_actions"][0]["status"] == "rejected"


def test_board_read_is_pure_and_repeatable(tmp_path):
    svc, project = setup(tmp_path)
    action = svc.propose_next_action(project.id, "Read-only")
    a = len(svc.store.get_audits())
    e = len(svc.store.get_next_action_events(action["id"]))
    first = board(svc)
    assert first == board(svc)
    assert len(svc.store.get_audits()) == a
    assert len(svc.store.get_next_action_events(action["id"])) == e
    same = MemoryService(str(tmp_path / "r3.db"))
    assert same.circle_back_review_board(as_of=NOW) == first


def test_cross_profile_actions_projects_not_listed(tmp_path):
    svc, project = setup(tmp_path)
    action = svc.propose_next_action(project.id, "Private operator record")
    other = svc.create_profile("Other", "vault-default")
    svc.switch_profile(other.profile_id)
    result = board(svc)
    assert project.id not in str(result)
    assert action["id"] not in str(result)
    assert "Private operator record" not in str(result)


def test_source_edit_between_approval_and_attestation_blocks_done(tmp_path):
    svc, project = setup(tmp_path)
    source = add(svc, project)
    act = svc.propose_next_action(project.id, "Review", source_capsule_ids=[source.id])
    svc.decide_next_action(act["id"], True)
    completion = add(svc, project, text="Synthetic completion evidence")
    source.metadata["changed"] = "since approval"
    svc.store.upsert_capsule(source)
    initial_events = svc.next_action_history(act["id"])
    with pytest.raises(ValueError, match="Source evidence changed"):
        svc.attest_next_action_done(act["id"], [completion.id], "Operator check")
    assert svc.store.get_next_action(act["id"]).status.value == "approved"
    assert svc.next_action_history(act["id"]) == initial_events
    assert svc.store.get_next_action(act["id"]).completion_evidence_ids == []


def test_source_policy_change_between_approval_and_attest_blocks_done(tmp_path):
    svc, project = setup(tmp_path)
    source = add(svc, project)
    action = svc.propose_next_action(project.id, "Review", source_capsule_ids=[source.id])
    svc.decide_next_action(action["id"], True)
    source.policy = PolicyMode.private_local_only
    svc.store.upsert_capsule(source)
    with pytest.raises(ValueError, match="not policy-visible"):
        svc.attest_next_action_done(action["id"], [source.id], "Operator note")
    assert svc.store.get_next_action(action["id"]).status.value == "approved"


def test_legacy_approved_without_snapshots_cannot_attest_as_if_verified(tmp_path):
    svc, project = setup(tmp_path)
    cap = add(svc, project)
    action = svc.propose_next_action(project.id, "R2 action", source_capsule_ids=[cap.id])
    svc.decide_next_action(action["id"], True)
    old = svc.store.get_next_action(action["id"])
    old.source_snapshots = {}
    svc.store._upsert("next_actions", old.id, old.model_dump(mode="json"))
    with pytest.raises(ValueError, match="snapshot unavailable"):
        svc.attest_next_action_done(action["id"], [cap.id], "Local claim")
    assert svc.store.get_next_action(action["id"]).status.value == "approved"


def test_no_source_refs_can_still_be_attested_with_new_evidence(tmp_path):
    svc, project = setup(tmp_path)
    action = svc.propose_next_action(project.id, "Review without old source")
    svc.decide_next_action(action["id"], True)
    cap = add(svc, project)
    out = svc.attest_next_action_done(action["id"], [cap.id], "Explicit operator claim")
    assert out["status"] == "operator_attested"
    assert project_card(svc, project)["completion_status"] == "not_independently_verified"


def test_more_than_eight_actions_are_bounded_but_flagged(tmp_path):
    svc, project = setup(tmp_path)
    for i in range(9):
        svc.propose_next_action(project.id, f"proposal-{i}")
    row = project_card(svc, project)
    assert row["operator_action_count"] == 9
    assert len(row["operator_actions"]) == 8
    assert row["operator_actions_truncated"] is True


def test_more_than_hundred_projects_report_partial_coverage(tmp_path):
    svc, _ = setup(tmp_path)
    for i in range(102):
        svc.store.upsert_project(ProjectRecord(
            profile_id=svc.active_profile_id,
            workspace_id=f"many-{i}",
            name=f"Many-{i:03}",
        ))
    result = svc.circle_back_review_board(limit=12, as_of=NOW)
    assert result["total_projects"] > 100
    assert result["projects_considered"] == 100
    assert result["coverage_complete"] is False
    assert len(result["cards"]) == 12
    assert result["cards_truncated"] is True
    assert sum(result["signals_in_considered_projects"].values()) == 100


@pytest.mark.parametrize("limit,days", [(0,30), (101,30), (True,30), (5,0), (5,3651)])
def test_review_board_bounds(tmp_path, limit, days):
    svc, _ = setup(tmp_path)
    with pytest.raises(ValueError):
        svc.circle_back_review_board(limit=limit, stale_days=days, as_of=NOW)


def test_cli_review_arguments_are_read_only(tmp_path):
    args = build_parser().parse_args(["--db", str(tmp_path / "local.db"), "review", "--limit", "7", "--stale-days", "15"])
    assert args.operation == "review"
    assert args.limit == 7 and args.stale_days == 15
    assert not hasattr(args, "confirm_local_operator")
