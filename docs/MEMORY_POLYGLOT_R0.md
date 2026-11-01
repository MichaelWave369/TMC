# Φ Memory Polyglot | Rung 0: local, read-only interchange experiment

**Owner:** Total Memory Core (TMC). **Status:** experimental, synthetic-only. **Network endpoints:** none.

The insight from a DOS/Linux binary polyglot is applied to memory **interpretation**, not executable headers: one canonical TMC `Capsule` is projected into three separately useful read-only representations without updating the source.

```text
TMC Capsule (immutable input to this operation)
        |
        v
out-of-band operator ReaderGrant + local policy/scope checks
        |                |               |
   PocketBrain        BrainC        SML candidate
   compact view     semantic view    shadow/review-only
        \                |               /
         Same capsule ID + canonical JSON SHA-256 change indicator
```

## Demo, without local services or real memory

```bash
python -m app.tools.polyglot_preview
python -m pytest -q tests/test_memory_polyglot_r0.py
```

The fixture uses a fictional wrist-menu requirement. It writes nothing and calls no APIs or models. The same source capsule yields:

- `pocketbrain`: a compact summary/tag context projection, **not** a live PocketBrain IndexedDB write.
- `brainc`: semantic-ready text, summary, tags, entities and relations, **not** a live BrainC memory insert.
- `sml`: a minimal Sovereign Memory Lattice `MemoryPacket`-shaped **shadow candidate**, with local-only collaboration and an explicit unverified/review-only disposition. No council run, promotion or proof claim is performed.

Every projection includes `schema`, `reader`, `capsule_id`, `source_sha256`, and `evidence_status`. The fingerprint is SHA-256 of the full TMC `Capsule.model_dump(mode="json")` with sorted canonical JSON keys. It detects *changes when compared against a trusted earlier value*; it is **not** an authenticity signature, evidence receipt, encrypted payload or proof of correctness. Source assertions are not independently verified.

## Fail-closed R0 rules

The `ReaderGrant` must be supplied **out of band** by a trusted local caller and must match the named reader, profile, vault and **all** capsule workspaces. Deny unknown readers, mismatches, workspace-less capsules and any memory outside local, active, persistent state (including private, locked, session, ephemeral, conflicting, uncertain and pending-review). Data embedded in the capsule cannot approve its own reader. A refusal does not include the text.

**Security boundary:** The grant record is not a credential, signature or authentication. A caller who can forge grant values or already access raw TMC capsules bypasses this experiment. TMC's HTTP routes currently lack external authentication and its legacy XOR vault is not secure encryption. Run the demo only with non-sensitive synthetic content. Do **not** expose this projector as a remote API or represent it as data-at-rest encryption. A real runtime integration must authenticate a reader, issue operator-bound grants outside capsule data, isolate the source store, and audit accesses before accessing personal memories.

## Ownership and next gates

- **TMC:** owns canonical capsules, operator decisions, policy and deletion boundaries. Never copies a second canonical truth into consumer memory.
- **SML:** owns candidate review/adjudication. A shadow projection alone cannot be promoted or executed. Conflicts, dissent and provenance should survive later transformations.
- **PocketBrain:** local browser memory, consent and encrypted backup remain its responsibility; prototype is a context projection only.
- **BrainC:** existing authenticated semantic memory and runtime/tool safeguards remain its responsibility; prototype is a context projection only.

Next steps only after R0 negative controls pass: (1) authenticated local read API with least-privilege grants and explicit consent; (2) authenticated readers/import validation on both sides; (3) revocation/deletion propagation; (4) cross-version schema tests; (5) SML packet integration tests without promoting source claims to verified truth; (6) encrypted transfer with independently reviewed implementation. No automatic web exposure, cloud sync, or autonomous actions.
