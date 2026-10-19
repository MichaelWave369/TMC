from app.core.service import MemoryService


def test_policy_simulation_blocks_private_export(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    out = svc.policy_simulate('export', {'is_private': True})
    assert out['allowed'] is False
