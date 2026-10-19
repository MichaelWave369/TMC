from app.core.service import MemoryService


def test_audit_and_approval_enforcement(tmp_path):
    svc = MemoryService(str(tmp_path / 't.db'))
    peer = svc.register_peer('peer', 'k', 'trusted')
    sess = svc.sync_preview(peer.device_id)
    pending = svc.sync_apply(sess.id, {'capsules': [{'id':'x','source_type':'n','source_ref':'s','text':'id mem','summary':'id','tags':[],'entities':[],'importance':0.5,'trust':0.5,'decay_class':'normal','policy':'persistent','status':'active','kind':'identity','profile_id':'default','workspace_ids':[],'vault_id':'vault-default','device_id':'peer','sync_state':'synced','pinned':False,'retention_weight':1.0,'related_capsule_ids':[],'provenance':[],'metadata':{}}]})
    assert pending['status'] == 'pending_approval'
    decision = svc.approval_decide(pending['approval_id'], True)
    assert decision['status'] == 'approved'
