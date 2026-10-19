from app.core.service import MemoryService
from app.memory.models import IngestRequest, PolicyMode


def test_archive_lock_and_export_policy(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    cap = svc.ingest_text(IngestRequest(source_type='note', source_ref='x', text='private', policy=PolicyMode.private_local_only))[0]
    svc.set_capsule_state(cap.id, 'lock')
    exported = svc.export_capsules(include_private=False)
    ids = {c['id'] for c in exported['capsules']}
    assert cap.id not in ids
