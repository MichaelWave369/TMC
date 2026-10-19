from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from app.core.service import MemoryService
from app.memory.models import IngestRequest

router = APIRouter()
service = MemoryService()


class RetrieveRequest(BaseModel):
    query: str
    context: dict = {}
    top_k: int = 5


class VaultCreate(BaseModel):
    display_name: str
    owner_label: str = "Local Operator"
    passphrase: str


class VaultUnlock(BaseModel):
    passphrase: str


class SyncPeerReq(BaseModel):
    device_name: str
    public_key: str = ""
    trust_status: str = "pending"


class SyncPreviewReq(BaseModel):
    target_device_id: str
    include_private: bool = False
    include_binaries: bool = False


class SyncApplyReq(BaseModel):
    session_id: str
    incoming_payload: dict | None = None


class SnapshotReq(BaseModel):
    vault_id: str
    profile_id: str | None = None


class RestoreReq(BaseModel):
    dry_run: bool = False
    selective: str = "all"


class ProfileReq(BaseModel):
    display_name: str
    default_vault_id: str = "vault-default"
    default_policy_profile: str = "strict"


class AgentStartReq(BaseModel):
    profile_id: str
    workspace_id: str
    task: str


class AgentAppendReq(BaseModel):
    role: str
    text: str


class AgentContextReq(BaseModel):
    profile_id: str
    workspace_id: str
    query: str
    session_id: str | None = None


class ApprovalReq(BaseModel):
    note: str = ""


class ConfigValidateReq(BaseModel):
    config: dict


class RepairApplyReq(BaseModel):
    preview: bool = True


class PluginInstallReq(BaseModel):
    plugin_id: str
    name: str
    version: str = "0.1.0"
    min_core_version: str = "0.7.0"
    plugin_type: str = "automation"
    requested_permissions: list[str] = []
    config_schema: dict = {}


class PluginApproveReq(BaseModel):
    permissions: list[str]


class ConnectorReq(BaseModel):
    connector_type: str
    name: str
    config: dict = {}


class WorkflowReq(BaseModel):
    workflow: dict


class WorkflowTestReq(BaseModel):
    event: dict


class AppRegisterReq(BaseModel):
    name: str
    scopes: list[str] = []


class ToolInvokeReq(BaseModel):
    tool: str
    payload: dict = {}
    scopes: list[str] = []


class ModuleReviewReq(BaseModel):
    decision: str
    note: str = ""


class PolicySimReq(BaseModel):
    action: str
    context: dict = {}
    template_name: str = "strict_private"


@router.post('/ingest')
def ingest(req: IngestRequest): return [c.model_dump(mode='json') for c in service.ingest_text(req)]


@router.post('/ingest/file')
def ingest_file(file: UploadFile = File(...)):
    Path('data').mkdir(exist_ok=True)
    path = f"data/uploads_{file.filename}"
    with open(path, 'wb') as f: f.write(file.file.read())
    return [c.model_dump(mode='json') for c in service.ingest_file(path)]


@router.post('/retrieve')
def retrieve(req: RetrieveRequest): return service.retrieve(req.query, req.context, req.top_k)


@router.get('/runtime/status')
def runtime_status(): return service.runtime_status()


@router.post('/runtime/start')
def runtime_start(): return service.runtime_start()


@router.post('/runtime/stop')
def runtime_stop(): return service.runtime_stop()


@router.post('/runtime/restart')
def runtime_restart(): return service.runtime_restart()


@router.post('/runtime/reindex')
def runtime_reindex(): return service.reindex()


@router.get('/jobs')
def jobs_list(): return service.list_jobs()


@router.post('/jobs/{job_id}/retry')
def jobs_retry(job_id: str): return service.retry_job(job_id)


@router.post('/jobs/{job_id}/cancel')
def jobs_cancel(job_id: str): return service.cancel_job(job_id)


@router.post('/repair/check')
def repair_check(): return service.repair_check()


