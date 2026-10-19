from app.memory.embeddings import EmbeddingManager
from app.memory.graph_store import MemoryGraph
from app.memory.models import Capsule
from app.memory.policies import PolicyEngine
from app.memory.retrieval import RetrievalEngine


def test_retrieval_returns_breakdown():
    c1 = Capsule(source_type='note', source_ref='a', text='offline mode matters', tags=['release'])
    c2 = Capsule(source_type='note', source_ref='b', text='gardening plans', tags=['home'])
    emb = EmbeddingManager('tfidf'); emb.rebuild([(c1.id, c1.text), (c2.id, c2.text)])
    graph = MemoryGraph(); graph.rebuild([c1, c2])
    engine = RetrievalEngine(emb, graph, PolicyEngine())
    out = engine.retrieve('offline mode', [c1, c2], {}, 2)
    assert out and 'semantic' in out[0].breakdown
