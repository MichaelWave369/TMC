"""Synthetic-only negative controls for local memory capability gateway R1."""
import pytest

from app.memory.models import (
    ApprovalItem, ApprovalStatus, Capsule, CapsuleStatus, PolicyMode,
)
from app.memory.polyglot import ReaderGrant
from app.memory.polyglot_gateway import LocalCapabilityGateway

KEY = b"test-secret-key-not-a-production-key-12345"
NOW = 1793510000


class Store:
    def __init__(self):
        self.capsule = Capsule(
            id="synthetic",
            source_type="synthetic_fixture",
            source_ref="fixture://r1",
            text="Fictional instruction: wrist-check gesture shows a menu.",
            summary="Fictional wrist menu",
            profile_id="demo",
            vault_id="demo-vault",
            workspace_ids=["vr-demo"],
            provenance=["fixture://r1"],
        )
        self.approval = ApprovalItem(
            id="approval-1",
            status=ApprovalStatus.approved,
            action_type="memory.polyglot.read",
            payload={
                "capsule_id": "synthetic",
                "reader": "brainc",
                "profile_id": "demo",
                "vault_id": "demo-vault",
                "workspace_ids": ["vr-demo"],
            },
        )

    def get_capsule(self, capsule_id):
        return self.capsule if capsule_id == self.capsule.id else None

    def get_approval(self, approval_id):
        return self.approval if approval_id == self.approval.id else None


def setup(tmp_path):
    store = Store()
    gateway = LocalCapabilityGateway(
        store=store, secret_key=KEY, ledger_path=tmp_path / "ledger.db"
    )
    grant = ReaderGrant("brainc", "demo", "demo-vault", frozenset({"vr-demo"}))
    return store, gateway, grant


def token(gateway, grant):
    return gateway.issue(
        capsule_id="synthetic", grant=grant, approval_id="approval-1", now=NOW
    )


def test_successful_read_and_audit(tmp_path):
    store, gateway, grant = setup(tmp_path)
    view = gateway.read(token=token(gateway, grant), reader="brainc", now=NOW + 1)
    assert view["view"]["text"] == store.capsule.text
    assert view["capsule_id"] == "synthetic"
    assert [r["outcome"] for r in gateway.audit_records()] == ["allowed"]


def test_replay_blocked_across_instances(tmp_path):
    store, gateway, grant = setup(tmp_path)
    value = token(gateway, grant)
    gateway.read(token=value, reader="brainc", now=NOW + 1)
    other = LocalCapabilityGateway(
        store=store, secret_key=KEY, ledger_path=tmp_path / "ledger.db"
    )
    with pytest.raises(PermissionError):
        other.read(token=value, reader="brainc", now=NOW + 2)
    assert [r["outcome"] for r in other.audit_records()] == ["allowed", "denied"]


def test_wrong_reader_rejected(tmp_path):
    _, gateway, grant = setup(tmp_path)
    with pytest.raises(PermissionError):
        gateway.read(token=token(gateway, grant), reader="sml", now=NOW + 1)


def test_token_tampering_rejected(tmp_path):
    _, gateway, grant = setup(tmp_path)
    value = token(gateway, grant)
    corrupted = ("A" if value[0] != "A" else "B") + value[1:]
    with pytest.raises(PermissionError):
        gateway.read(token=corrupted, reader="brainc", now=NOW + 1)


def test_token_expiration(tmp_path):
    _, gateway, grant = setup(tmp_path)
    with pytest.raises(PermissionError):
        gateway.read(token=token(gateway, grant), reader="brainc", now=NOW + 121)


def test_future_issuance_rejected(tmp_path):
    _, gateway, grant = setup(tmp_path)
    with pytest.raises(PermissionError):
        gateway.read(token=token(gateway, grant), reader="brainc", now=NOW - 1)


def test_wrong_secret_rejected(tmp_path):
    store, gateway, grant = setup(tmp_path)
    value = token(gateway, grant)
    other = LocalCapabilityGateway(
        store=store, secret_key=b"other-secret-key-1234567890-12345678",
        ledger_path=tmp_path / "ledger.db",
    )
    with pytest.raises(PermissionError):
        other.read(token=value, reader="brainc", now=NOW + 1)


@pytest.mark.parametrize("mutation", [
    {"status": ApprovalStatus.pending},
    {"status": ApprovalStatus.rejected},
    {"action_type": "some.other.permission"},
    {"payload": {"reader": "brainc"}},
])
def test_issue_requires_matching_operator_approval(tmp_path, mutation):
    store, gateway, grant = setup(tmp_path)
    for key, value in mutation.items():
        setattr(store.approval, key, value)
    with pytest.raises(PermissionError):
        token(gateway, grant)


