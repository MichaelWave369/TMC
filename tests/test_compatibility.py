from app.core.service import MemoryService


def test_compatibility_warns_on_unapproved_app(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    svc.app_register('partner-app', ['read_capsules'])
    rep = svc.compatibility()
    assert rep['issues']
