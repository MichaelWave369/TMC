from app.core.service import MemoryService
from app.memory.models import IngestRequest


def test_result_cap_behavior(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    for i in range(12):
        svc.ingest_text(IngestRequest(source_type='n', source_ref=str(i), text=f'alpha {i}'))
    out = svc.retrieve('alpha', {'profile_id': 'default'}, 5)
    assert len(out) <= 5
