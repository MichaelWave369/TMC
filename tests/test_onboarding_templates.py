from app.core.service import MemoryService


def test_onboarding_templates_shape(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    tpl = svc.onboarding_templates()
    assert 'workflow_templates' in tpl and 'connector_templates' in tpl
