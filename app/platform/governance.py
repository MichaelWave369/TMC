"""Policy intelligence, templates, inheritance, and simulation."""
from __future__ import annotations


POLICY_TEMPLATES = {
    "strict_private": {
        "retention_default_days": 365,
        "identity_retention_days": 3650,
        "allow_export_private": False,
        "allow_sync_private": False,
        "workspace_privacy_mode": "strict",
        "plugin_policy_caps": {"write_identity": False},
    },
    "balanced_operator": {
        "retention_default_days": 180,
        "identity_retention_days": 1825,
        "allow_export_private": False,
        "allow_sync_private": False,
        "workspace_privacy_mode": "balanced",
        "plugin_policy_caps": {"write_identity": True},
    },
}


def effective_policy(context: dict, template_name: str = "strict_private") -> dict:
    base = dict(POLICY_TEMPLATES.get(template_name, POLICY_TEMPLATES["strict_private"]))
    base.update(context.get("overrides", {}))
    base["applies_to"] = {
        "profile": context.get("profile_id", "default"),
        "workspace": context.get("workspace_id", ""),
        "capsule_type": context.get("capsule_type", "standard"),
        "attachment_type": context.get("attachment_type", "generic"),
        "integration": context.get("integration", "operator"),
        "module_class": context.get("module_class", "core"),
    }
    return base


def detect_policy_conflicts(policy: dict) -> list[str]:
    issues = []
    if policy.get("allow_export_private") and not policy.get("allow_sync_private"):
        issues.append("export private enabled while sync private disabled")
    if policy.get("identity_retention_days", 0) < policy.get("retention_default_days", 0):
        issues.append("identity retention below default retention")
    return issues


def simulate_policy(action: str, context: dict, template_name: str = "strict_private") -> dict:
    eff = effective_policy(context, template_name)
    conflicts = detect_policy_conflicts(eff)
    allowed = True
    reason = "allowed"
    if action in {"export", "sync"} and context.get("is_private"):
        if action == "export" and not eff.get("allow_export_private"):
            allowed = False; reason = "private export blocked by policy"
        if action == "sync" and not eff.get("allow_sync_private"):
            allowed = False; reason = "private sync blocked by policy"
    return {"action": action, "allowed": allowed, "reason": reason, "effective_policy": eff, "conflicts": conflicts}
