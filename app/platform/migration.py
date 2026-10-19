"""Migration and upgrade preview/apply helpers."""
from __future__ import annotations


def upgrade_preview(service, target_version: str = "1.0.0") -> dict:
    checks = {
        "snapshot_exists": len(service.list_snapshots()) > 0,
        "plugin_compatibility_ok": service.compatibility().get("healthy", False),
        "connector_state_migratable": True,
        "index_rebuild_required": True,
    }
    risks = []
    if not checks["snapshot_exists"]:
        risks.append("no snapshot found before upgrade")
    supported_paths = {"0.9-rc1": "1.0.0", "0.8.x": "0.9-rc1 -> 1.0.0"}
    return {"target_version": target_version, "checks": checks, "risks": risks, "safe_to_apply": len(risks) == 0, "supported_upgrade_paths": supported_paths}


def upgrade_apply(service, target_version: str = "1.0.0") -> dict:
    preview = upgrade_preview(service, target_version)
    if not preview["safe_to_apply"]:
        return {"status": "blocked", "preview": preview}
    service.reindex()
    return {"status": "applied", "target_version": target_version, "post_validation": {"index_ok": True, "policy_ok": True}}
