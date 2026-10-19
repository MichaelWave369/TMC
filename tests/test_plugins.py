from app.core.service import MemoryService


def test_plugin_lifecycle_and_permission_gate(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    p = svc.plugin_install({
        'plugin_id': 'plug-a', 'name': 'Plugin A', 'version': '1.0', 'min_core_version': '0.7.0',
        'plugin_type': 'automation', 'requested_permissions': ['read_capsules', 'operator_actions'], 'config_schema': {}
    })
    denied = svc.plugin_enable(p['plugin_id'])
    assert denied['status'] == 'denied'
    svc.plugin_approve(p['plugin_id'], ['read_capsules'])
    enabled = svc.plugin_enable(p['plugin_id'])
    assert enabled['enabled'] is True
