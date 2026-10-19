"""Circle-Back R2: detection of stale local evidence references without truth claims."""
from __future__ import annotations

from app.core.service import MemoryService
from app.memory.models import IngestRequest, NextActionStatus, PolicyMode
from app.memory.evidence_drift import snapshot_capsule, snapshot_status
from app.tools.circle_back_actions import build_parser
import pytest


def fixture(tmp_path):
    svc = MemoryService(str(tmp_path / "drift.db"))
    project = svc.create_project("r2-workspace", "R2 synthetic project")
    cap = svc.ingest_text(IngestRequest(
        source_type="test", source_ref="synthetic", text="Initial source snapshot",
        workspace_ids=[project.workspace_id],
    ))[0]
    proposal = svc.propose_next_action(
        project.id, "Operator decides", "No automatic completion", [cap.id]
    )
    return svc, project, cap, proposal


def test_proposal_has_local_snapshot_but_never_exposes_digest(tmp_path):
    svc, _, cap, proposal = fixture(tmp_path)
    stored = svc.store.get_next_action(proposal["id"])
    assert stored.source_snapshots[cap.id] == snapshot_capsule(cap)
    assert "source_snapshots" not in proposal
    assert "completion_snapshots" not in proposal
    listed = next(x for x in svc.list_next_actions() if x["id"] == proposal["id"])
    assert "source_snapshots" not in listed and "completion_snapshots" not in listed
    report = svc.assess_next_action_evidence(proposal["id"])
    assert report["source_snapshot_status"] == "unchanged_since_snapshot"
    assert report["completion_snapshot_status"] == "not_applicable"
    assert report["evidence_review"] == "consistent_with_local_snapshot"
    assert report["independent_verification"] is False
    assert cap.id not in str(report)
    assert stored.source_snapshots[cap.id] not in str(report)


def test_source_edit_blocks_approval_with_no_event_written(tmp_path):
    svc, _, cap, proposal = fixture(tmp_path)
    before = len(svc.next_action_history(proposal["id"]))
    cap.text = "This source changed after the proposal"
    svc.store.upsert_capsule(cap)
    report = svc.assess_next_action_evidence(proposal["id"])
    assert report["source_snapshot_status"] == "attention_required"
    assert report["evidence_review"] == "operator_recheck_required"
    with pytest.raises(ValueError, match="Source evidence changed"):
        svc.decide_next_action(proposal["id"], True)
    assert len(svc.next_action_history(proposal["id"])) == before
    assert svc.store.get_next_action(proposal["id"]).status == NextActionStatus.proposed
    assert svc.decide_next_action(proposal["id"], False)["status"] == "rejected"


def test_metadata_only_edits_are_detected(tmp_path):
    svc, _, cap, proposal = fixture(tmp_path)
    cap.metadata["operator_warning"] = "Added after proposal"
    svc.store.upsert_capsule(cap)
    assert svc.assess_next_action_evidence(proposal["id"])["source_snapshot_status"] == "attention_required"


@pytest.mark.parametrize("mode", ["private", "removed", "workspace", "locked_vault"])
def test_hidden_evidence_does_not_leak_ref_or_specific_count(tmp_path, mode):
    svc, _, cap, proposal = fixture(tmp_path)
    if mode == "private":
        cap.policy = PolicyMode.private_local_only
        svc.store.upsert_capsule(cap)
    elif mode == "removed":
        svc.store.delete_capsule(cap.id)
    elif mode == "workspace":
        cap.workspace_ids = ["different-workspace"]
        svc.store.upsert_capsule(cap)
    else:
        svc.lock_vault(cap.vault_id)
    report = svc.assess_next_action_evidence(proposal["id"])
    assert report["source_snapshot_status"] == "attention_required"
    assert report["evidence_review"] == "operator_recheck_required"
    assert "source_capsule_ids" not in report
    assert cap.id not in str(report)


def test_completion_source_drift_after_attestation(tmp_path):
    svc, project, cap, proposal = fixture(tmp_path)
    svc.decide_next_action(proposal["id"], True)
    completion = svc.ingest_text(IngestRequest(
        source_type="test", source_ref="completion",
        text="Operator-provided local completion note",
        workspace_ids=[project.workspace_id],
    ))[0]
    done = svc.attest_next_action_done(
        proposal["id"], [completion.id], "Operator review only"
    )
    assert done["status"] == "operator_attested"
    assert "completion_snapshots" not in done
    report = svc.assess_next_action_evidence(proposal["id"])
    assert report["source_snapshot_status"] == "unchanged_since_snapshot"
    assert report["completion_snapshot_status"] == "unchanged_since_snapshot"
    assert report["independent_verification"] is False
    completion.text = "Revised completion note"
    svc.store.upsert_capsule(completion)
    report = svc.assess_next_action_evidence(proposal["id"])
    assert report["source_snapshot_status"] == "unchanged_since_snapshot"
    assert report["completion_snapshot_status"] == "attention_required"
    assert "completion_evidence_ids" not in report


