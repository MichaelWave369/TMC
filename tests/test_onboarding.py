from app.core.service import MemoryService


def test_onboarding_flow(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    assert svc.onboarding_status()['completed'] in {True, False}
    svc.onboarding_complete()
    assert svc.onboarding_status()['completed'] is True
