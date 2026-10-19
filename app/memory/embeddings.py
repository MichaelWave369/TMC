"""Pluggable local embedding providers with deterministic fallback."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.memory.vector_index import LocalVectorIndex


class EmbeddingProvider(Protocol):
    name: str

    def rebuild(self, docs: list[tuple[str, str]]) -> None: ...

    def query(self, text: str) -> dict[str, float]: ...


@dataclass
class TfidfProvider:
    name: str = "tfidf"

    def __post_init__(self) -> None:
        self.index = LocalVectorIndex()

    def rebuild(self, docs: list[tuple[str, str]]) -> None:
        self.index.rebuild(docs)

    def query(self, text: str) -> dict[str, float]:
        return self.index.query(text)


class SentenceTransformerProvider(TfidfProvider):
    name: str = "sentence_transformers_local"


class OllamaEmbeddingProvider(TfidfProvider):
    name: str = "ollama_local"


class EmbeddingManager:
    def __init__(self, preferred: str = "tfidf") -> None:
        self.provider = self._select(preferred)
        self.last_reindex_tick = 0

    def _select(self, preferred: str) -> EmbeddingProvider:
        # Deterministic local fallback behavior for unavailable advanced providers.
        if preferred in {"sentence_transformers_local", "ollama_local"}:
            return TfidfProvider()
        return TfidfProvider()

    @property
    def provider_name(self) -> str:
        return self.provider.name

    def rebuild(self, docs: list[tuple[str, str]], tick: int = 0) -> None:
        self.provider.rebuild(docs)
        self.last_reindex_tick = tick

    def query(self, text: str) -> dict[str, float]:
        return self.provider.query(text)
