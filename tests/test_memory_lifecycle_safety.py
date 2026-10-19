"""Negative controls for the restored local MemoryService operations."""
import pytest

from app.core.service import MemoryService
from app.memory.models import CapsuleKind, CapsuleStatus, IngestRequest, PolicyMode


def fresh(tmp_path):
    return MemoryService(str(tmp_path / "t.db"))


def add(svc, text="ordinary", policy=PolicyMode.persistent):
    return svc.ingest_text(IngestRequest(
        source_type="note", source_ref="unit", text=text, policy=policy
    ))[0]


def test_delete_cannot_cross_profile_or_delete_pinned(tmp_path):
    svc = fresh(tmp_path)
    cap = add(svc)
    cap.pinned = True
    svc.store.upsert_capsule(cap)
    assert svc.delete_capsule(cap.id) is False
    assert svc.store.get_capsule(cap.id) is not None
    cap.pinned = False
    svc.store.upsert_capsule(cap)
    other = svc.create_profile("Other", "vault-default")
    svc.switch_profile(other.profile_id)
    assert svc.delete_capsule(cap.id) is False
    assert svc.promote_identity(cap.id) is None
    assert svc.store.get_capsule(cap.id).kind == CapsuleKind.standard


def test_locked_memory_cannot_be_mutated_or_exported(tmp_path):
    svc = fresh(tmp_path)
    cap = add(svc)
    assert svc.set_capsule_state(cap.id, "lock") is not None
    assert svc.delete_capsule(cap.id) is False
    assert svc.promote_identity(cap.id) is None
    assert svc.assign_projects(cap.id, ["not-real"]) is None
    assert cap.id not in {c["id"] for c in svc.export_capsules(True)["capsules"]}
    assert svc.retrieve("ordinary", {}, 10)
    assert cap.id not in {r["capsule"]["id"] for r in svc.retrieve("ordinary", {}, 10)}


def test_private_export_requires_explicit_flag(tmp_path):
    svc = fresh(tmp_path)
    cap = add(svc, "local secret", PolicyMode.private_local_only)
    assert cap.id not in {c["id"] for c in svc.export_capsules()["capsules"]}
    assert cap.id in {c["id"] for c in svc.export_capsules(True)["capsules"]}


def test_import_rejects_conflicting_id_without_overwriting(tmp_path):
    svc = fresh(tmp_path)
    cap = add(svc, "source record")
    row = cap.model_dump(mode="json")
    assert svc.import_capsules({"capsules": [row]})["count"] == 0
    altered = {**row, "text": "forged content"}
    with pytest.raises(ValueError, match="conflict review"):
        svc.import_capsules({"capsules": [altered]})
    assert svc.store.get_capsule(cap.id).text == "source record"


def test_import_refuses_cross_profile_and_duplicate_ids(tmp_path):
    svc = fresh(tmp_path)
    cap = add(svc)
    row = cap.model_dump(mode="json")
    with pytest.raises(ValueError, match="Duplicate"):
        svc.import_capsules({"capsules": [row, row]})
    with pytest.raises(ValueError, match="Cross-profile"):
        svc.import_capsules({"capsules": [{**row, "profile_id": "other"}]})


def test_project_assignment_requires_owned_workspace(tmp_path):
    svc = fresh(tmp_path)
    cap = add(svc)
    with pytest.raises(ValueError, match="Unknown"):
        svc.assign_projects(cap.id, ["fabricated"])
    project = svc.create_project("verified-local", "Local example")
    assert svc.assign_projects(cap.id, [project.workspace_id]).workspace_ids == ["verified-local"]
    other = svc.create_profile("Other", "vault-default")
    svc.switch_profile(other.profile_id)
    assert svc.assign_projects(cap.id, [project.workspace_id]) is None


def test_attachment_change_requires_new_ingest(tmp_path):
    svc = fresh(tmp_path)
    path = tmp_path / "note.txt"
    path.write_text("first", encoding="utf-8")
    svc.ingest_file(str(path))
    attached = svc.list_attachments()[-1]
    assert isinstance(svc.reingest_attachment(attached["id"]), list)
    path.write_text("altered", encoding="utf-8")
    with pytest.raises(ValueError, match="Attachment changed"):
        svc.reingest_attachment(attached["id"])


def test_archival_state_retained_in_store(tmp_path):
    svc = fresh(tmp_path)
    cap = add(svc, "historical")
    saved = svc.set_capsule_state(cap.id, "archive")
    assert saved.status == CapsuleStatus.archived
    assert svc.store.get_capsule(cap.id).status == CapsuleStatus.archived
    with pytest.raises(ValueError, match="Unsupported"):
        svc.set_capsule_state(cap.id, "publish")
