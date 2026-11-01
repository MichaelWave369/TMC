"""Synthetic-only Φ Memory Polyglot R2 interoperability negative controls."""
import json

import pytest

from app.memory.models import ApprovalItem, ApprovalStatus, Capsule
from app.memory.polyglot import ReaderGrant
from app.memory.polyglot_consumer import (
    EVIDENCE, RETENTION, SCHEMA, create_consumer_handoff,
)
from app.memory.polyglot_gateway import LocalCapabilityGateway

NOW = 1793510000
KEY = b"synthetic-test-key-please-do-not-use-in-prod"


class FixtureStore:
    def __init__(self, *, reader="pocketbrain"):
        self.capsule = Capsule(
            id="demo-r2", source_type="synthetic_fixture",
            source_ref="fixture://polyglot/r2",
            text="A fictional watch-check gesture opens a demo menu.",
            summary="Demo watch-check gesture",
            tags=["vr", "demo"], entities=["GenEWrist"],
            profile_id="demo", vault_id="demo-vault",
            workspace_ids=["vr-demo"],
        )
        self.approval = ApprovalItem(
            id="fixture-approval", status=ApprovalStatus.approved,
            action_type="memory.polyglot.read",
            payload={
                "capsule_id": "demo-r2", "reader": reader,
                "profile_id": "demo", "vault_id": "demo-vault",
                "workspace_ids": ["vr-demo"],
            },
        )

    def get_capsule(self, capsule_id):
        return self.capsule if self.capsule.id == capsule_id else None

    def get_approval(self, approval_id):
        return self.approval if self.approval.id == approval_id else None


def fixture(tmp_path, reader="pocketbrain"):
    store = FixtureStore(reader=reader)
    gateway = LocalCapabilityGateway(
        store=store, secret_key=KEY, ledger_path=tmp_path / "ledger.db"
    )
    grant = ReaderGrant(reader, "demo", "demo-vault", frozenset({"vr-demo"}))
    token = gateway.issue(
        capsule_id="demo-r2", grant=grant,
        approval_id="fixture-approval", now=NOW,
    )
    return store, gateway, token


@pytest.mark.parametrize("reader,kind", [
    ("pocketbrain", "compact_context"),
    ("brainc", "semantic_context"),
])
def test_two_readers_receive_distinct_bounded_context(tmp_path, reader, kind):
    store, gateway, token = fixture(tmp_path, reader)
    obj = create_consumer_handoff(gateway, token=token, reader=reader, now=NOW+1)
    assert obj["schema"] == SCHEMA
    assert obj["reader"] == reader
    assert obj["retention"] == RETENTION
    assert obj["evidence_status"] == EVIDENCE
    assert obj["payload"]["kind"] == kind
    assert obj["payload"]["truncated"] is False
    assert obj["capsule_id"] == store.capsule.id
    assert len(obj["source_sha256"]) == 64
    assert token not in json.dumps(obj)
    assert store.approval.id not in json.dumps(obj)


def test_pocketbrain_receives_summary_not_full_corpus(tmp_path):
    store, gateway, token = fixture(tmp_path)
    obj = create_consumer_handoff(gateway, token=token, reader="pocketbrain", now=NOW+1)
    assert obj["payload"]["text"] == store.capsule.summary
    assert store.capsule.text not in json.dumps(obj)


def test_brainc_receives_semantic_fields(tmp_path):
    _, gateway, token = fixture(tmp_path, "brainc")
    obj = create_consumer_handoff(gateway, token=token, reader="brainc", now=NOW+1)
    assert obj["payload"]["entities"] == ["GenEWrist"]
    assert obj["payload"]["tags"] == ["vr", "demo"]
    assert obj["payload"]["summary"] == "Demo watch-check gesture"


def test_unauthorized_reader_cannot_redeem(tmp_path):
    _, gateway, token = fixture(tmp_path)
    with pytest.raises(PermissionError):
        create_consumer_handoff(gateway, token=token, reader="brainc", now=NOW+1)


def test_sml_not_a_live_consumer(tmp_path):
    _, gateway, token = fixture(tmp_path)
    with pytest.raises(PermissionError, match="unsupported consumer"):
        create_consumer_handoff(gateway, token=token, reader="sml", now=NOW+1)


def test_replay_rejected(tmp_path):
    _, gateway, token = fixture(tmp_path)
    create_consumer_handoff(gateway, token=token, reader="pocketbrain", now=NOW+1)
    with pytest.raises(PermissionError):
        create_consumer_handoff(gateway, token=token, reader="pocketbrain", now=NOW+2)


def test_revoked_approval_rejected(tmp_path):
    store, gateway, token = fixture(tmp_path)
    store.approval.status = ApprovalStatus.rejected
    with pytest.raises(PermissionError):
        create_consumer_handoff(gateway, token=token, reader="pocketbrain", now=NOW+1)


def test_no_unbounded_payload(tmp_path):
    store, gateway, _ = fixture(tmp_path, "brainc")
    store.capsule.text = "X" * 10000
    store.capsule.summary = "S" * 1000
    store.capsule.tags = [f"long-{i}-" + "z" * 100 for i in range(12)]
    store.capsule.entities = [f"entity-{i}" for i in range(12)]
    grant = ReaderGrant("brainc", "demo", "demo-vault", frozenset({"vr-demo"}))
    token = gateway.issue(
        capsule_id=store.capsule.id, grant=grant,
        approval_id=store.approval.id, now=NOW,
    )
    obj = create_consumer_handoff(gateway, token=token, reader="brainc", now=NOW+1)
    assert len(obj["payload"]["text"]) == 4096
    assert len(obj["payload"]["summary"]) == 512
    assert len(obj["payload"]["tags"]) == 8
    assert len(obj["payload"]["entities"]) == 8
    assert obj["payload"]["truncated"] is True


def test_source_change_denies_old_handoff(tmp_path):
    store, gateway, token = fixture(tmp_path)
    store.capsule.text = "Changed demo"
    with pytest.raises(PermissionError):
        create_consumer_handoff(gateway, token=token, reader="pocketbrain", now=NOW+1)


def test_only_read_action_not_write(tmp_path):
    store, gateway, token = fixture(tmp_path)
    before = store.capsule.model_dump(mode="json")
    create_consumer_handoff(gateway, token=token, reader="pocketbrain", now=NOW+1)
    assert store.capsule.model_dump(mode="json") == before
