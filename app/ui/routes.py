from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.routes import service
from app.desktop.shell import launch

router = APIRouter()
templates = Jinja2Templates(directory='app/ui/templates')


@router.get('/', response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse('dashboard.html', {'request': request, 'diagnostics': service.diagnostics(), 'runtime': service.runtime_status(), 'desktop': launch(), 'recent_audit': service.list_audit()[-10:], 'onboarding': service.onboarding_status()})


@router.get('/plugins', response_class=HTMLResponse)
def plugins(request: Request):
    return templates.TemplateResponse('plugins.html', {'request': request, 'plugins': service.plugin_list()})


@router.get('/permissions', response_class=HTMLResponse)
def permissions(request: Request):
    return templates.TemplateResponse('permissions.html', {'request': request, 'plugins': service.plugin_list()})


@router.get('/connectors', response_class=HTMLResponse)
def connectors(request: Request):
    return templates.TemplateResponse('connectors.html', {'request': request, 'connectors': service.connector_list()})


@router.get('/workflows', response_class=HTMLResponse)
def workflows(request: Request):
    return templates.TemplateResponse('workflows.html', {'request': request, 'workflows': service.workflow_list()})


@router.get('/events', response_class=HTMLResponse)
def events(request: Request):
    return templates.TemplateResponse('events.html', {'request': request, 'events': service.events()[-200:]})


@router.get('/apps', response_class=HTMLResponse)
def apps(request: Request):
    return templates.TemplateResponse('apps.html', {'request': request, 'apps': service.app_list()})


@router.get('/tools', response_class=HTMLResponse)
def tools(request: Request):
    return templates.TemplateResponse('tools.html', {'request': request, 'audits': [a for a in service.list_audit() if a['action'].startswith('tool_') or a['action']=='tool_invocation']})


@router.get('/routing', response_class=HTMLResponse)
def routing(request: Request):
    return templates.TemplateResponse('routing.html', {'request': request, 'suggestions': service.routing_suggestions()})


@router.get('/runtime', response_class=HTMLResponse)
def runtime_page(request: Request):
    return templates.TemplateResponse('runtime.html', {'request': request, 'status': service.runtime_status(), 'jobs': service.list_jobs()})


@router.get('/jobs', response_class=HTMLResponse)
def jobs_page(request: Request):
    return templates.TemplateResponse('jobs.html', {'request': request, 'jobs': service.list_jobs()})


@router.get('/vaults', response_class=HTMLResponse)
def vaults_page(request: Request):
    return templates.TemplateResponse('vaults.html', {'request': request, 'vaults': service.list_vaults()})


@router.get('/sync', response_class=HTMLResponse)
def sync_page(request: Request):
    return templates.TemplateResponse('sync.html', {'request': request, 'peers': service.list_peers(), 'conflicts': service.list_conflicts()})


@router.get('/profiles', response_class=HTMLResponse)
def profiles_page(request: Request):
    return templates.TemplateResponse('profiles.html', {'request': request, 'profiles': service.list_profiles()})


@router.get('/agent', response_class=HTMLResponse)
def agent_page(request: Request):
    return templates.TemplateResponse('agent.html', {'request': request})


@router.get('/snapshots', response_class=HTMLResponse)
def snapshots_page(request: Request):
    return templates.TemplateResponse('snapshots.html', {'request': request, 'snapshots': service.list_snapshots()})


@router.get('/audit', response_class=HTMLResponse)
def audit_page(request: Request):
    return templates.TemplateResponse('audit.html', {'request': request, 'audits': service.list_audit()})


@router.get('/approvals', response_class=HTMLResponse)
def approvals_page(request: Request):
    return templates.TemplateResponse('approvals.html', {'request': request, 'approvals': service.list_approvals()})


@router.get('/repair', response_class=HTMLResponse)
def repair_page(request: Request):
    return templates.TemplateResponse('repair.html', {'request': request, 'checks': service.repair_check()})


@router.get('/ecosystem', response_class=HTMLResponse)
def ecosystem(request: Request):
    return templates.TemplateResponse('ecosystem.html', {'request': request, 'compat': service.compatibility(), 'catalog': service.modules_catalog()})


@router.get('/governance', response_class=HTMLResponse)
def governance(request: Request):
    return templates.TemplateResponse('governance.html', {'request': request, 'review': service.governance_review()})


@router.get('/integration-readiness', response_class=HTMLResponse)
def integration_readiness(request: Request):
    return templates.TemplateResponse('integration_readiness.html', {'request': request, 'apps': service.app_list(), 'templates': service.onboarding_templates()})


@router.get('/upgrade', response_class=HTMLResponse)
def upgrade_center(request: Request):
    return templates.TemplateResponse('upgrade.html', {'request': request, 'preview': service.upgrade_preview()})


@router.get('/modules', response_class=HTMLResponse)
def module_catalog(request: Request):
    return templates.TemplateResponse('modules.html', {'request': request, 'catalog': service.modules_catalog()})


@router.get('/release', response_class=HTMLResponse)
def release_dashboard(request: Request):
    return templates.TemplateResponse('release.html', {'request': request, 'validation': service.release_validation(), 'readiness': service.release_readiness(), 'warnings': service.warnings(), 'limitations': service.limitations()})
