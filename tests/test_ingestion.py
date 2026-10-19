from app.memory.ingestion import chunk_text, to_capsules
from app.memory.models import IngestRequest


def test_ingestion_chunking_v04():
    req = IngestRequest(source_type='note', source_ref='n1', text='a' * 1300, workspace_ids=['ws'])
    caps = to_capsules(req)
    assert len(caps) >= 2
    assert caps[0].workspace_ids == ['ws']


def test_chunk_text_overlap():
    chunks = chunk_text('abcdef' * 200, chunk_size=300, overlap=50)
    assert len(chunks) > 1