def test_old_r1_proposal_without_snapshot_remains_review_required(tmp_path):
    svc, _, cap, proposal = fixture(tmp_path)
    old = svc.store.get_next_action(proposal["id"])
    old.source_snapshots = {}
    # Emulate an older stored R1 action created before R2 metadata existed.
    with svc.store._connect() as conn:
        import json
        payload = old.model_dump(mode="json")
        payload.pop("source_snapshots")
        payload.pop("completion_snapshots")
        conn.execute(
            "UPDATE next_actions SET payload=? WHERE id=?",
            (json.dumps(payload), old.id),
        )
    result = svc.assess_next_action_evidence(old.id)
    assert result["source_snapshot_status"] == "snapshot_unavailable"
    assert result["evidence_review"] == "operator_recheck_required"
    with pytest.raises(ValueError, match="Source snapshot unavailable"):
        svc.decide_next_action(old.id, True)
    assert svc.decide_next_action(old.id, False)["status"] == "rejected"


def test_empty_proposal_and_rejected_action_make_no_verification_claim(tmp_path):
    svc, project, _, _ = fixture(tmp_path)
    row = svc.propose_next_action(project.id, "Review manually")
    before = len(svc.store.get_next_action_events(row["id"]))
    report = svc.assess_next_action_evidence(row["id"])
    assert report["source_snapshot_status"] == "not_applicable"
    assert report["completion_snapshot_status"] == "not_applicable"
    assert report["evidence_review"] == "no_evidence_snapshot"
    assert len(svc.store.get_next_action_events(row["id"])) == before
    svc.decide_next_action(row["id"], False)
    assert svc.assess_next_action_evidence(row["id"])["independent_verification"] is False


def test_evidence_check_is_non_mutating_and_survives_restart(tmp_path):
    svc, _, _, proposal = fixture(tmp_path)
    audits = len(svc.store.get_audits())
    events = len(svc.store.get_next_action_events(proposal["id"]))
    first = svc.assess_next_action_evidence(proposal["id"])
    second = svc.assess_next_action_evidence(proposal["id"])
    other = MemoryService(str(tmp_path / "drift.db"))
    assert first == second == other.assess_next_action_evidence(proposal["id"])
    assert len(svc.store.get_audits()) == audits
    assert len(svc.store.get_next_action_events(proposal["id"])) == events
    assert first["automatic_actions"] is False


def test_cross_profile_checks_denied_and_not_disclosed(tmp_path):
    svc, _, cap, proposal = fixture(tmp_path)
    other = svc.create_profile("Other profile", "vault-default")
    svc.switch_profile(other.profile_id)
    with pytest.raises(ValueError, match="not available"):
        svc.assess_next_action_evidence(proposal["id"])
    assert cap.id not in str(svc.list_next_actions())


def test_multiple_evidence_records_do_not_leak_changed_identity(tmp_path):
    svc, project, cap, proposal = fixture(tmp_path)
    second = svc.ingest_text(IngestRequest(
        source_type="test", source_ref="synthetic-2",
        text="Second source", workspace_ids=[project.workspace_id],
    ))[0]
    pair = svc.propose_next_action(project.id, "Check both", source_capsule_ids=[cap.id, second.id])
    second.text = "Changed second item"
    svc.store.upsert_capsule(second)
    out = svc.assess_next_action_evidence(pair["id"])
    assert out["source_snapshot_status"] == "attention_required"
    assert second.id not in str(out)
    assert cap.id not in str(out)


def test_pure_snapshot_result_states():
    assert snapshot_status([], {}, {}) == "not_applicable"
    assert snapshot_status(["one"], {}, {"one": "value"}) == "snapshot_unavailable"
    assert snapshot_status(["one"], {"one": "x"}, {}) == "attention_required"
    assert snapshot_status(["one"], {"one": "x"}, {"one": "y"}) == "attention_required"
    assert snapshot_status(["one"], {"one": "x"}, {"one": "x"}) == "unchanged_since_snapshot"


def test_check_cli_flag_is_explicitly_read_only():
    args = build_parser().parse_args(["--db", "local.db", "check", "--action-id", "action-synthetic"])
    assert args.operation == "check" and args.action_id == "action-synthetic"
