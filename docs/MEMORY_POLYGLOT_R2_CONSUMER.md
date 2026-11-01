# Φ Memory Polyglot R2: consumer handoff contract

**Experimental, offline, synthetic-data-only.** No network service, new TMC routes, autonomous writes, browser API, import, or persistence. Build atop merged R0/R1.

## Purpose

Convert an **already authorized** one-use TMC R1 read into a **bounded, typed, ephemeral context envelope** targeted at one specific consumer. This is a source-side producer contract, not a live connection or independently authenticated transfer mechanism.

```
Canonical TMC Capsule
       |
Operator approval + one-use signed R1 token
       |
LocalCapabilityGateway.read (scope / policy / revocation / audit)
       |
create_consumer_handoff
       +-- pocketbrain: compact_context (<=1024 chars)
       +-- brainc: semantic_context (<=4096 chars)
             |
       Explicit consumer preview/validation only
```

## Envelope shape

```json
{
  "schema": "phi.memory.polyglot.consumer.r2",
  "reader": "pocketbrain",
  "capsule_id": "synthetic-demo",
  "source_sha256": "<64 lower-case hex characters>",
  "evidence_status": "source_claim_not_independently_verified",
  "retention": "ephemeral_preview_only",
  "payload": {
    "kind": "compact_context",
    "text": "Synthetic watch-check gesture",
    "tags": ["vr", "demo"],
    "truncated": false
  }
}
```

A `brainc` envelope uses `kind=semantic_context` and additionally contains `summary` and `entities`. Tags/entities: at most eight, each at most 64 characters. Summary: at most 512 characters. Truncation is explicit. Capsule IDs and fingerprints are **correlation clues**, not signatures.

**No direct prompt insertion:** Memory text is untrusted data; an app must not treat it as a tool call, system instruction, authenticated claim, or model output. SML remains shadow/review-only in R0/R1 and is **not** a direct R2 consumer.

## Safe synthetic-only example

```python
from app.memory.polyglot_consumer import create_consumer_handoff

# Within a trusted local operator process, after an operator has approved
# the exact capsule/reader/profile/vault/workspaces and issued an R1 token:
envelope = create_consumer_handoff(
    gateway, token=issued_one_use_token, reader="pocketbrain"
)
# Keep in memory: do not save personal memory in a browser file, console or log.
```

Run `python -m pytest -q tests/test_memory_polyglot_consumer_r2.py` and full TMC CI.

## Threat model and next gates

- An R2 envelope is **not signed**, and any caller could fabricate one. The real trust check happens earlier at R1 redemption. A future transport must authenticate both endpoints and bind recipient, origin, channel, and operator consent. Reject direct import as verified evidence.
- R1's existing TMC approval record is not independently proof of human approval on an unauthenticated TMC HTTP surface. The operator process and key must be protected.
- No keys, actual memories, private exports or runtime databases in public source, test fixtures, HTML pages, Pages deployments or logs.
- The consumer adapters in PocketBrain and BrainC should enforce schema, audience, type, size, and ephemeral-only handling. A valid envelope is **still unverified**.
- A future stage should bind a trusted transport to app identity (including browser origin controls), add operator-visible per-reader approval and delivery previews, enforce revocation and delete propagation, and test offline + cross-process behavior.
- Only after an independent security review should real personal memories be introduced.

**Do not enable a public memory endpoint or auto-sync.**
