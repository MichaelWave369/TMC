"""Central configuration manager for TMC v0.6."""
from __future__ import annotations

import json
from pathlib import Path


DEFAULT_CONFIG = {
    "profile": "local-operator",
    "storage_path": "data",
    "service_mode": False,
    "auto_start": False,
    "background_indexing": True,
    "scheduled_consolidation": True,
    "scheduled_snapshots": True,
    "embedding_provider": "tfidf",
    "result_cap": 8,
    "context_budget": 6000,
    "vault_auto_lock_on_exit": True,
    "vault_auto_lock_idle_min": 30,
    "log_level": "INFO",
}


class ConfigManager:
    def __init__(self, path: str = "data/config.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save(DEFAULT_CONFIG)

    def load(self) -> dict:
        return json.loads(self.path.read_text())

    def save(self, cfg: dict):
        self.path.write_text(json.dumps(cfg, indent=2))

    def validate(self, cfg: dict) -> tuple[bool, list[str]]:
        errors = []
        if cfg.get("result_cap", 0) <= 0:
            errors.append("result_cap must be > 0")
        if cfg.get("context_budget", 0) < 500:
            errors.append("context_budget too low")
        if cfg.get("vault_auto_lock_idle_min", 0) < 0:
            errors.append("vault_auto_lock_idle_min invalid")
        return (len(errors) == 0, errors)

    def export_non_secret(self) -> dict:
        cfg = self.load()
        return {k: v for k, v in cfg.items() if "passphrase" not in k and "secret" not in k}
