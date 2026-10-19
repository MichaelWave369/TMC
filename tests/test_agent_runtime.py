from app.core.service import MemoryService


def test_agent_session_and_promotion(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    s = svc.agent_session_start('default', 'ws-ops', 'test task')
    svc.agent_session_append(s.id, 'user', 'remember this preference')
    out = svc.agent_session_promote(s.id)
    assert out['status'] == 'ok'
