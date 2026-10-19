from app.core.service import MemoryService


def test_runtime_status_and_lifecycle(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    assert 'backend' in svc.runtime_status()
    svc.runtime_start()
    assert svc.runtime_status()['backend']['running']
    svc.runtime_stop()
    assert not svc.runtime_status()['backend']['running']
