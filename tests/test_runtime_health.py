from app.core.service import MemoryService


def test_runtime_health_shape(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    h = svc.runtime_health()
    assert h['version'] == '1.0.0' and 'runtime' in h and 'compatibility' in h
