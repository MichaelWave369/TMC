from app.core.service import MemoryService


def test_vault_unlock_flow(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    v = svc.create_vault('Ops Vault', 'Local Operator', 'secret')
    assert svc.lock_vault(v.vault_id)['status'] == 'locked'
    assert svc.unlock_vault(v.vault_id, 'secret')['status'] == 'unlocked'
