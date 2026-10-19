from app.core.service import MemoryService
from app.memory.models import IngestRequest


def test_contradiction_detection_marks_conflict(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    svc.ingest_text(IngestRequest(source_type='note', source_ref='a', text='I prefer email updates', tags=['preference']))
    out = svc.ingest_text(IngestRequest(source_type='note', source_ref='b', text='I do not prefer email updates', tags=['preference']))
    conflicts = svc.list_conflicts()
    assert conflicts
    assert out[0].status.value in {'conflicting', 'active'}
