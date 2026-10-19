from app.core.service import MemoryService


def test_context_pack_generation(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    out = svc.build_context_pack('default', 'ws-ops', 'preference')
    assert 'context_pack' in out and 'identity_pack' in out
