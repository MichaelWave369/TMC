from app.core.service import MemoryService
from app.memory.models import IngestRequest


def test_delete_and_reindex(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    cap = svc.ingest_text(IngestRequest(source_type='note', source_ref='x', text='to delete'))[0]
    svc.delete_capsule(cap.id)
    assert svc.store.get_capsule(cap.id) is None
    info = svc.reindex()
    assert info['status'] == 'ok'