@router.post('/repair/apply')
def repair_apply(req: RepairApplyReq): return service.repair_apply(req.preview)


@router.get('/config')
def config_get(): return service.get_config()


@router.post('/config/validate')
def config_validate(req: ConfigValidateReq): return service.validate_config(req.config)


@router.post('/support/export')
def support_export(redact: bool = True): return service.export_support(redact)


@router.get('/onboarding/status')
def onboarding_status(): return service.onboarding_status()


@router.post('/onboarding/complete')
def onboarding_complete(): return service.onboarding_complete()


@router.get('/plugins')
def plugins(): return service.plugin_list()


@router.post('/plugins/install')
def plugin_install(req: PluginInstallReq): return service.plugin_install(req.model_dump())


@router.post('/plugins/{plugin_id}/enable')
def plugin_enable(plugin_id: str): return service.plugin_enable(plugin_id)


@router.post('/plugins/{plugin_id}/disable')
def plugin_disable(plugin_id: str): return service.plugin_disable(plugin_id)


@router.get('/plugins/{plugin_id}/permissions')
def plugin_permissions(plugin_id: str): return service.plugin_permissions(plugin_id)


@router.post('/plugins/{plugin_id}/approve')
def plugin_approve(plugin_id: str, req: PluginApproveReq): return service.plugin_approve(plugin_id, req.permissions)


@router.get('/connectors')
def connectors(): return service.connector_list()


@router.post('/connectors')
def connector_add(req: ConnectorReq): return service.connector_add(req.connector_type, req.name, req.config)


@router.post('/connectors/{connector_id}/sync')
def connector_sync(connector_id: str): return service.connector_sync(connector_id)


@router.get('/workflows')
def workflows(): return service.workflow_list()


@router.post('/workflows')
def workflow_add(req: WorkflowReq): return service.workflow_create(req.workflow)


@router.post('/workflows/{workflow_id}/test')
def workflow_test(workflow_id: str, req: WorkflowTestReq): return service.workflow_test(workflow_id, req.event)


@router.get('/events')
def events(event_type: str | None = None): return service.events(event_type)


@router.get('/apps')
def apps(): return service.app_list()


@router.post('/apps/register')
def app_register(req: AppRegisterReq): return service.app_register(req.name, req.scopes)


@router.post('/apps/{app_id}/approve')
def app_approve(app_id: str): return service.app_approve(app_id)


@router.post('/tools/invoke')
def tools_invoke(req: ToolInvokeReq): return service.tool_invoke(req.tool, req.payload, req.scopes)


@router.get('/routing/suggestions')
def routing_suggestions(query: str = ""): return service.routing_suggestions(query)




@router.get('/compatibility')
def compatibility(): return service.compatibility()


@router.post('/policy/simulate')
def policy_simulate(req: PolicySimReq): return service.policy_simulate(req.action, req.context, req.template_name)


@router.get('/modules/catalog')
def modules_catalog(): return service.modules_catalog()


@router.post('/modules/{module_id}/review')
def module_review(module_id: str, req: ModuleReviewReq): return service.module_review(module_id, req.decision, req.note)


@router.get('/reports/operational')
def reports_operational(): return service.report_operational()


@router.get('/reports/memory-quality')
def reports_memory_quality(): return service.report_memory_quality()


@router.post('/upgrade/preview')
def upgrade_preview(target_version: str = "1.0.0"): return service.upgrade_preview(target_version)


@router.post('/upgrade/apply')
def upgrade_apply(target_version: str = "1.0.0"): return service.upgrade_apply(target_version)


@router.get('/onboarding/templates')
def onboarding_templates(): return service.onboarding_templates()


@router.get('/governance/review')
def governance_review(): return service.governance_review()




@router.get('/runtime/health')
def runtime_health(): return service.runtime_health()


@router.get('/release/validation')
def release_validation(): return service.release_validation()


@router.get('/release/readiness')
def release_readiness(): return service.release_readiness()


