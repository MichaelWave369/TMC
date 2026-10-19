from app.core.service import MemoryService


def test_warnings_and_limitations_available(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    assert isinstance(svc.warnings(), list)
    assert isinstance(svc.limitations(), list)
