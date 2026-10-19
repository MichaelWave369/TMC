# Second Brain: Circle-Back v0

**Status:** read-only local development feature, not a background autonomous agent.

## Why this first rung exists

A useful second brain shouldn't pretend that remembering a project means the project is finished. Circle-Back offers a deterministic queue of **operator review suggestions** for workspaces already registered in TMC.

- It reads existing project records and linked memory capsules.
- It never asserts that a stored memory is independently verified, even if a provenance string says otherwise.
- It provides source capsule **IDs**, not immutable proofs, text, file paths, or private memory content.
- It suggests a review step, not a claimed project completion, job execution, or automated merge.
- It never reads out another profile's projects or policy-hidden/locked-vault memory.

v0 only considers **persistent, non-private, non-archived**, unlocked-vault capsules. Other memories are not counted or exposed, and unavailable evidence is not silently substituted with a guess.

## Try it locally

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m app.tools.circle_back_preview --db data/tmc.db --limit 10
```

Starting a new database initializes TMC defaults, which may include **synthetic sample records**. Generating the queue itself performs no writes, triggers no jobs, and makes no network requests. CLI output is printed locally and is not suitable for public logs.

## Card semantics

- `needs_visible_evidence`: no eligible source capsules linked to a project. This doesn't establish that other private notes don't exist.
- `review_uncertain_sources`: visible linked capsules are marked uncertain, conflicting or pending review; this is an operator review signal, **not** a finding of real-world inconsistency.
- `stale_context`: last *visible* project/capsule update is at least the specified number of days old.
- `ready_for_operator_review`: visible linked memory exists, without stronger review signals. This is **not** a declaration of launch readiness.
- `source_capsule_ids`: at most five lookup pointers to source records, **not** signed or cryptographically immutable receipts.
- `provenance_assessment`: always `stored_memory_not_independently_verified`.

Review cards are ordered by signals, staleness, and name deterministically. TMC does **not** infer what a person truly finished.

## Boundaries and next gates

No new HTTP endpoint or unauthenticated UI page has been added. TMC's existing web API has no verified outer authentication layer and its vault cipher is not secure encryption. Keep using trusted loopback only with synthetic/non-sensitive data. Later rungs can add operator-approved "next action" records, evidence provenance, and retrieval hooks **after** appropriate authorization controls are designed and tested.
