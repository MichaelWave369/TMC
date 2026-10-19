"""Permissioned memory tool invocation framework."""
from __future__ import annotations


TOOL_SCOPES = {
    "search_memory": "read_capsules",
    "retrieve_context_pack": "retrieve_context",
    "create_capsule": "write_capsules",
    "update_capsule": "write_capsules",
    "link_capsules": "write_capsules",
    "promote_memory": "write_identity",
    "archive_memory": "write_capsules",
    "lock_memory": "manage_vaults",
    "attach_file_metadata": "manage_attachments",
    "trigger_consolidation": "operator_actions",
    "request_snapshot": "operator_actions",
    "open_conflict_review": "read_diagnostics",
    "query_diagnostics": "read_diagnostics",
}


class ToolExecutor:
    def __init__(self, service) -> None:
        self.service = service

    def invoke(self, tool: str, payload: dict, granted_scopes: list[str]) -> dict:
        required = TOOL_SCOPES.get(tool)
        if not required:
            return {"status": "error", "error": "unknown_tool"}
        if required not in granted_scopes:
            self.service._audit("tool_denied", {"tool": tool, "required": required})
            return {"status": "denied", "required_scope": required}

        if tool == "search_memory":
            out = self.service.retrieve(payload.get("query", ""), payload.get("context", {}), payload.get("top_k", 5))
        elif tool == "retrieve_context_pack":
            out = self.service.build_context_pack(payload.get("profile_id", "default"), payload.get("workspace_id", ""), payload.get("query", ""), payload.get("session_id"))
        elif tool == "create_capsule":
            req = self.service._ingest_request(source_type="tool", source_ref="tool:create", text=payload.get("text", ""), profile_id=payload.get("profile_id", "default"), workspace_ids=payload.get("workspace_ids", []))
            out = [c.model_dump(mode="json") for c in self.service.ingest_text(req)]
        elif tool == "query_diagnostics":
            out = self.service.diagnostics()
        elif tool == "request_snapshot":
            out = self.service.create_snapshot(payload.get("vault_id", "vault-default")).model_dump(mode="json")
        else:
            out = {"status": "ok", "message": f"tool {tool} executed"}

        self.service._audit("tool_invocation", {"tool": tool})
        return {"status": "ok", "tool": tool, "result": out, "provenance": "tool_executor"}
