"""Plugin manifest, registry, and lifecycle management."""
from __future__ import annotations

from dataclasses import dataclass, field


SUPPORTED_SCOPES = {
    "read_capsules", "write_capsules", "read_identity", "write_identity", "read_projects", "write_projects",
    "read_attachments", "manage_attachments", "retrieve_context", "run_actions", "manage_sync", "manage_vaults",
    "read_diagnostics", "operator_actions",
}


@dataclass
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    min_core_version: str
    plugin_type: str
    requested_permissions: list[str] = field(default_factory=list)
    config_schema: dict = field(default_factory=dict)


class PluginRegistry:
    def __init__(self, store) -> None:
        self.store = store

    def _key(self) -> str:
        return "plugin_registry"

    def list_plugins(self) -> list[dict]:
        import json
        return json.loads(self.store.get_kv(self._key(), "[]"))

    def _save(self, rows: list[dict]) -> None:
        import json
        self.store.set_kv(self._key(), json.dumps(rows))

    def install(self, manifest: PluginManifest) -> dict:
        perms = [p for p in manifest.requested_permissions if p in SUPPORTED_SCOPES]
        item = {
            "plugin_id": manifest.plugin_id,
            "name": manifest.name,
            "version": manifest.version,
            "min_core_version": manifest.min_core_version,
            "plugin_type": manifest.plugin_type,
            "requested_permissions": perms,
            "approved_permissions": [],
            "enabled": False,
            "health": "installed",
            "trust_status": "pending",
            "config_schema": manifest.config_schema,
        }
        rows = [p for p in self.list_plugins() if p["plugin_id"] != manifest.plugin_id]
        rows.append(item)
        self._save(rows)
        return item

    def approve(self, plugin_id: str, permissions: list[str]) -> dict:
        rows = self.list_plugins()
        out = {"status": "missing"}
        for p in rows:
            if p["plugin_id"] == plugin_id:
                p["approved_permissions"] = [x for x in permissions if x in p["requested_permissions"]]
                p["trust_status"] = "approved"
                out = p
        self._save(rows)
        return out

    def enable(self, plugin_id: str) -> dict:
        rows = self.list_plugins(); out = {"status": "missing"}
        for p in rows:
            if p["plugin_id"] == plugin_id:
                if not p["approved_permissions"]:
                    out = {"status": "denied", "reason": "permissions not approved"}
                    continue
                p["enabled"] = True
                p["health"] = "running"
                out = p
        self._save(rows)
        return out

    def disable(self, plugin_id: str) -> dict:
        rows = self.list_plugins(); out = {"status": "missing"}
        for p in rows:
            if p["plugin_id"] == plugin_id:
                p["enabled"] = False
                p["health"] = "stopped"
                out = p
        self._save(rows)
        return out
