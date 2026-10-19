from app.core.service import MemoryService


def test_operational_and_quality_reports(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    op = svc.report_operational()
    mq = svc.report_memory_quality()
    assert 'daily_summary' in op and 'state_distribution' in mq
