from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone


def compute_metrics(capsules: list, *, conflict_count: int = 0, attachment_backlog: int = 0, embedding_provider: str = "tfidf") -> dict:
    if not capsules:
        return {"L_t": 0.0, "L_diag_t": 0.0, "trust_mean": 0.0, "fragmentation": 0.0, "stale_ratio": 0.0, "duplicate_density": 0.0, "drift_indicator": 0.0, "contradiction_count": float(conflict_count), "attachment_extraction_backlog": float(attachment_backlog), "embedding_index_status": embedding_provider}
    now = datetime.now(timezone.utc)
    trust_mean = sum(c.trust for c in capsules) / len(capsules)
    stale = sum(1 for c in capsules if (now - c.updated_at).days > 30)
    dup = sum(v - 1 for v in Counter([c.summary.lower().strip() for c in capsules]).values() if v > 1)
    return {
        "L_t": float(len(capsules)),
        "L_diag_t": float(len(capsules)) * trust_mean,
        "trust_mean": trust_mean,
        "fragmentation": len({t for c in capsules for t in c.tags}) / max(1, len(capsules)),
        "stale_ratio": stale / len(capsules),
        "duplicate_density": dup / len(capsules),
        "drift_indicator": 1 - trust_mean,
        "contradiction_count": float(conflict_count),
        "attachment_extraction_backlog": float(attachment_backlog),
        "embedding_index_status": embedding_provider,
    }
