"""Trusted local app integration registry."""
from __future__ import annotations


class AppIntegrationRegistry:
    def __init__(self, store) -> None:
        self.store = store

    def _key(self) -> str:
        return "registered_apps"

    def list(self) -> list[dict]:
        import json
        return json.loads(self.store.get_kv(self._key(), "[]"))

    def _save(self, rows: list[dict]):
        import json
        self.store.set_kv(self._key(), json.dumps(rows))

    def register(self, name: str, scopes: list[str]) -> dict:
        from uuid import uuid4
        app = {
            "app_id": f"app-{uuid4()}",
            "name": name,
            "client_key": f"local-{uuid4()}",
            "scopes": scopes,
            "approved": False,
            "health": "registered",
        }
        rows = self.list(); rows.append(app); self._save(rows)
        return app

    def approve(self, app_id: str) -> dict:
        rows = self.list(); out = {"status": "missing"}
        for a in rows:
            if a["app_id"] == app_id:
                a["approved"] = True; a["health"] = "active"; out = a
        self._save(rows)
        return out
