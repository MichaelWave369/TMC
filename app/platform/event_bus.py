"""Local internal event bus with bounded history."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class Event:
    event_type: str
    source: str
    payload: dict
    profile_id: str = "default"
    workspace_id: str = ""
    correlation_id: str = field(default_factory=lambda: f"corr-{uuid4()}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventBus:
    def __init__(self, max_history: int = 500) -> None:
        self.max_history = max_history
        self._history: deque[dict] = deque(maxlen=max_history)

    def publish(self, event: Event) -> dict:
        row = event.__dict__.copy()
        self._history.append(row)
        return row

    def list_events(self, event_type: str | None = None, profile_id: str | None = None) -> list[dict]:
        out = list(self._history)
        if event_type:
            out = [e for e in out if e["event_type"] == event_type]
        if profile_id:
            out = [e for e in out if e["profile_id"] == profile_id]
        return out

    def replay(self, limit: int = 100) -> list[dict]:
        return list(self._history)[-limit:]
