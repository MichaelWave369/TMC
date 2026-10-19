"""Policy enforcement logic."""
from __future__ import annotations

from app.memory.models import Capsule, PolicyMode


class PolicyEngine:
    def allow_retrieval(self, capsule: Capsule, context: dict) -> tuple[bool, str]:
        if capsule.policy == PolicyMode.locked:
            return False, "locked policy blocks retrieval"
        if capsule.policy == PolicyMode.private_local_only and context.get("allow_private") is not True:
            return False, "private_local_only requires explicit allow_private"
        if capsule.policy == PolicyMode.session and context.get("session_id") != capsule.metadata.get("session_id"):
            return False, "session policy mismatch"
        if capsule.policy == PolicyMode.ephemeral and context.get("ephemeral_ok") is not True:
            return False, "ephemeral policy requires explicit ephemeral_ok"
        return True, "policy allows retrieval"
