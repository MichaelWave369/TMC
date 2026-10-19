"""Compatibility contracts, feature flags, and module diagnostics for v0.8."""
from __future__ import annotations

CORE_API_VERSION = "0.8"
PLUGIN_SDK_VERSION = "0.8"
CONNECTOR_INTERFACE_VERSION = "0.8"
TOOL_SCHEMA_VERSION = "0.8"
WORKFLOW_SCHEMA_VERSION = "0.8"

DEPRECATIONS = [
    {"id": "legacy_sync_preview_v1", "message": "sync preview v1 payload shape will be removed in v0.10", "severity": "warning"},
]

DEFAULT_FEATURE_FLAGS = {
    "experimental_module_channels": False,
    "lazy_diagnostics": True,
    "workflow_staged_rollout": True,
    "policy_conflict_detection": True,
    "connector_backpressure": True,
}


def negotiate_capabilities(core_caps: dict, module_caps: dict) -> dict:
    agreed = {k: module_caps.get(k, False) and core_caps.get(k, False) for k in core_caps}
    return {"agreed": agreed, "compatible": all(agreed.values()) if agreed else True}


def compatibility_report(plugins: list[dict], connectors: list[dict], apps: list[dict]) -> dict:
    issues = []
    for p in plugins:
        if p.get("min_core_version") and str(p["min_core_version"]).split(".")[0] > CORE_API_VERSION.split(".")[0]:
            issues.append({"type": "plugin", "id": p.get("plugin_id"), "issue": "requires newer core"})
    for c in connectors:
        if c.get("connector_type") == "webhook" and c.get("enabled"):
            issues.append({"type": "connector", "id": c.get("connector_id"), "issue": "network connector should be disabled by default"})
    for a in apps:
        if not a.get("approved"):
            issues.append({"type": "app", "id": a.get("app_id"), "issue": "not approved"})
    return {
        "core_api_version": CORE_API_VERSION,
        "plugin_sdk_version": PLUGIN_SDK_VERSION,
        "connector_interface_version": CONNECTOR_INTERFACE_VERSION,
        "tool_schema_version": TOOL_SCHEMA_VERSION,
        "workflow_schema_version": WORKFLOW_SCHEMA_VERSION,
        "deprecations": DEPRECATIONS,
        "feature_flags_default": DEFAULT_FEATURE_FLAGS,
        "issues": issues,
        "healthy": len(issues) == 0,
    }
