from app.core.service import MemoryService
from app.memory.models import IngestRequest


def test_retrieval_explanation_fields(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    cap = svc.ingest_text(IngestRequest(source_type='note', source_ref='x', text='goal is offline reliable deployment', tags=['goal']))[0]
    svc.promote_identity(cap.id)
    out = svc.retrieve('goal offline', {}, 5)
    assert out and 'breakdown' in out[0] and 'selected_why' in out[0]