@router.get('/compatibility/summary')
def compatibility_summary(): return service.compatibility_summary()


@router.post('/migration/validate')
def migration_validate(target_version: str = "1.0.0"): return service.migration_validate(target_version)


@router.get('/warnings')
def warnings(): return service.warnings()


@router.get('/limitations')
def limitations(): return service.limitations()


@router.get('/performance/baseline')
def performance_baseline(): return service.performance_baseline()


@router.get('/vaults')
def vaults_list(): return service.list_vaults()


@router.post('/vaults')
def vaults_create(req: VaultCreate): return service.create_vault(req.display_name, req.owner_label, req.passphrase).model_dump(mode='json')


@router.post('/vaults/{vault_id}/lock')
def vaults_lock(vault_id: str): return service.lock_vault(vault_id)


@router.post('/vaults/{vault_id}/unlock')
def vaults_unlock(vault_id: str, req: VaultUnlock): return service.unlock_vault(vault_id, req.passphrase)


@router.post('/sync/peers')
def sync_peer_add(req: SyncPeerReq): return service.register_peer(req.device_name, req.public_key, req.trust_status).model_dump(mode='json')


@router.get('/sync/peers')
def sync_peers_list(): return service.list_peers()


@router.post('/sync/preview')
def sync_preview(req: SyncPreviewReq): return service.sync_preview(req.target_device_id, req.include_private, req.include_binaries).model_dump(mode='json')


@router.post('/sync/apply')
def sync_apply(req: SyncApplyReq): return service.sync_apply(req.session_id, req.incoming_payload)


@router.get('/sync/conflicts')
def sync_conflicts(): return service.list_conflicts()


@router.post('/snapshots/create')
def snapshot_create(req: SnapshotReq): return service.create_snapshot(req.vault_id, req.profile_id).model_dump(mode='json')


@router.get('/snapshots')
def snapshots(): return service.list_snapshots()


@router.post('/snapshots/{snapshot_id}/restore')
def snapshot_restore(snapshot_id: str, req: RestoreReq): return service.restore_snapshot(snapshot_id, req.dry_run, req.selective)


@router.get('/audit')
def audit(): return service.list_audit()


@router.get('/approvals')
def approvals(): return service.list_approvals()


@router.post('/approvals/{approval_id}/approve')
def approval_approve(approval_id: str, req: ApprovalReq): return service.approval_decide(approval_id, True, req.note)


@router.post('/approvals/{approval_id}/reject')
def approval_reject(approval_id: str, req: ApprovalReq): return service.approval_decide(approval_id, False, req.note)


@router.post('/profiles')
def profile_create(req: ProfileReq): return service.create_profile(req.display_name, req.default_vault_id, req.default_policy_profile).model_dump(mode='json')


@router.get('/profiles')
def profiles(): return service.list_profiles()


@router.post('/profiles/{profile_id}/switch')
def profile_switch(profile_id: str): return service.switch_profile(profile_id)


@router.post('/agent/session/start')
def agent_start(req: AgentStartReq): return service.agent_session_start(req.profile_id, req.workspace_id, req.task).model_dump(mode='json')


@router.post('/agent/session/{session_id}/append')
def agent_append(session_id: str, req: AgentAppendReq):
    s = service.agent_session_append(session_id, req.role, req.text)
    return s.model_dump(mode='json') if s else {'status': 'missing'}


@router.post('/agent/session/{session_id}/promote')
def agent_promote(session_id: str): return service.agent_session_promote(session_id)


@router.post('/agent/context/build')
def agent_context(req: AgentContextReq): return service.build_context_pack(req.profile_id, req.workspace_id, req.query, req.session_id)


@router.post('/agent/context/explain')
def agent_context_explain(req: AgentContextReq): return {'query': req.query, 'preview': service.build_context_pack(req.profile_id, req.workspace_id, req.query, req.session_id)}


@router.get('/diagnostics')
def diagnostics(): return service.diagnostics()
