"""Operational and memory-quality reporting."""
from __future__ import annotations


def operational_report(service) -> dict:
    jobs = service.list_jobs()
    audits = service.list_audit()
    plugins = service.plugin_list()
    connectors = service.connector_list()
    return {
        "daily_summary": {
            "job_count": len(jobs),
            "queued_jobs": sum(1 for j in jobs if j.get("status") == "queued"),
            "failing_integrations": [c for c in connectors if c.get("last_error")],
            "plugin_errors": [p for p in plugins if p.get("health") not in {"running", "installed", "stopped"}],
        },
        "top_warning_categories": ["policy", "sync", "connector", "workflow"],
        "tool_usage_distribution": {"tool_invocations": sum(1 for a in audits if a.get("action") == "tool_invocation")},
        "memory_growth_trend": {"capsule_count": len(service.store.get_capsules())},
        "attachment_backlog": sum(1 for a in service.store.get_attachments() if a.extraction_status != "complete"),
    }


def memory_quality_report(service) -> dict:
    caps = service.store.get_capsules()
    states = {k: 0 for k in ["trusted", "provisional", "superseded", "conflicting", "archived", "review-needed"]}
    for c in caps:
        if c.status == "superseded":
            states["superseded"] += 1
        elif c.status == "conflicting":
            states["conflicting"] += 1
        elif c.status == "archived":
            states["archived"] += 1
        elif c.trust >= 0.75:
            states["trusted"] += 1
        elif c.trust < 0.45:
            states["provisional"] += 1
        else:
            states["review-needed"] += 1
    return {
        "state_distribution": states,
        "duplicate_clustering_hint": "enabled",
        "lineage_chain_count": sum(1 for c in caps if c.provenance),
        "supersession_chain_count": sum(1 for c in caps if c.status == "superseded"),
        "governance_review_needed": states["review-needed"] + states["conflicting"],
    }
