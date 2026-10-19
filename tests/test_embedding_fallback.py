from app.memory.embeddings import EmbeddingManager


def test_embedding_provider_fallback_is_deterministic():
    mgr = EmbeddingManager('sentence_transformers_local')
    assert mgr.provider_name == 'tfidf'
