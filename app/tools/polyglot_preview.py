"""Synthetic-only, offline preview: python -m app.tools.polyglot_preview."""
from __future__ import annotations

from datetime import datetime, timezone
import json

from app.memory.models import Capsule
from app.memory.polyglot import ReaderGrant, project_capsule


def main() -> None:
    sample = Capsule(
        id="synthetic-wrist-001",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_type="synthetic_fixture",
        source_ref="fixture://vr/watch-gesture",
        text="Demo requirement: open a virtual wrist menu with a watch-check gesture.",
        summary="Use a natural wrist-check gesture for the menu.",
        tags=["vr", "interaction"],
        profile_id="demo",
        workspace_ids=["vr-demo"],
        vault_id="demo-vault",
        provenance=["fixture://vr/watch-gesture"],
    )
    views = {
        reader: project_capsule(
            sample,
            reader=reader,
            grant=ReaderGrant(reader, "demo", "demo-vault", frozenset({"vr-demo"})),
        )
        for reader in ("pocketbrain", "brainc", "sml")
    }
    print(json.dumps(views, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
