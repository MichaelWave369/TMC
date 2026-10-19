"""Onboarding templates and partner/internal readiness assets."""
from __future__ import annotations


def onboarding_templates() -> dict:
    return {
        "identity_project_sample": {
            "identity": "Operator prefers concise diagnostics summaries.",
            "project": "Project Atlas workspace bootstrap",
        },
        "connector_templates": [
            {"connector_type": "folder", "name": "Local Folder Ingest"},
            {"connector_type": "markdown_kb", "name": "Markdown Knowledge Base"},
        ],
        "workflow_templates": [
            {"name": "On contradiction, create review job", "trigger": "contradiction_detected", "action": {"type": "create_job", "job_type": "governance_review"}},
            {"name": "On vault unlock, trigger snapshot", "trigger": "vault_unlock", "action": {"type": "trigger_snapshot"}},
        ],
        "app_integration_profile": {"name": "Partner Sandbox", "scopes": ["read_capsules", "retrieve_context"], "sandbox_mode": True},
        "readiness_checklist": ["storage_check", "performance_check", "module_compatibility", "policy_baseline_selected"],
    }
