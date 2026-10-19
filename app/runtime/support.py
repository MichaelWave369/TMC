"""Local-only support bundle export with redaction."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def export_support_bundle(service, config_manager, redact: bool = True) -> dict:
    bundle_dir = Path("data/support")
    bundle_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    path = bundle_dir / f"tmc-support-{ts}.json"
    cfg = config_manager.export_non_secret() if redact else config_manager.load()
    payload = {
        "config": cfg,
        "runtime_status": service.runtime_status(),
        "diagnostics": service.diagnostics(),
        "jobs": service.list_jobs(),
        "errors": [j for j in service.list_jobs() if j.get("last_error")],
        "audit_excerpt": service.list_audit()[-20:],
        "version": "0.6.0",
    }
    path.write_text(json.dumps(payload, indent=2))
    return {"status": "ok", "path": str(path)}
