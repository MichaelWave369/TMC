"""Local connector framework."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConnectorRecord:
    connector_id: str
    connector_type: str
    name: str
    config: dict
    enabled: bool = True
    status: str = "idle"
    last_error: str = ""


class ConnectorManager:
    def __init__(self, store, service) -> None:
        self.store = store
        self.service = service

    def _key(self) -> str:
        return "connectors"

    def list(self) -> list[dict]:
        import json
        return json.loads(self.store.get_kv(self._key(), "[]"))

    def _save(self, rows: list[dict]):
        import json
        self.store.set_kv(self._key(), json.dumps(rows))

    def add(self, connector_type: str, name: str, config: dict) -> dict:
        from uuid import uuid4
        rec = ConnectorRecord(connector_id=f"conn-{uuid4()}", connector_type=connector_type, name=name, config=config).__dict__
        rows = self.list(); rows.append(rec); self._save(rows)
        return rec

    def sync(self, connector_id: str) -> dict:
        rows = self.list()
        for c in rows:
            if c["connector_id"] == connector_id:
                c["status"] = "syncing"
                if c["connector_type"] in {"folder", "notes", "markdown_kb", "json_csv", "manual_bundle"}:
                    sample_text = c["config"].get("sample_text", f"connector:{c['name']} ingest")
                    req = self.service._ingest_request(source_type=f"connector:{c['connector_type']}", source_ref=c["name"], text=sample_text)
                    self.service.ingest_text(req)
                    c["status"] = "ok"
                else:
                    c["status"] = "disabled"
                    c["last_error"] = "optional network connector disabled by default"
                self._save(rows)
                return c
        return {"status": "missing"}
