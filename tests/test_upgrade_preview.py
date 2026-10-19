from app.core.service import MemoryService


def test_upgrade_preview_reports_risk_without_snapshot(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    prev = svc.upgrade_preview('0.8.0')
    assert prev['safe_to_apply'] is False
