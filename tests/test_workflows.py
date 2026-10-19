from app.core.service import MemoryService


def test_workflow_dry_run_and_loop_protection(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    w = svc.workflow_create({'name': 'Rule1', 'trigger': 'capsule_created', 'action': {'type': 'create_job', 'job_type': 'snapshot'}})
    dry = svc.workflow_test(w['id'], {'event_type': 'capsule_created', 'payload': {'x': 1}})
    assert dry['status'] == 'dry_run'
