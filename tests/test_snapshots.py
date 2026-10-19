from app.core.service import MemoryService


def test_snapshot_create_and_restore_preview(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    s = svc.create_snapshot('vault-default')
    p = svc.restore_snapshot(s.id, dry_run=True)
    assert p['status'] == 'preview'
