"""Receipt-aware, non-autonomous Circle-Back v0 safety checks."""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.service import MemoryService
from app.memory.models import CapsuleStatus, IngestRequest, PolicyMode

FUTURE = datetime(2035, 1, 1, tzinfo=timezone.utc)


def setup(tmp_path, key):
    svc = MemoryService(str(tmp_path / (key + ".db")))
    project = svc.create_project("workspace-" + key, "Test " + key)
    return svc, project


def add(svc, project, text="Synthetic note", policy=PolicyMode.persistent, vault_id="vault-default"):
    return svc.ingest_text(IngestRequest(
        source_type="unit_test",
        source_ref="synthetic",
        text=text,
        policy=policy,
        profile_id=svc.active_profile_id,
        workspace_ids=[project.workspace_id],
        vault_id=vault_id,
    ))[0]


def card_for(svc, project, *, as_of=FUTURE):
    queue = svc.circle_back_queue(as_of=as_of)
    return next(c for c in queue["cards"] if c["project_id"] == project.id)


def test_empty_evidence_prompts_review_not_fabricated_completion(tmp_path):
    svc, project = setup(tmp_path, "empty")
    c = card_for(svc, project)
    assert c["signal"] == "needs_visible_evidence"
    assert c["visible_evidence_count"] == 0
    assert c["completion_status"] == "not_assessed"
    assert c["source_capsule_ids"] == []
    assert c["provenance_assessment"] == "stored_memory_not_independently_verified"


def test_linked_receipts_trace_ids_without_returning_text_or_source_paths(tmp_path):
    svc, project = setup(tmp_path, "linked")
    capsule = add(svc, project, "Sensitive-looking but synthetic placeholder")
    queue = svc.circle_back_queue(as_of=FUTURE)
    row = next(c for c in queue["cards"] if c["project_id"] == project.id)
    assert capsule.id in row["source_capsule_ids"]
    assert "Sensitive-looking" not in str(queue)
    assert capsule.source_ref not in str(queue)
    assert queue["auto_actions"] is False
    assert queue["claim_of_verification"] is False


def test_private_session_locked_and_archived_records_not_disclosed(tmp_path):
    svc, project = setup(tmp_path, "policies")
    private = add(svc, project, "PRIVATE-MARKER", PolicyMode.private_local_only)
    session = add(svc, project, "SESSION-MARKER", PolicyMode.session)
    ephemeral = add(svc, project, "EPHEMERAL-MARKER", PolicyMode.ephemeral)
    locked = add(svc, project, "LOCKED-MARKER", PolicyMode.locked)
    archived = add(svc, project, "ARCHIVED-MARKER")
    archived.status = CapsuleStatus.archived
    svc.store.upsert_capsule(archived)
    queue = svc.circle_back_queue(as_of=FUTURE)
    card = card_for(svc, project)
    assert card["signal"] == "needs_visible_evidence"
    assert not set(card["source_capsule_ids"]) & {
        private.id, session.id, ephemeral.id, locked.id, archived.id
    }
    for marker in ["PRIVATE", "SESSION", "EPHEMERAL", "LOCKED", "ARCHIVED"]:
        assert marker not in str(queue)


def test_locked_vault_is_not_a_source(tmp_path):
    svc, project = setup(tmp_path, "vault")
    vault = svc.create_vault("Synthetic locked vault", "Local Operator", "test-passphrase")
    cap = add(svc, project, vault_id=vault.vault_id)
    assert cap.id not in card_for(svc, project)["source_capsule_ids"]


def test_cross_profile_isolation_and_empty_profile_safety(tmp_path):
    svc, project = setup(tmp_path, "profile")
    cap = add(svc, project)
    other = svc.create_profile("Other", "vault-default")
    svc.switch_profile(other.profile_id)
    queue = svc.circle_back_queue(as_of=FUTURE)
    assert queue["profile_id"] == other.profile_id
    assert all(c["project_id"] != project.id for c in queue["cards"])
    assert cap.id not in str(queue)


def test_conflicts_are_review_signals_not_truth_claims(tmp_path):
    svc, project = setup(tmp_path, "conflicts")
    cap = add(svc, project)
    cap.status = CapsuleStatus.conflicting
    svc.store.upsert_capsule(cap)
    c = card_for(svc, project)
    assert c["signal"] == "review_uncertain_sources"
    assert c["review_record_count"] == 1
    assert c["completion_status"] == "not_assessed"


def test_read_only_queue_does_not_change_capsules_or_audit(tmp_path):
    svc, project = setup(tmp_path, "readonly")
    cap = add(svc, project)
    before = cap.model_dump(mode="json")
    audits = len(svc.store.get_audits())
    first = svc.circle_back_queue(as_of=FUTURE)
    second = svc.circle_back_queue(as_of=FUTURE)
    assert first == second
    assert len(svc.store.get_audits()) == audits
    assert svc.store.get_capsule(cap.id).model_dump(mode="json") == before


def test_stale_vs_recent_and_priority_are_deterministic(tmp_path):
    svc, p1 = setup(tmp_path, "sort")
    p2 = svc.create_project("second-sort", "Another synthetic project")
    cap = add(svc, p1)
    cap.updated_at = FUTURE - timedelta(days=40)
    svc.store.upsert_capsule(cap)
    p1.updated_at = FUTURE - timedelta(days=50)
    svc.store.upsert_project(p1)
    p2.updated_at = FUTURE
    svc.store.upsert_project(p2)
    queue = svc.circle_back_queue(as_of=FUTURE, stale_days=30)
    by_id = {c["project_id"]: c for c in queue["cards"]}
    assert by_id[p1.id]["signal"] == "stale_context"
    assert by_id[p2.id]["signal"] == "needs_visible_evidence"
    assert queue["cards"][0]["project_id"] == p2.id


@pytest.mark.parametrize("limit,days", [(0, 30), (101, 30), (5, 0), (True, 30)])
def test_limits_are_bounded(tmp_path, limit, days):
    svc, _project = setup(tmp_path, "bad")
    with pytest.raises(ValueError):
        svc.circle_back_queue(limit=limit, stale_days=days, as_of=FUTURE)


def test_naive_clock_is_rejected(tmp_path):
    svc, _project = setup(tmp_path, "time")
    with pytest.raises(ValueError, match="timezone-aware"):
        svc.circle_back_queue(as_of=datetime(2035, 1, 1))
