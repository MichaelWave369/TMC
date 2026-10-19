from app.core.service import MemoryService


def test_performance_baseline_report(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    out = svc.performance_baseline()
    assert 'retrieval_profile' in out and 'resource_ceilings' in out
