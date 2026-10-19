from app.core.service import MemoryService


def test_module_review_flow(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    cat = svc.modules_catalog()
    out = svc.module_review(cat[0]['id'], 'approved', 'validated')
    assert out['review_state'] == 'approved'
