"""Consolidation pass with bounded, auditable updates and bridge summaries."""
from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher

from app.memory.models import Capsule, CapsuleKind, CapsuleStatus, PolicyMode

MERGE_THRESHOLD = 0.92
MAX_UPDATES_PER_PASS = 20


def consolidate(capsules: list[Capsule], allow_locked_summary: bool = False) -> tuple[list[Capsule], dict[str, int]]:
    updates = merged = promoted = archived = bridges = 0
    by_id = {c.id: c for c in capsules}

    ids = list(by_id.keys())
    for i, ida in enumerate(ids):
        for idb in ids[i + 1 :]:
            if updates >= MAX_UPDATES_PER_PASS:
                break
            a, b = by_id[ida], by_id[idb]
            if PolicyMode.locked in {a.policy, b.policy}:
                continue
            sim = SequenceMatcher(None, a.text, b.text).ratio()
            if sim >= MERGE_THRESHOLD and b.status == CapsuleStatus.active:
                a.related_capsule_ids = sorted(set(a.related_capsule_ids + [b.id]))
                b.status = CapsuleStatus.archived
                b.provenance = sorted(set(b.provenance + [a.id]))
                updates += 1
                merged += 1

    themes = defaultdict(list)
    for c in capsules:
        for t in c.tags:
            themes[t].append(c)
    for theme, group in themes.items():
        if len(group) >= 3 and updates < MAX_UPDATES_PER_PASS:
            target = group[0]
            target.metadata["stable_preference"] = True
            target.importance = min(1.0, target.importance + 0.1)
            promoted += 1
            updates += 1
            if target.policy != PolicyMode.locked or allow_locked_summary:
                bridge = Capsule(
                    source_type="consolidation",
                    source_ref="scheduled-pass",
                    text=f"Repeated theme detected for '{theme}' across {len(group)} capsules.",
                    summary=f"Theme bridge: {theme}",
                    tags=["bridge", theme],
                    kind=CapsuleKind.summary_bridge,
                    related_capsule_ids=[g.id for g in group],
                    provenance=[g.id for g in group],
                )
                capsules.append(bridge)
                bridges += 1

    for c in capsules:
        if updates >= MAX_UPDATES_PER_PASS:
            break
        if c.policy == PolicyMode.locked:
            continue
        if c.importance < 0.3 and c.trust < 0.4 and c.status == CapsuleStatus.active:
            c.status = CapsuleStatus.archived
            archived += 1
            updates += 1

    return capsules, {"updates": updates, "merged": merged, "promoted": promoted, "archived": archived, "bridges": bridges}
