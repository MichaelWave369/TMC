from app.core.service import MemoryService


def test_release_validation_and_readiness(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    val = svc.release_validation()
    ready = svc.release_readiness()
    assert val['release'] == '1.0.0' and ready['status'] in {'ready', 'attention_required'}
