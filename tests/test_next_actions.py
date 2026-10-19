"""Circle-Back R1: explicit local decisions and policy-gated evidence."""
import pytest

from app.core.service import MemoryService
from app.memory.models import CapsuleStatus, IngestRequest, NextActionStatus, PolicyMode


def fresh(tmp_path):
    svc = MemoryService(str(tmp_path / "actions.db"))
    project = svc.create_project("operator-workspace", "Synthetic operator project")
    return svc, project


def capsule(svc, project, name="Supporting synthetic note", policy=PolicyMode.persistent):
    return svc.ingest_text(IngestRequest(
        source_type="test", source_ref="fixture",
        text=name, workspace_ids=[project.workspace_id],
        profile_id=svc.active_profile_id, policy=policy,
    ))[0]


def propose(svc, project, refs=None):
    return svc.propose_next_action(
        project.id, "Review next step",
        rationale="Synthetic operator choice",
        source_capsule_ids=refs,
    )


def test_proposal_is_unapproved_and_persistent(tmp_path):
    svc, project = fresh(tmp_path)
    row = propose(svc, project)
    assert row["status"] == "proposed"
    assert row["completion_evidence_ids"] == []
    history = svc.next_action_history(row["id"])
    assert [x["transition"] for x in history] == ["proposed"]
    other = MemoryService(str(tmp_path / "actions.db"))
    assert any(x["id"] == row["id"] for x in other.list_next_actions())


def test_decision_requires_explicit_boolean_and_writes_one_event(tmp_path):
    svc, project = fresh(tmp_path)
    row = propose(svc, project)
    before = len(svc.store.get_audits())
    with pytest.raises(ValueError, match="explicit boolean"):
        svc.decide_next_action(row["id"], "yes")
    assert svc.decide_next_action(row["id"], True, "I reviewed this")["status"] == "approved"
    assert [x["transition"] for x in svc.next_action_history(row["id"])] == ["proposed", "approved"]
    assert len(svc.store.get_audits()) == before  # no event bus / automation job
    with pytest.raises(ValueError, match="proposed"):
        svc.decide_next_action(row["id"], True)


def test_completion_is_operator_attested_not_verified(tmp_path):
    svc, project = fresh(tmp_path)
    cap = capsule(svc, project)
    row = propose(svc, project, [cap.id])
    with pytest.raises(ValueError, match="approved"):
        svc.attest_next_action_done(row["id"], [cap.id], "Test")
    svc.decide_next_action(row["id"], True)
    with pytest.raises(ValueError, match="At least one"):
        svc.attest_next_action_done(row["id"], [], "Test")
    with pytest.raises(ValueError, match="required"):
        svc.attest_next_action_done(row["id"], [cap.id], "")
    done = svc.attest_next_action_done(row["id"], [cap.id], "I checked locally")
    assert done["status"] == "operator_attested"
    assert done["completion_evidence_ids"] == [cap.id]
    listed = next(x for x in svc.list_next_actions() if x["id"] == row["id"])
    assert listed["evidence_claim"] == "operator_recorded_not_independently_verified"
    assert [x["transition"] for x in svc.next_action_history(row["id"])] == [
        "proposed", "approved", "operator_attested"
    ]
    with pytest.raises(ValueError, match="approved"):
        svc.attest_next_action_done(row["id"], [cap.id], "again")


def test_rejection_is_terminal_and_no_evidence_needed(tmp_path):
    svc, project = fresh(tmp_path)
    row = propose(svc, project)
    assert svc.decide_next_action(row["id"], False, "Not now")["status"] == "rejected"
    with pytest.raises(ValueError):
        svc.decide_next_action(row["id"], True)
    with pytest.raises(ValueError):
        svc.attest_next_action_done(row["id"], [], "No")


