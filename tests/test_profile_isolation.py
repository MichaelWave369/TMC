from app.core.service import MemoryService
from app.memory.models import IngestRequest


def test_profile_workspace_isolation(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    p = svc.create_profile('P2', 'vault-default')
    svc.ingest_text(IngestRequest(source_type='n', source_ref='a', text='alpha', profile_id='default', workspace_ids=['w1']))
    svc.ingest_text(IngestRequest(source_type='n', source_ref='b', text='beta', profile_id=p.profile_id, workspace_ids=['w2']))
    r = svc.retrieve('beta', {'profile_id': 'default'}, 10)
    assert all(x['capsule']['profile_id'] == 'default' for x in r)
