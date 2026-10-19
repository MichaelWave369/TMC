from app.core.service import MemoryService


def test_job_queue_retry_cancel(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    job = svc.enqueue_job('indexing')
    assert any(j['id'] == job['id'] for j in svc.list_jobs())
    svc.retry_job(job['id'])
    svc.cancel_job(job['id'])
    cur = [j for j in svc.list_jobs() if j['id'] == job['id']][0]
    assert cur['status'] == 'cancelled'