def test_rejected_approval_invalidates_issued_token(tmp_path):
    store, gateway, grant = setup(tmp_path)
    value = token(gateway, grant)
    store.approval.status = ApprovalStatus.rejected
    with pytest.raises(PermissionError):
        gateway.read(token=value, reader="brainc", now=NOW + 1)


def test_updated_memory_invalidates_token(tmp_path):
    store, gateway, grant = setup(tmp_path)
    value = token(gateway, grant)
    store.capsule.text = "Different fictional memory text"
    with pytest.raises(PermissionError):
        gateway.read(token=value, reader="brainc", now=NOW + 1)


def test_deleted_memory_invalidates_token(tmp_path):
    store, gateway, grant = setup(tmp_path)
    value = token(gateway, grant)
    store.capsule.id = "replaced"
    with pytest.raises(PermissionError):
        gateway.read(token=value, reader="brainc", now=NOW + 1)


@pytest.mark.parametrize("policy", [
    PolicyMode.locked, PolicyMode.private_local_only,
    PolicyMode.session, PolicyMode.ephemeral,
])
def test_ineligible_memory_cannot_be_read(tmp_path, policy):
    store, gateway, grant = setup(tmp_path)
    value = token(gateway, grant)
    store.capsule.policy = policy
    with pytest.raises(PermissionError):
        gateway.read(token=value, reader="brainc", now=NOW + 1)


def test_nonactive_memory_cannot_be_read(tmp_path):
    store, gateway, grant = setup(tmp_path)
    value = token(gateway, grant)
    store.capsule.status = CapsuleStatus.pending_review
    with pytest.raises(PermissionError):
        gateway.read(token=value, reader="brainc", now=NOW + 1)


def test_capsule_revocation_persists(tmp_path):
    store, gateway, grant = setup(tmp_path)
    value = token(gateway, grant)
    gateway.revoke_capsule("synthetic", now=NOW)
    other = LocalCapabilityGateway(
        store=store, secret_key=KEY, ledger_path=tmp_path / "ledger.db"
    )
    with pytest.raises(PermissionError):
        other.read(token=value, reader="brainc", now=NOW + 1)
    with pytest.raises(PermissionError):
        token(other, grant)


def test_cross_profile_scope_denied(tmp_path):
    _, gateway, _ = setup(tmp_path)
    wrong = ReaderGrant("brainc", "other", "demo-vault", frozenset({"vr-demo"}))
    with pytest.raises(PermissionError):
        token(gateway, wrong)


def test_no_memory_text_or_bearer_in_audit(tmp_path):
    store, gateway, grant = setup(tmp_path)
    value = token(gateway, grant)
    gateway.read(token=value, reader="brainc", now=NOW + 1)
    assert store.capsule.text not in str(gateway.audit_records())
    assert value not in str(gateway.audit_records())


def test_minimum_key_length_and_persistent_ledger(tmp_path):
    with pytest.raises(ValueError):
        LocalCapabilityGateway(
            store=Store(), secret_key=b"short", ledger_path=tmp_path / "db"
        )
    with pytest.raises(ValueError):
        LocalCapabilityGateway(
            store=Store(), secret_key=KEY, ledger_path=":memory:"
        )


def test_sml_candidate_still_requires_review(tmp_path):
    store, gateway, _ = setup(tmp_path)
    store.approval.payload["reader"] = "sml"
    grant = ReaderGrant("sml", "demo", "demo-vault", frozenset({"vr-demo"}))
    view = gateway.read(token=token(gateway, grant), reader="sml", now=NOW + 1)
    assert view["view"]["candidate"]["state"] == "shadow"
    assert view["view"]["disposition"] == "review_only_unverified"


@pytest.mark.parametrize("bad_token", ["", "a", "ab.cd.ef", "%%.%%%"])
def test_malformed_tokens_denied(tmp_path, bad_token):
    _, gateway, _ = setup(tmp_path)
    with pytest.raises(PermissionError):
        gateway.read(token=bad_token, reader="brainc", now=NOW + 1)


def test_actual_tmc_sqlite_store_contract(tmp_path):
    """Exercise TMC's real capsule/approval persistence, not just the stub."""
    from app.memory.storage import SQLiteStore

    real_store = SQLiteStore(str(tmp_path / "tmc.db"))
    fixture = Store()
    real_store.upsert_capsule(fixture.capsule)
    real_store.upsert_approval(fixture.approval)
    gateway = LocalCapabilityGateway(
        store=real_store, secret_key=KEY, ledger_path=tmp_path / "audit.db"
    )
    grant = ReaderGrant("brainc", "demo", "demo-vault", frozenset({"vr-demo"}))
    view = gateway.read(token=token(gateway, grant), reader="brainc", now=NOW + 1)
    assert view["capsule_id"] == "synthetic"
    assert gateway.audit_records()[0]["outcome"] == "allowed"
