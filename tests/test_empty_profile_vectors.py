"""Switching to an empty profile clears semantic state rather than crashing."""
from app.memory.vector_index import LocalVectorIndex
from app.core.service import MemoryService
from app.memory.models import IngestRequest


def test_empty_index_and_no_semantic_leak():
    index = LocalVectorIndex()
    index.rebuild([("one", "red bicycle")])
    assert "one" in index.query("red")
    index.rebuild([])
    assert index.ids == []
    assert index.query("red") == {}


def test_documents_without_vocabulary():
    index = LocalVectorIndex()
    index.rebuild([("one", ""), ("two", "a")])
    assert index.query("anything") == {}
    index.rebuild([("three", "memory capsule")])
    assert list(index.query("memory")) == ["three"]


def test_service_can_switch_to_empty_profile(tmp_path):
    svc = MemoryService(str(tmp_path / "state.db"))
    first = svc.ingest_text(IngestRequest(
        source_type="note", source_ref="test", text="private-alpha-memory"
    ))[0]
    second = svc.create_profile("Empty", "vault-default")
    svc.switch_profile(second.profile_id)
    assert svc.retrieve("private-alpha-memory", {}, 10) == []
    assert first.id not in svc.embeddings.query("private-alpha-memory")
