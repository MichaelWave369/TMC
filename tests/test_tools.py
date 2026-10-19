from app.core.service import MemoryService


def test_tool_permission_enforcement_and_audit(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    denied = svc.tool_invoke('query_diagnostics', {}, scopes=['read_capsules'])
    assert denied['status'] == 'denied'
    ok = svc.tool_invoke('query_diagnostics', {}, scopes=['read_diagnostics'])
    assert ok['status'] == 'ok'
