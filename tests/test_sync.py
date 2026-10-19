from app.core.service import MemoryService


def test_device_registration_and_sync_preview(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    d = svc.register_peer('peer-A', 'pk', 'trusted')
    p = svc.sync_preview(d.device_id)
    assert p.target_device_id == d.device_id
