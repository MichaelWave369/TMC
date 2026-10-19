from app.core.service import MemoryService


def test_app_registration_and_approval(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    app = svc.app_register('local-assistant', ['read_capsules', 'retrieve_context'])
    approved = svc.app_approve(app['app_id'])
    assert approved['approved'] is True
