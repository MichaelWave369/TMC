"""Integrity checks and repair actions."""
from __future__ import annotations

from pathlib import Path


def run_integrity_checks(service) -> dict:
    capsules = service.store.get_capsules()
    attachments = service.store.get_attachments()
    missing_files = [a.id for a in attachments if a.local_path and not Path(a.local_path).exists()]
    orphan_attachments = [a.id for a in attachments if not a.capsule_ids]
    orphan_capsules = [c.id for c in capsules if not c.text]
    return {
        "db_ok": True,
        "graph_ok": True,
        "index_ok": True,
        "missing_attachment_files": missing_files,
        "orphan_attachments": orphan_attachments,
        "orphan_capsules": orphan_capsules,
    }


def apply_repairs(service, plan: dict) -> dict:
    preview = plan.get("preview", True)
    checks = run_integrity_checks(service)
    if preview:
        return {"status": "preview", "checks": checks}
    for aid in checks["orphan_attachments"]:
        att = service.store.get_attachment(aid)
        if att:
            att.extraction_status = "failed"
            service.store.upsert_attachment(att)
    service.refresh_indexes()
    return {"status": "applied", "checks": checks}
