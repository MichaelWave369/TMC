from pathlib import Path

from app.core.service import MemoryService


def test_support_bundle_export(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    out = svc.export_support(redact=True)
    assert out['status'] == 'ok'
    assert Path(out['path']).exists()