def test_evidence_requires_same_project_and_profile(tmp_path):
    svc, project = fresh(tmp_path)
    cap = capsule(svc, project)
    project2 = svc.create_project("another-workspace", "Another project")
    with pytest.raises(ValueError, match="not policy-visible"):
        propose(svc, project2, [cap.id])
    with pytest.raises(ValueError, match="Duplicate"):
        propose(svc, project, [cap.id, cap.id])
    row = propose(svc, project, [cap.id])
    other = svc.create_profile("Other", "vault-default")
    svc.switch_profile(other.profile_id)
    assert row["id"] not in {x["id"] for x in svc.list_next_actions()}
    with pytest.raises(ValueError, match="not available"):
        svc.decide_next_action(row["id"], True)
    with pytest.raises(ValueError, match="not available"):
        svc.next_action_history(row["id"])
    with pytest.raises(ValueError, match="Project is not available"):
        propose(svc, project, [cap.id])


@pytest.mark.parametrize("policy", [
    PolicyMode.private_local_only, PolicyMode.session,
    PolicyMode.ephemeral, PolicyMode.locked
])
def test_hidden_policy_records_rejected(tmp_path, policy):
    svc, project = fresh(tmp_path)
    cap = capsule(svc, project, policy=policy)
    with pytest.raises(ValueError, match="not policy-visible"):
        propose(svc, project, [cap.id])


def test_archived_or_missing_capsules_rejected(tmp_path):
    svc, project = fresh(tmp_path)
    cap = capsule(svc, project)
    cap.status = CapsuleStatus.archived
    svc.store.upsert_capsule(cap)
    with pytest.raises(ValueError, match="not policy-visible"):
        propose(svc, project, [cap.id])
    with pytest.raises(ValueError, match="not policy-visible"):
        propose(svc, project, ["not-a-real-capsule"])


def test_policy_change_blocks_approval_and_hides_reference(tmp_path):
    svc, project = fresh(tmp_path)
    cap = capsule(svc, project)
    row = propose(svc, project, [cap.id])
    cap.policy = PolicyMode.private_local_only
    svc.store.upsert_capsule(cap)
    listed = next(x for x in svc.list_next_actions() if x["id"] == row["id"])
    assert listed["source_capsule_ids"] == []
    assert svc.next_action_history(row["id"])[0]["evidence_capsule_ids"] == []
    with pytest.raises(ValueError, match="not policy-visible"):
        svc.decide_next_action(row["id"], True)
    assert svc.store.get_next_action(row["id"]).status == NextActionStatus.proposed
    assert svc.decide_next_action(row["id"], False)["status"] == "rejected"


def test_locked_vault_blocks_linked_evidence(tmp_path):
    svc, project = fresh(tmp_path)
    cap = capsule(svc, project)
    row = propose(svc, project, [cap.id])
    svc.lock_vault(cap.vault_id)
    with pytest.raises(ValueError, match="unavailable vault"):
        svc.decide_next_action(row["id"], True)


def test_completion_evidence_must_be_visible_in_same_workspace(tmp_path):
    svc, project = fresh(tmp_path)
    another = svc.create_project("other-workspace", "Other")
    othercap = capsule(svc, another)
    action = propose(svc, project)
    svc.decide_next_action(action["id"], True)
    with pytest.raises(ValueError, match="not policy-visible"):
        svc.attest_next_action_done(action["id"], [othercap.id], "not legitimate")


def test_status_guard_blocks_stale_transition_and_event_write(tmp_path):
    svc, project = fresh(tmp_path)
    action = propose(svc, project)
    rec = svc.store.get_next_action(action["id"])
    event_count = len(svc.store.get_next_action_events(action["id"]))
    from app.memory.models import NextActionEvent
    rec.status = NextActionStatus.approved
    with pytest.raises(ValueError, match="Stale"):
        svc.store.save_next_action_transition(
            rec,
            NextActionEvent(action_id=rec.id, profile_id=rec.profile_id, transition="approved"),
            expected_status=NextActionStatus.rejected.value,
        )
    assert len(svc.store.get_next_action_events(action["id"])) == event_count


def test_input_validation_never_leaks_into_event_history(tmp_path):
    svc, project = fresh(tmp_path)
    with pytest.raises(ValueError, match="Title is required"):
        svc.propose_next_action(project.id, " ")
    with pytest.raises(ValueError, match="at most 200"):
        svc.propose_next_action(project.id, "x" * 201)
    with pytest.raises(ValueError, match="at most 20"):
        propose(svc, project, ["x"] * 21)
    assert svc.store.get_next_actions() == []
