"""Persistent local job queue state."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


class JobSystem:
    def __init__(self, store):
        self.store = store

    def _key(self):
        return "jobs"

    def list_jobs(self) -> list[dict]:
        import json
        raw = self.store.get_kv(self._key(), "[]")
        return json.loads(raw)

    def _save(self, jobs: list[dict]):
        import json
        self.store.set_kv(self._key(), json.dumps(jobs))

    def enqueue(self, job_type: str, payload: dict | None = None) -> dict:
        j = {
            "id": f"job-{uuid4()}",
            "job_type": job_type,
            "status": "queued",
            "payload": payload or {},
            "retries": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_error": "",
        }
        jobs = self.list_jobs(); jobs.append(j); self._save(jobs)
        return j

    def update_status(self, job_id: str, status: str, error: str = ""):
        jobs = self.list_jobs()
        for j in jobs:
            if j["id"] == job_id:
                j["status"] = status
                j["last_error"] = error
        self._save(jobs)

    def retry(self, job_id: str):
        jobs = self.list_jobs()
        for j in jobs:
            if j["id"] == job_id:
                j["retries"] += 1
                j["status"] = "queued"
        self._save(jobs)

    def cancel(self, job_id: str):
        self.update_status(job_id, "cancelled")
