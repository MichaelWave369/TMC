from pathlib import Path

from app.core.service import MemoryService


def test_attachment_ingest_and_reingest(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    f = tmp_path / 'a.txt'
    f.write_text('attachment extracted text')
    svc.ingest_file(str(f))
    atts = svc.list_attachments()
    assert atts
    out = svc.reingest_attachment(atts[0]['id'])
    assert isinstance(out, list)
