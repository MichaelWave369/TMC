"""Φ Memory Polyglot R3: offline courier tests, synthetic capsules only."""
from __future__ import annotations

import base64
import json

import pytest

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.memory.models import ApprovalItem, ApprovalStatus, Capsule
from app.memory.storage import SQLiteStore
from app.memory.polyglot import ReaderGrant
from app.memory.polyglot_gateway import LocalCapabilityGateway
from app.memory.polyglot_courier import seal_consumer_handoff, SCHEMA

NOW = 1820000001
PASS = "synthetic-demo-password-not-a-secret"
KEY = b"r3-test-capability-key-32-plus-bytes-abcdef"


def setup(tmp_path, reader="pocketbrain"):
    store = SQLiteStore(str(tmp_path / "source.db"))
    capsule = Capsule(
        id="synthetic-r3", source_type="synthetic_fixture",
        source_ref="fixture://memory/r3",
        text="Fictional wrist-menu gesture is activated by checking a watch.",
        summary="Fictional wrist gesture", tags=["synthetic", "vr"],
        profile_id="demo", vault_id="demo-vault", workspace_ids=["vr-demo"],
    )
    approval = ApprovalItem(
        id="approval-r3", status=ApprovalStatus.approved,
        action_type="memory.polyglot.read",
        payload={
            "capsule_id": capsule.id,
            "reader": reader,
            "profile_id": "demo",
            "vault_id": "demo-vault",
            "workspace_ids": ["vr-demo"],
        },
    )
    store.upsert_capsule(capsule)
    store.upsert_approval(approval)
    gateway = LocalCapabilityGateway(
        store=store, secret_key=KEY, ledger_path=tmp_path / "audit.db"
    )
    grant = ReaderGrant(reader, "demo", "demo-vault", frozenset({"vr-demo"}))
    token = gateway.issue(
        capsule_id=capsule.id, grant=grant, approval_id=approval.id, now=NOW
    )
    signing_key = ec.generate_private_key(ec.SECP256R1())
    return store, gateway, token, signing_key, capsule


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


@pytest.mark.parametrize("reader,kind", [
    ("pocketbrain", "compact_context"), ("brainc", "semantic_context"),
])
def test_seal_produces_pinned_signable_encrypted_r2(tmp_path, reader, kind):
    store, gateway, token, signing_key, capsule = setup(tmp_path, reader)
    pkg = seal_consumer_handoff(
        gateway, token=token, reader=reader, passphrase=PASS,
        signer=signing_key, now=NOW+1
    )
    assert pkg["schema"] == SCHEMA
    assert pkg["reader"] == reader
    assert pkg["expires_at"] - pkg["issued_at"] == 120
    assert capsule.text not in json.dumps(pkg)
    assert PASS not in json.dumps(pkg)
    assert token not in json.dumps(pkg)
    fields = ("schema", "reader", "issued_at", "expires_at", "salt", "iv", "ciphertext")
    signed = "\n".join(str(pkg[k]) for k in fields).encode("ascii")
    signature = _unb64(pkg["signature"])
    r, s = int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big")
    signing_key.public_key().verify(
        utils.encode_dss_signature(r, s),
        signed, ec.ECDSA(hashes.SHA256())
    )
    salt = _unb64(pkg["salt"])
    iv = _unb64(pkg["iv"])
    derived = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=310000
    ).derive(PASS.encode("utf-8"))
    aad = "\n".join(str(pkg[k]) for k in fields[:4]).encode("ascii")
    plaintext = AESGCM(derived).decrypt(iv, _unb64(pkg["ciphertext"]), aad)
    result = json.loads(plaintext)
    assert result["reader"] == reader
    assert result["capsule_id"] == capsule.id
    assert result["retention"] == "ephemeral_preview_only"
    assert result["evidence_status"] == "source_claim_not_independently_verified"
    assert result["payload"]["kind"] == kind
    assert gateway.audit_records()[0]["outcome"] == "allowed"
    assert store.get_capsule(capsule.id).text == capsule.text


def test_token_cannot_be_sealed_twice(tmp_path):
    _, gateway, token, signer, _ = setup(tmp_path)
    seal_consumer_handoff(gateway, token=token, reader="pocketbrain",
                          passphrase=PASS, signer=signer, now=NOW+1)
    with pytest.raises(PermissionError):
        seal_consumer_handoff(gateway, token=token, reader="pocketbrain",
                              passphrase=PASS, signer=signer, now=NOW+2)


@pytest.mark.parametrize("ttl", [0, 301, 1.3, True])
def test_ttl_rejected(tmp_path, ttl):
    _, gateway, token, signer, _ = setup(tmp_path)
    with pytest.raises(ValueError):
        seal_consumer_handoff(gateway, token=token, reader="pocketbrain",
                              passphrase=PASS, signer=signer, ttl_seconds=ttl, now=NOW+1)


def test_wrong_reader_cannot_seal(tmp_path):
    _, gateway, token, signer, _ = setup(tmp_path)
    with pytest.raises(PermissionError):
        seal_consumer_handoff(gateway, token=token, reader="brainc",
                              passphrase=PASS, signer=signer, now=NOW+1)


def test_weak_passphrase_rejected(tmp_path):
    _, gateway, token, signer, _ = setup(tmp_path)
    with pytest.raises(ValueError):
        seal_consumer_handoff(gateway, token=token, reader="pocketbrain",
                              passphrase="short", signer=signer, now=NOW+1)


def test_revocation_before_delivery_rejected(tmp_path):
    store, gateway, token, signer, _ = setup(tmp_path)
    approval = store.get_approval("approval-r3")
    approval.status = ApprovalStatus.rejected
    store.upsert_approval(approval)
    with pytest.raises(PermissionError):
        seal_consumer_handoff(gateway, token=token, reader="pocketbrain",
                              passphrase=PASS, signer=signer, now=NOW+1)


def test_capsule_revision_change_rejected(tmp_path):
    store, gateway, token, signer, capsule = setup(tmp_path)
    capsule.text = "Another fictional instruction"
    store.upsert_capsule(capsule)
    with pytest.raises(PermissionError):
        seal_consumer_handoff(gateway, token=token, reader="pocketbrain",
                              passphrase=PASS, signer=signer, now=NOW+1)
