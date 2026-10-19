from app.core.service import MemoryService


def test_export_import_encrypted(tmp_path):
    svc1 = MemoryService(str(tmp_path / 'a.db'))
    blob = svc1.export_encrypted('pw')
    svc2 = MemoryService(str(tmp_path / 'b.db'))
    out = svc2.import_encrypted('pw', blob['ciphertext'])
    assert out['status'] == 'ok'
