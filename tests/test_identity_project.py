from app.core.service import MemoryService
from app.memory.models import IngestRequest


def test_identity_promotion_and_project_assignment(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    caps = svc.ingest_text(IngestRequest(source_type='note', source_ref='a', text='I prefer concise responses', tags=['preference']))
    promoted = svc.promote_identity(caps[0].id)
    assert promoted is not None and promoted.kind.value == 'identity'
    proj = svc.create_project('ws-a', 'Workspace A')
    assigned = svc.assign_projects(caps[0].id, [proj.workspace_id])
    assert assigned is not None and proj.workspace_id in assigned.workspace_ids
