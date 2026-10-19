from app.core.service import MemoryService
from app.memory.models import IngestRequest


def test_service_ingest_retrieve(tmp_path):
    db = tmp_path / 't.db'
    svc = MemoryService(str(db))
    svc.ingest_text(IngestRequest(source_type='note', source_ref='x', text='deterministic offline release notes'))
    out = svc.retrieve('offline release', {'session_id': 'demo-session'})
    assert isinstance(out, list)
