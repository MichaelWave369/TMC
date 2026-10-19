from app.core.service import MemoryService
from app.memory.models import IngestRequest


def test_routing_suggestions(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    svc.ingest_text(IngestRequest(source_type='n', source_ref='x', text='I prefer weekly summaries', workspace_ids=['w1']))
    out = svc.routing_suggestions()
    assert isinstance(out, list)
