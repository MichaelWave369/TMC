# Φ Memory Polyglot R1: offline signed capability gateway

**Status:** experimental, local in-process Python library. **No new HTTP routes.** The memory stored in TMC remains canonical. This is not a network-ready service, an encrypted export, or an authenticated host application.

## What R1 adds

A TMC `ApprovalItem` with `status=approved` and `action_type="memory.polyglot.read"` can authorize one reader to view **one exact capsule revision** through the R0 read-only projector. The approval payload must match exactly:

```json
{
  "capsule_id": "synthetic",
  "reader": "brainc",
  "profile_id": "demo",
  "vault_id": "demo-vault",
  "workspace_ids": ["vr-demo"]
}
```

The local trusted operator process uses a **separately provisioned random 32+ byte secret** to issue an HMAC-SHA256 signed capability. No key is embedded in source. The serialized capability is a **bearer token**, not proof of the application's identity: the local process holding it can redeem it. R1 therefore assumes the operator process and its key are already trusted; use a local OS-backed secure secret store and properly separated, ACL-protected processes before real personal memory is introduced.

Capabilities are scoped to the reader, profile, vault, complete workspace set, capsule ID and complete capsule fingerprint. Default TTL is 120 seconds, max 300 seconds. Single-use nonce and capsule revocations are persisted in a separate SQLite ledger.

At redemption, R1 verifies signature, expiry, audience, active approval, current capsule existence, matching source fingerprint, and **every R0 memory policy check again**. It then atomically rejects replay or revoked capsule IDs, records a minimal local audit entry (timestamp, reader, capsule ID, allow/deny), and returns only a read-only projection.

The operator can change an approval to rejected or invoke `revoke_capsule` to refuse outstanding tokens. Deleted, modified, private, locked, non-active and out-of-scope capsules also fail closed. Revocation cannot retract copies of content already delivered to a reader.

## Offline usage (synthetic fixture only)

This is a Python library, not an HTTP listener, CLI listener, or browser bridge.

```python
from pathlib import Path
import secrets
from app.memory.models import ApprovalItem, ApprovalStatus, Capsule
from app.memory.storage import SQLiteStore
from app.memory.polyglot import ReaderGrant
from app.memory.polyglot_gateway import LocalCapabilityGateway

# Demonstration database files belong in an existing, private local directory.
private_dir = Path("/path/to/private-local-directory") # choose real private path
store = SQLiteStore(str(private_dir / "tmc-synthetic.db"))
capsule = Capsule(
    id="synthetic", source_type="synthetic_fixture", source_ref="fixture://demo",
    text="Fictional VR menu preference", summary="Fictional menu",
    profile_id="demo", vault_id="demo-vault", workspace_ids=["vr-demo"],
)
store.upsert_capsule(capsule)
grant = ReaderGrant("brainc", "demo", "demo-vault", frozenset({"vr-demo"}))
approval = ApprovalItem(
    status=ApprovalStatus.approved, action_type="memory.polyglot.read",
    payload={
        "capsule_id": "synthetic", "reader": "brainc", "profile_id": "demo",
        "vault_id": "demo-vault", "workspace_ids": ["vr-demo"],
    },
)
# This example manually creates an approval for a disposable test DB only.
# A real service must authenticate and authorize the approving operator.
store.upsert_approval(approval)
gateway = LocalCapabilityGateway(
    store=store, secret_key=secrets.token_bytes(32),
    ledger_path=private_dir / "memory-polyglot-audit.db",
)
token = gateway.issue(capsule_id="synthetic", grant=grant, approval_id=approval.id)
view = gateway.read(token=token, reader="brainc")
assert view["view"]["kind"] == "semantic_context"
```

**Tests:** `python -m pytest -q tests/test_memory_polyglot_gateway_r1.py`. A focused test imports and exercises TMC's real `SQLiteStore`, not only the fake store.

## Non-negotiable boundaries

- **No network exposure.** Existing TMC HTTP API has no complete authentication middleware and its legacy vault XOR transform is not secure encryption. A TMC approval record is **not itself proof that a human operator approved it** when an unauthenticated caller could alter it. R1 only adds a local capability-checking primitive and assumes approval issuance is independently protected.
- **No private data in the repo.** Do not check in keys, ledgers, audit identifiers, databases or exported capsules. Private directory permissions/ACLs and secure key provisioning remain the caller's responsibility. SQLite ledger files and backups are not encrypted here.
- **No automatic knowledge promotion.** SML gets a `shadow`, `local_only`, `review_only_unverified` candidate; no consensus, approval, execution, autonomous action or model invocation follows.
- **No completed consumer integration.** PocketBrain, BrainC, and SML do not yet import these views directly. The `reader` claim is bound to the signed capability, but a browser app could not securely hold the signing key itself. Any future bridge needs strong host authentication and per-consumer authorization.
- **No foolproof revocation across devices.** The shared ledger enforces replay/revocation only for processes using that same private ledger. A separate host/ledger is not automatically notified.
- **Not proof of integrity or provenance.** Capsule SHA-256 is a deterministic change indicator, not an independently signed evidence receipt; HMAC protects only token integrity against actors without the key.

## Next promotion gate

Before exposing *any* real memory to PocketBrain/BrainC, implement and independently test a credentialed, loopback-only gateway with authenticated per-app identity, host protection/ACLs, trusted operator approval issuance, cross-process replay tests, ledger backup and revocation semantics, bounded outputs, and privacy/security review. Do not wire this into the current unauthenticated TMC HTTP API.
