"""Local TF-IDF vector index for semantic retrieval."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass
class LocalVectorIndex:
    vectorizer: TfidfVectorizer = field(default_factory=lambda: TfidfVectorizer(ngram_range=(1, 2), min_df=1))
    ids: list[str] = field(default_factory=list)
    matrix: np.ndarray | None = None

    def rebuild(self, docs: list[tuple[str, str]]) -> None:
        # Switching to an empty profile must invalidate the prior profile's
        # vectors, not attempt to fit an empty TF-IDF vocabulary or keep stale data.
        self.ids = [d[0] for d in docs]
        self.matrix = None
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        if not docs:
            return
        texts = [d[1] for d in docs]
        try:
            tfidf = self.vectorizer.fit_transform(texts)
        except ValueError as exc:
            if "empty vocabulary" not in str(exc):
                raise
            # All docs may contain only whitespace or one-letter tokens.
            # Keep the record IDs for metadata ranking but no semantic vectors.
            return
        self.matrix = tfidf.toarray()

    def query(self, text: str) -> dict[str, float]:
        if not self.ids or self.matrix is None:
            return {}
        q = self.vectorizer.transform([text]).toarray()[0]
        denom = (np.linalg.norm(self.matrix, axis=1) * np.linalg.norm(q)) + 1e-8
        scores = (self.matrix @ q) / denom
        return {cid: float(score) for cid, score in zip(self.ids, scores)}
