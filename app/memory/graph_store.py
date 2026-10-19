"""NetworkX-backed relationship graph."""
from __future__ import annotations

import networkx as nx

from app.memory.models import Capsule


class MemoryGraph:
    def __init__(self) -> None:
        self.graph = nx.Graph()

    def rebuild(self, capsules: list[Capsule]) -> None:
        self.graph.clear()
        for capsule in capsules:
            self.graph.add_node(capsule.id, trust=capsule.trust)
        for capsule in capsules:
            for rel in capsule.related_capsule_ids:
                if self.graph.has_node(rel):
                    self.graph.add_edge(capsule.id, rel, weight=1.0)
            for other in capsules:
                if other.id == capsule.id:
                    continue
                if set(capsule.tags) & set(other.tags) or set(capsule.entities) & set(other.entities):
                    self.graph.add_edge(capsule.id, other.id, weight=0.3)

    def neighborhood_relevance(self, capsule_id: str, query_related_ids: set[str]) -> float:
        if not self.graph.has_node(capsule_id):
            return 0.0
        neighbors = set(self.graph.neighbors(capsule_id))
        if not neighbors:
            return 0.0
        overlap = len(neighbors & query_related_ids)
        return overlap / len(neighbors)

    def trust_centrality(self) -> dict[str, float]:
        if self.graph.number_of_nodes() == 0:
            return {}
        centrality = nx.degree_centrality(self.graph)
        return {k: min(1.0, v) for k, v in centrality.items()}
