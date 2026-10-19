from __future__ import annotations

from app.core.ranking import WEIGHTS, duplicate_penalty, identity_relevance, recency_score, session_relevance, sync_provenance_confidence, workspace_relevance
from app.memory.graph_store import MemoryGraph
from app.memory.models import RetrievalResult
from app.memory.policies import PolicyEngine


class RetrievalEngine:
    def __init__(self, embeddings, graph: MemoryGraph, policy: PolicyEngine) -> None:
        self.embeddings = embeddings
        self.graph = graph
        self.policy = policy

    def retrieve(self, query: str, capsules: list, context: dict, top_k: int = 5):
        sem = self.embeddings.query(query)
        qrel = {c.id for c in capsules if any(tok in c.text.lower() for tok in query.lower().split())}
        seen = set()
        sup = 0
        out = []
        for c in capsules:
            ok, reason = self.policy.allow_retrieval(c, context)
            if not ok:
                sup += 1
                continue
            b = {
                "semantic": sem.get(c.id, 0.0),
                "graph": self.graph.neighborhood_relevance(c.id, qrel),
                "recency": recency_score(c),
                "importance": c.importance,
                "trust": c.trust,
                "identity_relevance": identity_relevance(c, query),
                "workspace_relevance": workspace_relevance(c, context),
                "session_relevance": session_relevance(c, context),
                "sync_provenance_confidence": sync_provenance_confidence(c),
                "duplicate_penalty": duplicate_penalty(c, seen),
                "policy_allowance": 1.0,
            }
            score = sum(b[k] * WEIGHTS[k] for k in b)
            out.append(
                RetrievalResult(
                    capsule=c,
                    final_score=score,
                    breakdown=b,
                    policy_reason=reason,
                    selected_why="Hybrid relevance with policy filtering",
                    source_device=c.device_id,
                    synced_provenance_influence=c.sync_state != "local",
                    suppressed_count=sup,
                )
            )
        return sorted(out, key=lambda x: x.final_score, reverse=True)[:top_k]
