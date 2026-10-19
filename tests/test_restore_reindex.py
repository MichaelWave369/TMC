from app.core.service import MemoryService


def test_reindex_after_restore(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    s = svc.create_snapshot('vault-default')
    svc.restore_snapshot(s.id)
    out = svc.reindex()
    assert out['status'] == 'ok'
