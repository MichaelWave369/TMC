from app.core.service import MemoryService


def test_repair_preview_apply(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    p = svc.repair_apply(preview=True)
    assert p['status'] == 'preview'
    a = svc.repair_apply(preview=False)
    assert a['status'] == 'applied'
