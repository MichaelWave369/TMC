"""Sovereign automation rules engine."""
from __future__ import annotations


class RuleEngine:
    def __init__(self, store, service, event_bus) -> None:
        self.store = store
        self.service = service
        self.bus = event_bus
        self._recursion_guard: set[str] = set()

    def _key(self) -> str:
        return "workflows"

    def list_rules(self) -> list[dict]:
        import json
        return json.loads(self.store.get_kv(self._key(), "[]"))

    def _save(self, rows: list[dict]) -> None:
        import json
        self.store.set_kv(self._key(), json.dumps(rows))

    def create_rule(self, rule: dict) -> dict:
        from uuid import uuid4
        row = {
            "id": rule.get("id") or f"rule-{uuid4()}",
            "name": rule.get("name", "Unnamed Rule"),
            "trigger": rule.get("trigger", "capsule_created"),
            "condition": rule.get("condition", {}),
            "action": rule.get("action", {"type": "tag_capsule", "tag": "auto"}),
            "enabled": rule.get("enabled", True),
            "priority": int(rule.get("priority", 50)),
            "notes": rule.get("notes", ""),
        }
        rows = self.list_rules(); rows.append(row); self._save(rows)
        return row

    def test_rule(self, rule_id: str, event: dict) -> dict:
        rule = next((r for r in self.list_rules() if r["id"] == rule_id), None)
        if not rule:
            return {"status": "missing"}
        return {"status": "dry_run", "would_trigger": self._match(rule, event), "rule": rule}

    def handle_event(self, event: dict) -> list[dict]:
        outcomes = []
        key = f"{event.get('correlation_id','')}-{event.get('event_type','')}"
        if key in self._recursion_guard:
            return [{"status": "blocked", "reason": "loop_prevented"}]
        self._recursion_guard.add(key)
        try:
            for rule in sorted(self.list_rules(), key=lambda r: r["priority"]):
                if not rule["enabled"]:
                    continue
                if self._match(rule, event):
                    outcomes.append(self._apply(rule, event))
        finally:
            self._recursion_guard.discard(key)
        return outcomes

    def _match(self, rule: dict, event: dict) -> bool:
        if event.get("event_type") != rule["trigger"]:
            return False
        cond = rule.get("condition", {})
        if "contains" in cond:
            txt = str(event.get("payload", {})).lower()
            return cond["contains"].lower() in txt
        return True

    def _apply(self, rule: dict, event: dict) -> dict:
        act = rule["action"]
        t = act.get("type")
        if t == "create_job":
            j = self.service.enqueue_job(act.get("job_type", "automation"), {"rule_id": rule["id"]})
            return {"status": "ok", "action": "create_job", "job_id": j["id"]}
        if t == "trigger_snapshot":
            snaps = self.service.list_vaults()
            if snaps:
                s = self.service.create_snapshot(snaps[0]["vault_id"])
                return {"status": "ok", "action": "trigger_snapshot", "snapshot_id": s.id}
        if t == "request_approval":
            ap = self.service.store.get_approvals()
            return {"status": "ok", "action": "request_approval", "existing": len(ap)}
        return {"status": "ok", "action": "noop"}
