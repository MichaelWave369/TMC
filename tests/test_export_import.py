from app.core.service import MemoryService
from app.memory.models import IngestRequest, PolicyMode


def test_export_import_policy_preserved(tmp_path):
    db1 = tmp_path / 'a.db'
    db2 = tmp_path / 'b.db'
    svc1 = MemoryService(str(db1))
    cap = svc1.ingest_text(IngestRequest(source_type='note', source_ref='x', text='persist', policy=PolicyMode.persistent))[0]
    payload = svc1.export_capsules(include_private=True)
    svc2 = MemoryService(str(db2))
    svc2.import_capsules(payload)
    loaded = svc2.store.get_capsule(cap.id)
    assert loaded is not None and loaded.policy == PolicyMode.persistent
