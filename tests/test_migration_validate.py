from app.core.service import MemoryService


def test_migration_validate_maps_to_upgrade_preview(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    out = svc.migration_validate('1.0.0')
    assert 'safe_to_apply' in out and 'supported_upgrade_paths' in out
