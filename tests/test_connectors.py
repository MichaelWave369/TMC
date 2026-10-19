from app.core.service import MemoryService


def test_connector_add_and_sync(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    c = svc.connector_add('folder', 'notes-folder', {'sample_text': 'connector text'})
    out = svc.connector_sync(c['connector_id'])
    assert out['status'] == 'ok'
